# engine/voice/voice_main_wake.py
"""
Wake word -> record command -> speech-to-text -> plan -> run every action.

Latency notes (M2 MacBook Air):
  - Recording stops ~0.7 s after you stop talking (voice activity detection)
    instead of a fixed window, and long multi-step commands aren't cut off.
  - Speech-to-text runs locally with Whisper (~0.9 s) instead of uploading
    to AssemblyAI and polling (~3.5-6 s).
  - Simple commands skip the LLM entirely; others use a fast planner (~1 s).
"""

import json
import re
import subprocess
import time
from pathlib import Path

import numpy as np
import pyaudio
from openwakeword.model import Model
from openwakeword.vad import VAD

from engine.voice import stt, tts
from engine.voice.nlu import plan_command
from engine.dispatcher.actions import dispatch

DING_PATH = Path(__file__).resolve().parent / "wakewords" / "ding.wav"

RATE      = 16000
CHANNELS  = 1
FORMAT    = pyaudio.paInt16
CHUNK     = 1280    # 80 ms frames — required by openwakeword
CHUNK_SEC = CHUNK / RATE
THRESHOLD = 0.5     # wake word confidence (0–1); raise to reduce false triggers

# Command recording
VAD_THRESHOLD     = 0.5   # speech probability from the Silero VAD
END_SILENCE_SEC   = 0.7   # stop this long after you stop talking
NO_SPEECH_SEC     = 5.0   # give up if you say nothing after the wake word
MAX_COMMAND_SEC   = 15.0  # hard cap for very long commands
MIN_SPEECH_CHUNKS = 2     # ignore blips shorter than ~160 ms (e.g. the ding)

# Whisper sometimes "hears" these in background noise.
_NOISE_TEXT = {"", "you", "thank you", "thanks", "thanks for watching", "bye", "okay", "ok"}

# Actions that speak their own answer, so the planner's reply is skipped.
_SELF_SPEAKING = {"what_time", "what_date"}


def play_ding():
    if DING_PATH.exists():
        try:
            subprocess.Popen(["afplay", str(DING_PATH)])
        except Exception as e:
            print(f"[Wake] Failed to play ding: {e}")
    else:
        print(f"[Wake] ding.wav not found at {DING_PATH}")


def record_command(audio_stream, vad: VAD) -> np.ndarray | None:
    """Record until the speaker pauses. Returns int16 PCM, or None if nothing was said."""
    print("Listening for your command...")
    vad.reset_states()

    frames: list[np.ndarray] = []
    speech_chunks = 0
    started = False
    silence = 0.0

    while True:
        data = audio_stream.read(CHUNK, exception_on_overflow=False)
        pcm = np.frombuffer(data, dtype=np.int16)
        frames.append(pcm)
        elapsed = len(frames) * CHUNK_SEC

        if vad.predict(pcm, frame_size=640) >= VAD_THRESHOLD:
            speech_chunks += 1
            silence = 0.0
            if speech_chunks >= MIN_SPEECH_CHUNKS:
                started = True
        else:
            silence += CHUNK_SEC

        if started and silence >= END_SILENCE_SEC:
            break
        if not started and elapsed >= NO_SPEECH_SEC:
            return None
        if elapsed >= MAX_COMMAND_SEC:
            break

    return np.concatenate(frames)


def _looks_like_noise(text: str) -> bool:
    t = re.sub(r"[^\w\s']", "", text.lower()).strip()
    return t in _NOISE_TEXT or "voice commands for a mac assistant" in t


def run_actions(actions, text: str):
    for i, action in enumerate(actions):
        intent = action.get("intent")
        params = dict(action.get("params") or {})
        if intent == "open_app_generic" and i < len(actions) - 1:
            params["_wait"] = True  # let the app come to the front before the next step
        print(f"Action: {intent}, params={params}")
        try:
            dispatch(intent, text=text, params=params)
        except Exception as e:
            print(f"[Voice] Action {intent} failed: {e}")


def handle_command(audio_stream, vad: VAD):
    t_start = time.time()
    pcm = record_command(audio_stream, vad)
    t_recorded = time.time()

    if pcm is None:
        print("No command heard.")
        return

    try:
        text = stt.transcribe(pcm)
    except Exception as e:
        print(f"Error: Could not transcribe command: {e}")
        tts.speak("Sorry, I didn't catch that.")
        return
    t_heard = time.time()

    if _looks_like_noise(text):
        print("No command heard.")
        return
    print(f"Heard: {text!r}")

    plan = plan_command(text)
    t_planned = time.time()
    print(f"[Voice] Plan ({plan.source}): {plan.actions}")
    # For the app's Dashboard ("Last command" panel and the activity log)
    steps = " → ".join(a.get("intent", "?") for a in plan.actions) or "no action"
    print(json.dumps({"type": "VOICE", "text": text, "intent": steps}), flush=True)

    say = plan.say
    if any(a.get("intent") in _SELF_SPEAKING for a in plan.actions):
        say = ""
    if say:
        tts.speak(say)  # non-blocking: talks while the actions run

    if not plan.actions:
        print("No matching action.")
    run_actions(plan.actions, text)
    t_done = time.time()

    print(
        f"[Timing] listening {t_recorded - t_start:.1f}s | speech-to-text {t_heard - t_recorded:.2f}s | "
        f"planning {t_planned - t_heard:.2f}s ({plan.source}) | actions {t_done - t_planned:.2f}s | "
        f"~{t_done - t_recorded + END_SILENCE_SEC:.1f}s after you stopped talking"
    )
    print("Done.\n")


def _drain(audio_stream):
    """Drop audio that piled up while we were busy, so we react to fresh sound only."""
    try:
        available = audio_stream.get_read_available()
        if available:
            audio_stream.read(available, exception_on_overflow=False)
    except Exception:
        pass


def main():
    stt.preload()
    tts.preload()

    print("[Wake] Loading hey_jarvis model...")
    oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    vad = VAD()
    print("[Wake] Model ready.")

    pa = pyaudio.PyAudio()
    audio_stream = pa.open(
        rate=RATE,
        channels=CHANNELS,
        format=FORMAT,
        input=True,
        frames_per_buffer=CHUNK,
    )

    stt.wait_until_ready()  # so the first command isn't slowed by model loading
    _drain(audio_stream)
    print("Voice system ready.")
    print("Say the wake word: 'Hey Jarvis'")

    try:
        while True:
            audio_bytes = audio_stream.read(CHUNK, exception_on_overflow=False)
            scores = oww.predict(np.frombuffer(audio_bytes, dtype=np.int16))

            if max(scores.values(), default=0.0) >= THRESHOLD:
                print("Wake word detected.")
                play_ding()
                handle_command(audio_stream, vad)
                oww.reset()
                _drain(audio_stream)

    except KeyboardInterrupt:
        print("\nShutting down voice engine.")
    finally:
        audio_stream.stop_stream()
        audio_stream.close()
        pa.terminate()


if __name__ == "__main__":
    main()
