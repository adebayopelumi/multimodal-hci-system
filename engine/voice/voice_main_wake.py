# engine/voice/voice_main_wake.py

import io
import struct
import time
import wave
import subprocess
from pathlib import Path

import numpy as np
import pyaudio
from openwakeword.model import Model

from engine.voice.assemblyai_client import transcribe_audio_bytes
from engine.voice.nlu import predict_intents_with_params
from engine.dispatcher.actions import dispatch

DING_PATH = Path(__file__).resolve().parent / "wakewords" / "ding.wav"

RATE      = 16000
CHANNELS  = 1
FORMAT    = pyaudio.paInt16
CHUNK     = 1280    # 80 ms frames — required by openwakeword
THRESHOLD = 0.5     # detection confidence (0–1); raise to reduce false triggers


def play_ding():
    if DING_PATH.exists():
        try:
            subprocess.Popen(["afplay", str(DING_PATH)])
        except Exception as e:
            print(f"[Wake] Failed to play ding: {e}")
    else:
        print(f"[Wake] ding.wav not found at {DING_PATH}")


def record_command(
    audio_stream,
    pa,
    max_duration: float = 3.0,
    silence_timeout: float = 0.7,
    silence_threshold: int = 500,
) -> bytes:
    print("Listening for your command...")

    frames = []
    start_time = time.time()
    last_voice_time = start_time
    sample_width = pa.get_sample_size(FORMAT)

    while True:
        now = time.time()
        if now - start_time >= max_duration:
            break

        data = audio_stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

        pcm = struct.unpack_from("h" * CHUNK, data)
        avg_energy = sum(abs(s) for s in pcm) / len(pcm)

        if avg_energy > silence_threshold:
            last_voice_time = now
        else:
            if (now - last_voice_time) > silence_timeout and last_voice_time > start_time:
                break

    buffer = io.BytesIO()
    wav = wave.open(buffer, "wb")
    wav.setnchannels(CHANNELS)
    wav.setsampwidth(sample_width)
    wav.setframerate(RATE)
    wav.writeframes(b"".join(frames))
    wav.close()
    return buffer.getvalue()


def handle_command(audio_stream, pa):
    wav_bytes = record_command(audio_stream, pa)

    try:
        text = transcribe_audio_bytes(wav_bytes)
    except Exception as e:
        print(f"Error: Could not transcribe command: {e}")
        return

    if not text:
        print("No command heard.")
        return

    print(f"Heard: {text!r}")

    intents = predict_intents_with_params(text)
    if not intents:
        print("No matching action.")
        return

    for item in intents:
        intent = item.get("intent")
        params = item.get("params", {})
        if not intent:
            continue
        print(f"Action: {intent}, params={params}")
        dispatch(intent, text=text, params=params)

    print("Done.\n")


def main():
    print("[Wake] Loading hey_jarvis model (first run downloads ~2 MB)...")
    oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    print("[Wake] Model ready.")

    pa = pyaudio.PyAudio()
    audio_stream = pa.open(
        rate=RATE,
        channels=CHANNELS,
        format=FORMAT,
        input=True,
        frames_per_buffer=CHUNK,
    )

    print("Voice system ready.")
    print("Say the wake word: 'Hey Jarvis'")

    try:
        while True:
            audio_bytes = audio_stream.read(CHUNK, exception_on_overflow=False)
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)

            oww.predict(audio_array)

            for model_name, scores in oww.prediction_buffer.items():
                if list(scores)[-1] >= THRESHOLD:
                    print("Wake word detected.")
                    oww.prediction_buffer[model_name].clear()
                    play_ding()
                    handle_command(audio_stream, pa)
                    break

    except KeyboardInterrupt:
        print("\nShutting down voice engine.")
    finally:
        audio_stream.stop_stream()
        audio_stream.close()
        pa.terminate()


if __name__ == "__main__":
    main()
