# engine/voice/stt.py
"""
Local speech-to-text with OpenAI Whisper (runs on this Mac, no upload).

The model is loaded once in a background thread so the first command
doesn't pay the load cost. If local Whisper isn't available, it falls back
to the AssemblyAI cloud API.

Measured on an M2 MacBook Air: ~0.9 s for a 4 s command with the "small"
model on CPU, versus 3.5-6 s for the AssemblyAI upload + polling flow.
(The Apple GPU / "mps" backend produces garbage with openai-whisper, so CPU
is used on purpose.)
"""

from __future__ import annotations

import io
import os
import re
import threading
import time
import wave
from pathlib import Path

import numpy as np

MODEL_NAME = os.environ.get("MHCI_WHISPER_MODEL", "small")
SAMPLE_RATE = 16000

# Nudges Whisper towards the words this assistant hears most often.
VOCAB_PROMPT = (
    "Voice commands for a Mac assistant: open Spotify, YouTube, Safari, "
    "Google Chrome, WhatsApp, Google Maps. Play MrBeast, Wizkid, Burna Boy, Davido."
)

# Optional: your own names/words, one per line or comma-separated (contacts,
# artists, apps), so Whisper spells them right, e.g. "Tunde, Adebayo, Asake".
CUSTOM_VOCAB_PATH = Path(__file__).resolve().parent / "custom_vocab.txt"
if CUSTOM_VOCAB_PATH.exists():
    _words = [w.strip() for w in re.split(r"[,\n]", CUSTOM_VOCAB_PATH.read_text(encoding="utf-8")) if w.strip()]
    if _words:
        VOCAB_PROMPT += " Names: " + ", ".join(_words[:60]) + "."

_model = None
_load_error: Exception | None = None
_ready = threading.Event()


def _load():
    global _model, _load_error
    try:
        t0 = time.time()
        import whisper  # heavy import (torch), so done off the main thread

        _model = whisper.load_model(MODEL_NAME, device="cpu")
        print(f"[STT] Whisper '{MODEL_NAME}' ready in {time.time() - t0:.1f}s", flush=True)
    except Exception as e:  # missing package/model -> cloud fallback
        _load_error = e
        print(f"[STT] Local Whisper unavailable ({e}); using AssemblyAI.", flush=True)
    finally:
        _ready.set()


def preload():
    """Start loading the model in the background (call once at startup)."""
    if not _ready.is_set() and not any(t.name == "whisper-load" for t in threading.enumerate()):
        threading.Thread(target=_load, name="whisper-load", daemon=True).start()


def wait_until_ready():
    preload()
    _ready.wait()


def _to_wav_bytes(pcm: np.ndarray) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.astype(np.int16).tobytes())
    return buf.getvalue()


def transcribe(pcm: np.ndarray) -> str:
    """Transcribe 16 kHz mono int16 audio to text."""
    preload()
    _ready.wait()

    if _model is not None:
        audio = pcm.astype(np.float32) / 32768.0
        result = _model.transcribe(
            audio,
            language="en",
            fp16=False,
            temperature=0.0,
            condition_on_previous_text=False,
            without_timestamps=True,
            initial_prompt=VOCAB_PROMPT,
        )
        return (result.get("text") or "").strip()

    from engine.voice.assemblyai_client import transcribe_audio_bytes

    return transcribe_audio_bytes(_to_wav_bytes(pcm))
