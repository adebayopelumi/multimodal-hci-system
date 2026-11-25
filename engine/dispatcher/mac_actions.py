# engine/dispatcher/mac_actions.py

from __future__ import annotations

import os
import re
import subprocess
import datetime
import webbrowser
import difflib
import urllib.parse
import time
from engine.voice.history import log_search
from engine.voice import tts
from engine.dispatcher import web_actions, mac_ui
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
    tts.speak(text)


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


def _app_match_score(app_name: str, candidate: str) -> float:
    return difflib.SequenceMatcher(
        None, normalize_app_name(app_name), normalize_app_name(candidate)
    ).ratio()


def open_app_by_name(spoken_name: str, wait: bool = False) -> str | None:
    """Open an app (or known website). Returns the matched app name, if any."""
    if not spoken_name:
        say("I didn't catch which app to open.")
        return
    print(f"[Dispatcher] Looking for app like: {spoken_name!r}")
    best = find_best_matching_app(spoken_name)

    # "YouTube", "Gmail", ... are websites unless a real app with that name exists.
    site = web_actions.site_for(spoken_name)
    if site and (not best or _app_match_score(spoken_name, best) < 0.85):
        web_actions.open_url(site)
        return None

    if best:
        print(f"[Dispatcher] Opening app: {best}")
        if wait:
            mac_ui.focus_app(best)  # launches and waits until it's ready for keystrokes
        else:
            # `open -a` launches/focuses without needing Automation permission.
            subprocess.run(["open", "-a", best], check=False)
        return best

    print(f"[Dispatcher] No matching app found for: {spoken_name!r}")
    say(f"I couldn't find the app {spoken_name}.")
    return None


def resolve_installed_app(spoken_name: str | None) -> str | None:
    """Map a spoken app name to an installed app name ("VS Code" -> "Visual Studio Code")."""
    if not spoken_name:
        return None
    return find_best_matching_app(spoken_name) or spoken_name


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
    # Natural Kokoro voice (falls back to macOS `say` inside tts if unavailable).
    tts.speak(text)


#  Spotify (desktop app via AppleScript)

SPOTIFY_RANDOM_URI = os.environ.get(
    "MHCI_SPOTIFY_RANDOM_URI", "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"  # Today's Top Hits
)
_spotify_hint_given = False


def _spotify_osascript(body: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["osascript", "-e", f'tell application "Spotify"\n{body}\nend tell'],
        capture_output=True, text=True, check=False,
    )


def _spotify_ready(timeout: float = 10.0) -> bool:
    """Launch Spotify if needed and wait until it accepts commands."""
    running = subprocess.run(["pgrep", "-x", "Spotify"], capture_output=True).returncode == 0
    if not running:
        subprocess.run(["open", "-a", "Spotify"], check=False)
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = _spotify_osascript("return player state as string")
        if r.returncode == 0 and r.stdout.strip():
            if not running:
                time.sleep(1.0)  # freshly launched: let it finish loading the player
            return True
        time.sleep(0.4)
    print("[Spotify] Spotify didn't become ready in time.")
    return False


def spotify_play_uri(uri: str, shuffle: bool | None = None) -> bool:
    if not _spotify_ready():
        return False
    body = ""
    if shuffle is not None:
        body += f"set shuffling to {'true' if shuffle else 'false'}\n"
    body += f'play track "{uri}"'
    r = _spotify_osascript(body)
    if r.returncode != 0:
        print(f"[Spotify] play failed: {r.stderr.strip()}")
        return False
    return True


def spotify_search(query: str):
    subprocess.run(["open", "spotify:search:" + urllib.parse.quote(query)], check=False)


def spotify_play(query: str | None, kind: str | None):
    global _spotify_hint_given
    kind = (kind or "").lower()

    if kind == "random" or not query:
        spotify_play_uri(SPOTIFY_RANDOM_URI, shuffle=True)
        return

    if web_actions.spotify_api_available():
        found = web_actions.spotify_find_uri(query, kind or "track")
        if found:
            uri, name = found
            print(f"[Spotify] Playing {name!r} ({uri})")
            spotify_play_uri(uri, shuffle=(kind in ("artist", "playlist", "album")) or None)
            return

    # Without Spotify API keys there's no way to look up the exact song, so show the search.
    spotify_search(query)
    if not _spotify_hint_given:
        _spotify_hint_given = True
        say(f"I opened {query} in Spotify search. Add a Spotify API key so I can press play for you.")

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
            run_osascript(f'tell application "{app}" to previous track'); return
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

    elif intent in ("next_track", "previous_track"):
        app = get_frontmost_app()
        if app not in ("Music", "Spotify"):
            app = "Spotify"
        verb = "next" if intent == "next_track" else "previous"
        run_osascript(f'tell application "{app}" to {verb} track')

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
        # wait=True when more actions follow, so e.g. keystrokes land in the new app
        open_app_by_name(app_name, wait=bool(params.get("_wait")))

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

    #  WEB / YOUTUBE / SPOTIFY / MAPS
    elif intent == "open_website":
        web_actions.open_url(web_actions.normalize_url(params.get("url", "")), params.get("browser"))

    elif intent == "web_search":
        query = params.get("query") or extract_search_query(text or "")
        if query:
            log_search(query, raw_text=text)
            web_actions.web_search(query, params.get("browser"))

    elif intent == "maps_search":
        web_actions.maps_search(params.get("query") or "restaurants near me")

    elif intent == "youtube_search":
        query = params.get("query") or ""
        if query:
            log_search(query, app_name="YouTube", raw_text=text)
            web_actions.youtube_search(query)
        else:
            web_actions.open_url("https://www.youtube.com")

    elif intent == "youtube_play":
        query = params.get("query") or ""
        if not query:
            web_actions.open_url("https://www.youtube.com")
        elif not web_actions.youtube_play(query, latest=bool(params.get("latest"))):
            say(f"I couldn't find that exact video, so here are the results for {query}.")

    elif intent == "spotify_search":
        query = params.get("query") or ""
        if query:
            spotify_search(query)
        else:
            subprocess.run(["open", "-a", "Spotify"], check=False)

    elif intent == "spotify_play":
        spotify_play(params.get("query"), params.get("kind"))

    elif intent == "music_play":
        query = params.get("query") or ""
        if not query:
            run_osascript('tell application "Music" to play')
        elif not mac_ui.music_play(query):
            say(f"{query} isn't in your library, so I opened it in Apple Music.")

    #  GENERIC APP AUTOMATION (works with most apps)
    elif intent == "app_search":
        app = resolve_installed_app(params.get("app_name")) or get_frontmost_app()
        query = params.get("query") or ""
        if app and normalize_app_name(app) == "spotify" and query:
            spotify_search(query)  # Spotify's URI search is more reliable than its UI
        elif app and query:
            submit = params.get("submit")
            mac_ui.app_search(app, query, shortcut=params.get("shortcut"),
                              submit=True if submit is None else bool(submit))

    elif intent == "press_keys":
        if params.get("app_name"):
            mac_ui.focus_app(resolve_installed_app(params["app_name"]))
        mac_ui.press_keys(params.get("keys") or "")

    elif intent == "type_text":
        if params.get("app_name"):
            mac_ui.focus_app(resolve_installed_app(params["app_name"]))
        mac_ui.type_text(str(params.get("text") or ""))

    elif intent == "click_menu":
        app = resolve_installed_app(params.get("app_name"))
        if not mac_ui.click_menu(params.get("menu", ""), params.get("item", ""), app):
            say(f"I couldn't find {params.get('item', 'that')} in the {params.get('menu', '')} menu.")

    elif intent == "wait":
        time.sleep(min(float(params.get("seconds") or 1), 10))

    elif intent == "notes_create":
        mac_ui.notes_create(params.get("body") or text or "", params.get("title"))

    elif intent == "reminder_create":
        mac_ui.reminder_create(params.get("text") or text or "")

    elif intent == "email_compose":
        mac_ui.email_compose(params.get("to", ""), params.get("subject", ""), params.get("body", ""))

    elif intent == "open_folder":
        mac_ui.open_folder(params.get("path") or "~")

    elif intent == "run_shortcut":
        if not mac_ui.run_shortcut(params.get("name", "")):
            say(f"I couldn't run the shortcut {params.get('name', '')}.")

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