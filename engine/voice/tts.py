# engine/voice/tts.py
"""
Natural-sounding speech with Kokoro-82M (open source, Apache-2.0), run
locally through kokoro-onnx: https://github.com/thewh1teagle/kokoro-onnx

speak() never blocks the caller: text goes onto a queue and a background
thread synthesizes and plays it. If Kokoro or its model files are missing,
it falls back to the built-in macOS `say` voice.

Model files (not in git, ~340 MB) go in engine/voice/tts_models/:
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

Settings (environment variables):
  MHCI_VOICE        Kokoro voice, default "af_heart". Others: am_michael,
                    bf_emma, bm_george, af_bella, am_fenrir, ...
  MHCI_VOICE_SPEED  Speaking speed, default 1.05.
"""

from __future__ import annotations

import os
import platform
import queue
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path

import numpy as np

MODEL_DIR = Path(__file__).resolve().parent / "tts_models"
MODEL_PATH = MODEL_DIR / "kokoro-v1.0.onnx"
VOICES_PATH = MODEL_DIR / "voices-v1.0.bin"

VOICE = os.environ.get("MHCI_VOICE", "af_heart")
SPEED = float(os.environ.get("MHCI_VOICE_SPEED", "1.05"))
FALLBACK_MAC_VOICE = "Samantha"

_kokoro = None
_kokoro_failed = False
_load_lock = threading.Lock()
_queue: "queue.Queue[str]" = queue.Queue()
_worker: threading.Thread | None = None


def _lang_for(voice: str) -> str:
    # Kokoro voice ids start with a = American English, b = British English.
    return "en-gb" if voice.startswith("b") else "en-us"


def _load_kokoro():
    global _kokoro, _kokoro_failed
    with _load_lock:
        if _kokoro is not None or _kokoro_failed:
            return _kokoro
        try:
            t0 = time.time()
            from kokoro_onnx import Kokoro

            if not (MODEL_PATH.exists() and VOICES_PATH.exists()):
                raise FileNotFoundError(f"model files not found in {MODEL_DIR}")
            _kokoro = Kokoro(str(MODEL_PATH), str(VOICES_PATH))
            # Warm up so the first real sentence is fast.
            _kokoro.create("Ready.", voice=VOICE, speed=SPEED, lang=_lang_for(VOICE))
            print(f"[TTS] Kokoro voice '{VOICE}' ready in {time.time() - t0:.1f}s", flush=True)
        except Exception as e:
            _kokoro_failed = True
            print(f"[TTS] Kokoro unavailable ({e}); using the system voice.", flush=True)
        return _kokoro


def _play(samples: np.ndarray, sample_rate: int):
    try:
        import sounddevice as sd

        sd.play(samples, sample_rate)
        sd.wait()
        return
    except Exception as e:
        print(f"[TTS] sounddevice playback failed ({e}); using afplay.", flush=True)

    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
    subprocess.run(["afplay", path], check=False)
    os.unlink(path)


def _system_say(text: str):
    if platform.system() == "Darwin":
        subprocess.run(["say", "-v", FALLBACK_MAC_VOICE, text], check=False)
    else:
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"[TTS] No speech engine available: {e}", flush=True)


def _speak_now(text: str):
    kokoro = _load_kokoro()
    if kokoro is None:
        _system_say(text)
        return
    try:
        samples, sr = kokoro.create(text, voice=VOICE, speed=SPEED, lang=_lang_for(VOICE))
        _play(samples, sr)
    except Exception as e:
        print(f"[TTS] Kokoro failed ({e}); using the system voice.", flush=True)
        _system_say(text)


def _run_worker():
    while True:
        text = _queue.get()
        try:
            _speak_now(text)
        finally:
            _queue.task_done()


def _ensure_worker():
    global _worker
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_run_worker, name="tts", daemon=True)
        _worker.start()


def preload():
    """Load the voice model in the background (call once at startup)."""
    threading.Thread(target=_load_kokoro, name="tts-load", daemon=True).start()


def speak(text: str, block: bool = False):
    """Say text out loud. Returns immediately unless block=True."""
    text = (text or "").strip()
    if not text:
        return
    print(f"[TTS] {text}", flush=True)
    _ensure_worker()
    _queue.put(text)
    if block:
        _queue.join()


def wait_until_done():
    _queue.join()
