import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
import subprocess


#  helpers 
def notify(title: str, message: str):
    # macOS notification
    script = f'display notification "{message}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], check=False)

def play_alarm_sound():
    # Built-in macOS sound (portable)
    subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"])

@dataclass
class AlarmJob:
    when: datetime
    label: str = "Alarm"

class Scheduler:
    def __init__(self, speak_fn):
        self.speak = speak_fn
        self._lock = threading.Lock()
        self._alarms: list[AlarmJob] = []
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def set_timer(self, seconds: int, label: str = "Timer"):
        def _timer_worker():
            time.sleep(max(0, seconds))
            play_alarm_sound()
            notify(label, "Time is up.")
            self.speak(f"{label} done.")

        threading.Thread(target=_timer_worker, daemon=True).start()

    def set_alarm_for_datetime(self, when: datetime, label: str = "Alarm"):
        with self._lock:
            self._alarms.append(AlarmJob(when=when, label=label))

    def _loop(self):
        while self._running:
            now = datetime.now()
            fired: list[AlarmJob] = []
            with self._lock:
                remaining = []
                for a in self._alarms:
                    if a.when <= now:
                        fired.append(a)
                    else:
                        remaining.append(a)
                self._alarms = remaining

            for a in fired:
                play_alarm_sound()
                notify(a.label, f"Alarm for {a.when.strftime('%I:%M %p').lstrip('0')}")
                self.speak(f"{a.label}. It's {a.when.strftime('%I:%M %p').lstrip('0')}.")

            time.sleep(0.25)