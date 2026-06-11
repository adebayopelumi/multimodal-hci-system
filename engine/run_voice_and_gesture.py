# engine/run_voice_and_gesture.py

import sys
import subprocess
import time
import signal
import os


def _spawn(module: str, extra_args=None, extra_env=None) -> subprocess.Popen:
    extra_args = extra_args or []
    env = dict(**os.environ)
    if extra_env:
        env.update(extra_env)

    return subprocess.Popen(
        [sys.executable, "-u", "-m", module, *extra_args],
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
        start_new_session=True,
        env=env,
    )


def _terminate(proc: subprocess.Popen | None, name: str, timeout: float = 3.0):
    if proc is None or proc.poll() is not None:
        return

    try:
        if sys.platform.startswith("win"):
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
    except Exception:
        pass

    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            return
        time.sleep(0.05)

    try:
        proc.kill()
    except Exception:
        pass


def main():
    voice_mod = "engine.voice.voice_main_wake"
    gest_mod = "engine.gesture.gesture_runtime"

    print("[Launcher] Starting voice + gesture...")

    # If you added HEADLESS handling in gesture_runtime.py, this will prevent cv2.imshow window
    voice_p = _spawn(voice_mod)
    gest_p = _spawn(gest_mod, extra_env={"HEADLESS": "1"})

    stopping = {"flag": False}

    def _on_signal(signum, _frame):
        if stopping["flag"]:
            return
        stopping["flag"] = True
        print(f"\n[Launcher] Signal {signum} received. Shutting down children...")
        _terminate(voice_p, "voice")
        _terminate(gest_p, "gesture")

    # Ensure Electron stop (SIGTERM) kills both children cleanly
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    try:
        while True:
            v = voice_p.poll() if voice_p else None
            g = gest_p.poll() if gest_p else None

            # If voice exits, keep gesture running
            if voice_p and v is not None:
                print(f"[Launcher] Voice exited (code={v}). Gesture will keep running.")
                voice_p = None

            # If gesture exits, keep voice running
            if gest_p and g is not None:
                print(f"[Launcher] Gesture exited (code={g}). Voice will keep running.")
                gest_p = None

            # If both are gone, we are done
            if voice_p is None and gest_p is None:
                print("[Launcher] Both processes exited. Done.")
                break

            time.sleep(0.2)

    except KeyboardInterrupt:
        print("\n[Launcher] Ctrl+C received. Shutting down...")

    finally:
        _terminate(voice_p, "voice")
        _terminate(gest_p, "gesture")
        print("[Launcher] Done.")


if __name__ == "__main__":
    main()