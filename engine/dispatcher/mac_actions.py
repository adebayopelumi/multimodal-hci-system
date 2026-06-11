# engine/dispatcher/mac_actions.py

from __future__ import annotations

import os
import re
import subprocess
import datetime
import webbrowser
import difflib
import urllib.parse
from engine.voice.history import log_search
from typing import Dict, Any
from datetime import datetime
from engine.context import get_context_app
from engine.dispatcher.scheduler import Scheduler


APPS_CACHE: list[str] | None = None

WIFI_SERVICE = "en0"
DEFAULT_VOICE = "Samantha"  
DEFAULT_RATE = "175"       
BROWSERS = {"Google Chrome", "Safari", "Brave Browser", "Arc", "Microsoft Edge", "Firefox"}
APP_ALIASES = {
    "WPS Office": "wpsoffice",
    "WPS Writer": "wpsoffice",
    "WPS Presentation": "wpsoffice",
    "WPS Spreadsheets": "wpsoffice",
}
WPS_APPS = ("wpsoffice",)  

SCHED = None

def init_scheduler():
    global SCHED
    if SCHED is None:
        SCHED = Scheduler(speak_fn=speak)
        SCHED.start()


def run_osascript(script: str):
    subprocess.run(["osascript", "-e", script], check=False)


def say(text: str):
    subprocess.run(["say", text], check=False)


def get_frontmost_app() -> str:
    script = (
        'tell application "System Events" to get name of '
        'first process whose frontmost is true'
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


#  App discovery & fuzzy matching

def build_apps_cache() -> list[str]:
    candidates: list[str] = []
    app_dirs = [
        "/Applications",
        "/System/Applications",
        os.path.join(os.path.expanduser("~"), "Applications"),
    ]
    for folder in app_dirs:
        if os.path.isdir(folder):
            for entry in os.listdir(folder):
                if entry.endswith(".app"):
                    candidates.append(entry[:-4])
    return candidates


def get_apps_cache() -> list[str]:
    global APPS_CACHE
    if APPS_CACHE is None:
        APPS_CACHE = build_apps_cache()
        print(f"[Dispatcher] Cached {len(APPS_CACHE)} applications.")
    return APPS_CACHE


def normalize_app_name(name: str) -> str:
    return name.strip().lower()


def find_best_matching_app(app_name: str) -> str | None:
    candidates = get_apps_cache()
    if not candidates:
        return None

    target = normalize_app_name(app_name)
    best = None
    best_score = 0

    for c in candidates:
        score = difflib.SequenceMatcher(
            None, target, normalize_app_name(c)
        ).ratio()
        if score > best_score:
            best_score = score
            best = c

    if best_score < 0.45:
        return None
    return best


def open_app_by_name(spoken_name: str):
    if not spoken_name:
        say("I didn't catch which app to open.")
        return
    print(f"[Dispatcher] Looking for app like: {spoken_name!r}")
    best = find_best_matching_app(spoken_name)
    if best:
        print(f"[Dispatcher] Opening app: {best}")
        run_osascript(f'tell application "{best}" to activate')
    else:
        print(f"[Dispatcher] No matching app found for: {spoken_name!r}")
        say(f"I couldn't find the app {spoken_name}.")


def close_app_by_name(spoken_name: str):
    if not spoken_name:
        say("I didn't catch which app to close.")
        return
    print(f"[Dispatcher] Trying to close app like: {spoken_name!r}")
    best = find_best_matching_app(spoken_name)
    if best:
        print(f"[Dispatcher] Closing app: {best}")
        run_osascript(f'tell application "{best}" to quit')
    else:
        print(f"[Dispatcher] No matching app found for: {spoken_name!r}")
        say(f"I couldn't find the app {spoken_name}.")


#  Search helpers

def extract_search_query(text: str) -> str | None:
    if not text:
        return None
    lower = text.lower()
    if "search for " in lower:
        return text[lower.index("search for ") + len("search for "):].strip()
    if "search " in lower:
        return text[lower.index("search ") + len("search "):].strip()
    return text.strip()


def perform_app_search(app_name: str | None, query: str):
    if not query:
        webbrowser.open("https://www.google.com", new=2)
        return

    app_norm = normalize_app_name(app_name) if app_name else ""

    if "youtube" in app_norm:
        url = (
            "https://www.youtube.com/results?search_query="
            + urllib.parse.quote(query)
        )
        webbrowser.open(url, new=2)
        return

    # default: browser / google
    url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
    webbrowser.open(url, new=2)


#  Battery / timers / alarms / toggles

def get_battery_percentage() -> int | None:
    try:
        out = subprocess.check_output(
            ["pmset", "-g", "batt"], text=True
        )
        m = re.search(r"(\d+)%", out)
        if m:
            return int(m.group(1))
    except Exception as e:
        print("[Dispatcher] Battery read error:", e)
    return None

def page_down():
    # Page Down key
    subprocess.run([
        "osascript",
        "-e",
        'tell application "System Events" to key code 121'
    ])


def page_up():
    # Page Up key
    subprocess.run([
        "osascript",
        "-e",
        'tell application "System Events" to key code 116'
    ])

def human_time_str(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()

    hour = dt.hour
    minute = dt.minute

    ampm = "AM" if hour < 12 else "PM"
    hour12 = hour % 12
    if hour12 == 0:
        hour12 = 12

    # "1:05 PM" not "1:5 PM"
    return f"{hour12}:{minute:02d} {ampm}"


def human_date_str(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    return dt.strftime("%A, %B %d, %Y")

def speak(text: str, voice: str = DEFAULT_VOICE, rate: str = DEFAULT_RATE):
    # -v voice, -r rate
    subprocess.Popen(["say", "-v", voice, "-r", rate, text])

def time_as_words(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    t = human_time_str(dt)
    return f"It's {t}."

def date_as_words(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    return f"Today is {human_date_str(dt)}."

def get_active_app_for_actions() -> str:
    """
    Prefer Electron-provided context app.
    Fallback to true macOS frontmost app if context is not set.
    """
    return get_context_app() or get_frontmost_app()

def focus_app(app: str):
    run_osascript(f'tell application "{app}" to activate')
    run_osascript('delay 0.05')

def resolve_app_name(app: str | None) -> str | None:
    if not app:
        return None
    return APP_ALIASES.get(app, app)

def set_wifi(on: bool):
    subprocess.run(
        ["networksetup", "-setairportpower", WIFI_SERVICE, "on" if on else "off"],
        check=False
    )

def set_bluetooth(on: bool):
    subprocess.run(["blueutil", "-p", "1" if on else "0"], check=False)

def get_bluetooth_state() -> bool | None:
    try:
        out = subprocess.check_output(["blueutil", "-p"]).decode().strip()
        return out == "1"
    except Exception:
        return None


# MERGED IN: gesture_mac_actions.py 

_BACKEND = None  # "quartz" | "pyautogui" | "cliclick" | None

def _detect_backend() -> str | None:
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND

    # Quartz (PyObjC)
    try:
        import Quartz  # type: ignore
        _BACKEND = "quartz"
        return _BACKEND
    except Exception:
        pass

    # pyautogui
    try:
        import pyautogui  # type: ignore
        _BACKEND = "pyautogui"
        return _BACKEND
    except Exception:
        pass

    # cliclick
    try:
        subprocess.run(["which", "cliclick"], capture_output=True, text=True, check=False)
        out = subprocess.run(["which", "cliclick"], capture_output=True, text=True, check=False).stdout.strip()
        if out:
            _BACKEND = "cliclick"
            return _BACKEND
    except Exception:
        pass

    _BACKEND = None
    return None


def _run_osascript(script: str):
    subprocess.run(["osascript", "-e", script], check=False)


#  Quartz helpers 

def _quartz_move(x: int, y: int):
    import Quartz  # type: ignore
    ev = Quartz.CGEventCreateMouseEvent(
        None, Quartz.kCGEventMouseMoved, (x, y), Quartz.kCGMouseButtonLeft
    )
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


def _quartz_click(button: str = "left"):
    import Quartz  # type: ignore
    loc = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
    if button == "right":
        down = Quartz.kCGEventRightMouseDown
        up = Quartz.kCGEventRightMouseUp
        btn = Quartz.kCGMouseButtonRight
    else:
        down = Quartz.kCGEventLeftMouseDown
        up = Quartz.kCGEventLeftMouseUp
        btn = Quartz.kCGMouseButtonLeft

    ev1 = Quartz.CGEventCreateMouseEvent(None, down, loc, btn)
    ev2 = Quartz.CGEventCreateMouseEvent(None, up, loc, btn)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev1)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev2)


def _quartz_mouse_down(button: str = "left"):
    import Quartz  # type: ignore
    loc = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
    if button == "right":
        t = Quartz.kCGEventRightMouseDown
        btn = Quartz.kCGMouseButtonRight
    else:
        t = Quartz.kCGEventLeftMouseDown
        btn = Quartz.kCGMouseButtonLeft
    ev = Quartz.CGEventCreateMouseEvent(None, t, loc, btn)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


def _quartz_mouse_up(button: str = "left"):
    import Quartz  # type: ignore
    loc = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
    if button == "right":
        t = Quartz.kCGEventRightMouseUp
        btn = Quartz.kCGMouseButtonRight
    else:
        t = Quartz.kCGEventLeftMouseUp
        btn = Quartz.kCGMouseButtonLeft
    ev = Quartz.CGEventCreateMouseEvent(None, t, loc, btn)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


#  pyautogui helpers 

def _py_move(x: int, y: int):
    import pyautogui  # type: ignore
    pyautogui.moveTo(x, y)


def _py_click(button: str = "left"):
    import pyautogui  # type: ignore
    pyautogui.click(button=button)


def _py_down(button: str = "left"):
    import pyautogui  # type: ignore
    pyautogui.mouseDown(button=button)


def _py_up(button: str = "left"):
    import pyautogui  # type: ignore
    pyautogui.mouseUp(button=button)


#  cliclick helpers 

def _cliclick(args: list[str]):
    subprocess.run(["cliclick"] + args, check=False)


def _cliclick_click(button: str = "left"):
    if button == "right":
        _cliclick(["rc"])
    else:
        _cliclick(["c"])


def _cliclick_move(x: int, y: int):
    _cliclick([f"m:{x},{y}"])


def _cliclick_down(button: str = "left"):
    # cliclick uses "dd" (down) and "du" (up) for left; right-down is "rd"; right-up is "ru"
    if button == "right":
        _cliclick(["rd"])
    else:
        _cliclick(["dd"])


def _cliclick_up(button: str = "left"):
    if button == "right":
        _cliclick(["ru"])
    else:
        _cliclick(["du"])



#  Main dispatcher

def dispatch(intent: str, text: str | None = None, params: Dict[str, Any] | None = None):
    if params is None:
        params = {}
    print(f"[Dispatcher] Received intent: {intent}, params={params}")

    init_scheduler()

    # ADDED: Mouse intents (from gesture_mac_actions.py)

    if intent == "mouse_left_click":
        backend = _detect_backend()
        if backend == "quartz":
            _quartz_click("left")
        elif backend == "pyautogui":
            _py_click("left")
        elif backend == "cliclick":
            _cliclick_click("left")
        else:
            print("[Dispatcher] No mouse backend available for left click.")
        return

    elif intent == "mouse_right_click":
        backend = _detect_backend()
        if backend == "quartz":
            _quartz_click("right")
        elif backend == "pyautogui":
            _py_click("right")
        elif backend == "cliclick":
            _cliclick_click("right")
        else:
            print("[Dispatcher] No mouse backend available for right click.")
        return

    elif intent == "mouse_down":
        backend = _detect_backend()
        button = params.get("button", "left")
        if backend == "quartz":
            _quartz_mouse_down(button)
        elif backend == "pyautogui":
            _py_down(button)
        elif backend == "cliclick":
            _cliclick_down(button)
        else:
            print("[Dispatcher] No mouse backend available for mouse_down.")
        return

    elif intent == "mouse_up":
        backend = _detect_backend()
        button = params.get("button", "left")
        if backend == "quartz":
            _quartz_mouse_up(button)
        elif backend == "pyautogui":
            _py_up(button)
        elif backend == "cliclick":
            _cliclick_up(button)
        else:
            print("[Dispatcher] No mouse backend available for mouse_up.")
        return

    elif intent == "mouse_move":
        backend = _detect_backend()
        x = params.get("x")
        y = params.get("y")
        if x is None or y is None:
            print("[Dispatcher] mouse_move missing x/y.")
            return

        x = int(x); y = int(y)
        if backend == "quartz":
            _quartz_move(x, y)
        elif backend == "pyautogui":
            _py_move(x, y)
        elif backend == "cliclick":
            _cliclick_move(x, y)
        else:
            print("[Dispatcher] No mouse backend available for mouse_move.")
        return

    elif intent == "gesture_scroll_down":
        _run_osascript('tell application "System Events" to key code 125')
        return

    elif intent == "gesture_scroll_up":
        _run_osascript('tell application "System Events" to key code 126')
        return

    # EVERYTHING BELOW IS YOUR ORIGINAL mac_actions.py (unchanged)

    #  VOLUME
    if intent == "volume_up":
        script = """
        set vs to get volume settings
        set v to output volume of vs
        set newV to v + 25
        if newV > 100 then set newV to 100
        set volume output volume newV without output muted
        """
        run_osascript(script)

    elif intent == "volume_down":
        script = """
        set vs to get volume settings
        set v to output volume of vs
        set newV to v - 25
        if newV < 0 then set newV to 0
        set volume output volume newV without output muted
        """
        run_osascript(script)

    elif intent == "mute_volume":
        run_osascript("set volume with output muted")

    elif intent == "unmute_volume":
        run_osascript("set volume without output muted")

    #  BATTERY
    elif intent == "query_battery":
        pct = get_battery_percentage()
        if pct is None:
            say("Sorry, I couldn't read the battery level.")
        else:
            say(f"Your battery is at {pct} percent.")

    #  TABS
    elif intent == "next_tab":
        run_osascript(
            'tell application "System Events" to key code 124 using {command down, option down}'
        )
    elif intent == "previous_tab":
        run_osascript(
            'tell application "System Events" to key code 123 using {command down, option down}'
        )

    elif intent == "new_tab":
        app = get_frontmost_app()
        if app in (
            "Google Chrome",
            "Safari",
            "Microsoft Edge",
            "Opera",
            "Brave Browser",
        ):
            run_osascript(
                'tell application "System Events" to keystroke "t" using {command down}'
            )
        else:
            say("You need to be in a browser to open a new tab.")

    elif intent == "close_tab":
        app = get_frontmost_app()
        if app in (
            "Google Chrome",
            "Safari",
            "Microsoft Edge",
            "Opera",
            "Brave Browser",
        ):
            run_osascript(
                'tell application "System Events" to keystroke "w" using {command down}'
            )
        else:
            say("You need to be in a browser to close a tab.")

    #  APP SWITCHING
    elif intent == "next_app":
        run_osascript(
            'tell application "System Events" to key code 48 using {command down}'
        )
    elif intent == "previous_app":
        run_osascript(
            'tell application "System Events" to key code 48 using {command down, shift down}'
        )

    #  WINDOW SWITCHING
    elif intent == "next_window":
        run_osascript(
            'tell application "System Events" to key code 50 using {command down}'
        )
    elif intent == "previous_window":
        run_osascript(
            'tell application "System Events" to key code 50 using {command down, shift down}'
        )

    #  CONTEXTUAL NEXT / PREVIOUS
    elif intent == "next_action":
        app_raw = get_context_app() or get_frontmost_app()
        app = resolve_app_name(app_raw)
        print(f"[Dispatcher] next_action in: {app_raw} -> {app}")
        if not app: return

        if app in ("Spotify", "Music"):
            run_osascript(f'tell application "{app}" to next track'); return
        if app == "wpsoffice":
            focus_app(app)
            run_osascript('tell application "System Events" to key code 124'); return

        if app in ("Preview", "Adobe Acrobat Reader", "Keynote", "Microsoft PowerPoint"):
            focus_app(app)
            run_osascript('tell application "System Events" to key code 124'); return

        if app in ("Photos", "Finder") or app in BROWSERS:
            focus_app(app)
            run_osascript('tell application "System Events" to key code 124'); return

        print("[Dispatcher] No matching context for next_action.")

    elif intent == "previous_action":
        app_raw = get_context_app() or get_frontmost_app()
        app = resolve_app_name(app_raw)
        print(f"[Dispatcher] previous_action in: {app_raw} -> {app}")
        if not app: return

        if app in ("Spotify", "Music"):
            run_osascript(f'tell application "{app}" to next track'); return
        if app == "wpsoffice":
            focus_app(app)
            run_osascript('tell application "System Events" to key code 123'); return

        if app in ("Preview", "Adobe Acrobat Reader", "Keynote", "Microsoft PowerPoint"):
            focus_app(app)
            run_osascript('tell application "System Events" to key code 123'); return

        if app in ("Photos", "Finder") or app in BROWSERS:
            focus_app(app)
            run_osascript('tell application "System Events" to key code 123'); return

        print("[Dispatcher] No matching context for previous_action.")

    #  BRIGHTNESS
    elif intent == "brightness_up":
        script = """
        tell application "System Events"
            key code 144
            key code 144
            key code 144
        end tell
        """
        run_osascript(script)

    elif intent == "brightness_down":
        script = """
        tell application "System Events"
            key code 145
            key code 145
            key code 145
        end tell
        """
        run_osascript(script)

    #  SCROLL
    elif intent == "scroll_down":
        page_down()

    elif intent == "scroll_up":
        page_up()

    #  MEDIA
    elif intent in ("pause_media", "play_media"):
        app = get_frontmost_app()
        print(f"[Dispatcher] play/pause in: {app}")
        if app in ("Music", "Spotify"):
            run_osascript(f'tell application "{app}" to playpause')
        else:
            run_osascript(
                'tell application "System Events" to key code 49'
            )

    #  SCREENSHOT
    elif intent == "capture_screen":
        run_osascript(
            'tell application "System Events" to key code 20 using {command down, shift down}'
        )

    #  LOCK SCREEN
    elif intent == "lock_screen":
        run_osascript(
            'tell application "System Events" to keystroke "q" using {control down, command down}'
        )

    #  TIMER / ALARM
    elif intent == "set_timer":
        # params should include: seconds (int) OR minutes (int)
        seconds = int(params.get("seconds") or 0)
        minutes = int(params.get("minutes") or 0)
        total = seconds + minutes * 60
        if total <= 0:
            say("How long should I set the timer for?")
            return
        SCHED.set_timer(total, label="Timer")
        say(f"Timer set for {total//60} minutes." if total >= 60 else f"Timer set for {total} seconds.")

    elif intent == "set_alarm":
        # params should include hour, minute, ampm (AM/PM)
        from datetime import datetime, timedelta
        hour = int(params.get("hour"))
        minute = int(params.get("minute", 0))
        ampm = (params.get("ampm") or "").upper()

        # convert to 24h
        if ampm == "PM" and hour != 12:
            hour += 12
        if ampm == "AM" and hour == 12:
            hour = 0

        now = datetime.now()
        when = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if when <= now:
            when += timedelta(days=1)

        SCHED.set_alarm_for_datetime(when, label="Alarm")
        say(f"Alarm set for {when.strftime('%I:%M %p').lstrip('0')}.")

    #  BLUETOOTH
    elif intent == "bluetooth_on":
        set_bluetooth(True)

    elif intent == "bluetooth_off":
        set_bluetooth(False)

    #  WIFI
    elif intent == "wifi_on":
        set_wifi(True)

    elif intent == "wifi_off":
        set_wifi(False)

    #  GENERIC OPEN / CLOSE APP
    elif intent == "open_app_generic":
        app_name = params.get("app_name")
        if not app_name and text:
            app_name = text
        open_app_by_name(app_name)

    elif intent == "close_app_generic":
        app_name = params.get("app_name")
        if app_name:
            close_app_by_name(app_name)
        else:
            front = get_frontmost_app()
            print(f"[Dispatcher] Closing frontmost app: {front!r}")
            if front:
                close_app_by_name(front)
            else:
                say("I couldn't determine which app to close.")

    #  TIME / DATE / WEATHER
    elif intent == "what_time":
        speak(time_as_words())

    elif intent == "what_date":
        speak(date_as_words())

    elif intent == "what_weather":
        webbrowser.open("https://www.google.com/search?q=weather today", new=2)

    #  GENERIC SEARCH
    elif intent in ("search", "search_google", "search_youtube"):
        query = params.get("query") if params else None
        app_name = params.get("app_name") if params else None

        # fallback extraction from raw text
        if not query and text:
            query = extract_search_query(text)

        if not query:
            # No query → open homepage
            if app_name == "youtube":
                webbrowser.open("https://youtube.com", new=2)
            else:
                webbrowser.open("https://google.com", new=2)
        else:
            perform_app_search(app_name, query)

    else:
        print(f"[Dispatcher] No handler for intent: {intent}")