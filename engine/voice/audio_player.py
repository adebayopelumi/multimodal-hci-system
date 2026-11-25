# engine/voice/audio_player.py
"""
Tiny audio player that runs in its own process (started by tts.py).

The voice engine is busy in the background (wake-word model, YouTube
lookups, ...). Playing audio inside that process made speech choppy, because
the audio callback has to wait for Python's lock. Here nothing else runs, so
playback never waits.

Protocol on stdin, repeated:  b"<sample_rate> <num_samples>\\n" + int16 mono PCM
Replies on stdout: "ready" once at startup, then "done" (or "error ...") per clip.
The player exits when stdin closes (i.e. when the voice engine stops).
"""

import sys

import numpy as np

try:
    import sounddevice as sd
except Exception as e:  # no PortAudio -> tts.py falls back to another player
    print(f"error {e}", flush=True)
    sys.exit(1)


def main():
    print("ready", flush=True)
    inp = sys.stdin.buffer
    while True:
        header = inp.readline()
        if not header:
            break  # voice engine went away
        try:
            sample_rate, count = (int(x) for x in header.split())
        except ValueError:
            continue
        data = inp.read(count * 2)
        if len(data) < count * 2:
            break
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        try:
            sd.play(samples, sample_rate, latency="high")
            sd.wait()
            print("done", flush=True)
        except Exception as e:
            print(f"error {e}", flush=True)


if __name__ == "__main__":
    main()
