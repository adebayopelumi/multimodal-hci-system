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
import sys
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

PLAYER_SCRIPT = Path(__file__).resolve().parent / "audio_player.py"
_player: subprocess.Popen | None = None
_player_lock = threading.Lock()
_player_failures = 0  # (re)starts so far; reset once the player works


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


def _prepare(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    """Short fades (no clicks) and a little silence in front so the first word isn't clipped."""
    samples = np.asarray(samples, dtype=np.float32).copy()
    fade = min(len(samples) // 2, int(sample_rate * 0.005))
    if fade:
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        samples[:fade] *= ramp
        samples[-fade:] *= ramp[::-1]
    lead = np.zeros(int(sample_rate * 0.06), dtype=np.float32)
    tail = np.zeros(int(sample_rate * 0.08), dtype=np.float32)
    return np.concatenate([lead, samples, tail])


def _to_pcm16(samples: np.ndarray) -> bytes:
    return (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16).tobytes()


def _start_player() -> subprocess.Popen | None:
    """Start the audio player process (audio_player.py) and wait until it's ready."""
    global _player, _player_failures
    with _player_lock:
        if _player is not None and _player.poll() is None:
            return _player
        if _player_failures >= 3:
            return None  # stop retrying; use the fallbacks
        _player_failures += 1
        try:
            p = subprocess.Popen(
                [sys.executable, "-u", str(PLAYER_SCRIPT)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
            line = p.stdout.readline().strip()
            if line != b"ready":
                print(f"[TTS] Audio player didn't start ({line.decode(errors='replace')}).", flush=True)
                p.kill()
                return None
            _player = p
            _player_failures = 0
            return p
        except Exception as e:
            print(f"[TTS] Audio player didn't start ({e}).", flush=True)
            return None


def _play_player(samples: np.ndarray, sample_rate: int) -> bool:
    """
    Play through the separate audio player process. Playing inside this
    process made speech choppy: the audio callback needs Python's lock, and the
    wake-word loop or a YouTube lookup holding it for ~60 ms starved the
    ~46 ms audio buffer.
    """
    global _player
    p = _start_player()
    if p is None:
        return False
    pcm = _to_pcm16(samples)
    try:
        p.stdin.write(f"{sample_rate} {len(pcm) // 2}\n".encode() + pcm)
        p.stdin.flush()
        reply = p.stdout.readline().strip()  # returns once the clip has finished playing
    except Exception as e:
        reply = str(e).encode()
    if reply == b"done":
        return True
    print(f"[TTS] Audio player failed ({reply.decode(errors='replace') or 'exited'}).", flush=True)
    if p.poll() is None and not reply.startswith(b"error"):
        p.kill()
    if p.poll() is not None:
        _player = None
    return False


def _play_afplay(samples: np.ndarray, sample_rate: int) -> bool:
    """Fallback on macOS: robust, but adds ~0.85 s per clip."""
    fd, path = tempfile.mkstemp(prefix="mhci-tts-", suffix=".wav")
    os.close(fd)
    try:
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(_to_pcm16(samples))
        return subprocess.run(["afplay", path], check=False).returncode == 0
    except FileNotFoundError:
        return False
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _play_sounddevice(samples: np.ndarray, sample_rate: int) -> bool:
    try:
        import sounddevice as sd

        # Big buffer, so short stalls in this process don't cause dropouts.
        sd.play(samples, sample_rate, blocksize=2048, latency=0.3)
        sd.wait()
        return True
    except Exception as e:
        print(f"[TTS] sounddevice playback failed ({e}).", flush=True)
        return False


def _play(samples: np.ndarray, sample_rate: int):
    samples = _prepare(samples, sample_rate)
    if _play_player(samples, sample_rate):
        return
    if platform.system() == "Darwin" and _play_afplay(samples, sample_rate):
        return
    _play_sounddevice(samples, sample_rate)


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
    """Load the voice model and start the audio player in the background (call once at startup)."""
    threading.Thread(target=_load_kokoro, name="tts-load", daemon=True).start()
    threading.Thread(target=_start_player, name="tts-player", daemon=True).start()


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
