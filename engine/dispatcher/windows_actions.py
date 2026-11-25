# engine/dispatcher/windows_actions.py
from __future__ import annotations

import os
import re
import time
import difflib
import threading
import subprocess
import webbrowser
import urllib.parse
from typing import Dict, Any
from datetime import datetime, timedelta

from engine.dispatcher import web_actions

# ------------------------------------------------------------
# Backends:
# 1) pywin32 (RECOMMENDED) -> real Windows cursor/click/scroll
# 2) pyautogui fallback
# ------------------------------------------------------------

try:
    import win32api  # type: ignore
    import win32con  # type: ignore
    _WIN32_OK = True
except Exception:
    win32api = None  # type: ignore
    win32con = None  # type: ignore
    _WIN32_OK = False

try:
    import pyautogui  # type: ignore
except Exception:
    pyautogui = None


# ---------------- Config / globals ----------------
APPS_CACHE: list[str] | None = None
APP_PATHS: dict[str, str] | None = None

WIFI_INTERFACE_NAME = "Wi-Fi"


# ---------------- Basics (keys / speech) ----------------
def _hotkey(*keys: str):
    if pyautogui:
        pyautogui.hotkey(*keys)
        return
    print("[Windows] pyautogui missing. Install: pip install pyautogui")


def _press(key: str):
    if pyautogui:
        pyautogui.press(key)
        return
    print("[Windows] pyautogui missing. Install: pip install pyautogui")


def speak(text: str):
    safe = text.replace('"', "'")
    ps = (
        'Add-Type -AssemblyName System.Speech;'
        '$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;'
        f'$s.Speak("{safe}");'
    )
    subprocess.Popen(["powershell", "-NoProfile", "-Command", ps])


def say(text: str):
    speak(text)


def human_time_str(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    return dt.strftime("%I:%M %p").lstrip("0")


def human_date_str(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    return dt.strftime("%A, %B %d, %Y")


def time_as_words(dt: datetime | None = None) -> str:
    return f"It's {human_time_str(dt)}."


def date_as_words(dt: datetime | None = None) -> str:
    return f"Today is {human_date_str(dt)}."


# ---------------- Wi-Fi / Bluetooth ----------------
def set_wifi(on: bool):
    state = "enabled" if on else "disabled"
    subprocess.run(
        ["netsh", "interface", "set", "interface", WIFI_INTERFACE_NAME, f"admin={state}"],
        check=False,
        capture_output=True,
        text=True,
    )
    speak(f"Wi-Fi turned {'on' if on else 'off'}.")


def set_bluetooth(on: bool):
    speak("Bluetooth toggle on Windows isn't universal yet.")
    print("[Windows] Bluetooth toggle not implemented universally.")


# ---------------- Timers / alarms (in-process) ----------------
def _timer_worker(seconds: int, label: str = "Timer"):
    time.sleep(max(0, seconds))
    speak(f"{label} finished.")


def _alarm_worker(when: datetime, label: str = "Alarm"):
    delay = (when - datetime.now()).total_seconds()
    time.sleep(max(0, delay))
    speak(f"{label}!")


def set_timer(seconds: int):
    threading.Thread(target=_timer_worker, args=(seconds, "Timer"), daemon=True).start()


def set_alarm_for_datetime(when: datetime):
    threading.Thread(target=_alarm_worker, args=(when, "Alarm"), daemon=True).start()


# ---------------- App discovery & fuzzy matching (Start Menu shortcuts) ----------------
def _start_menu_dirs() -> list[str]:
    dirs: list[str] = []
    programdata = os.environ.get("PROGRAMDATA")
    if programdata:
        dirs.append(os.path.join(programdata, "Microsoft", "Windows", "Start Menu", "Programs"))
    appdata = os.environ.get("APPDATA")
    if appdata:
        dirs.append(os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs"))
    return [d for d in dirs if d and os.path.isdir(d)]


def _collect_shortcuts() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for base in _start_menu_dirs():
        for root, _, files in os.walk(base):
            for fn in files:
                if not fn.lower().endswith(".lnk"):
                    continue
                name = fn[:-4].strip()
                path = os.path.join(root, fn)
                if name not in mapping:
                    mapping[name] = path
    return mapping


def build_apps_cache() -> list[str]:
    global APP_PATHS
    APP_PATHS = _collect_shortcuts()
    return sorted(APP_PATHS.keys())


def get_apps_cache() -> list[str]:
    global APPS_CACHE
    if APPS_CACHE is None:
        APPS_CACHE = build_apps_cache()
        print(f"[Windows Dispatcher] Cached {len(APPS_CACHE)} Start Menu apps.")
    return APPS_CACHE


def normalize_app_name(name: str) -> str:
    return name.strip().lower()


def find_best_matching_app(app_name: str) -> str | None:
    candidates = get_apps_cache()
    if not candidates:
        return None

    target = normalize_app_name(app_name)
    best = None
    best_score = 0.0

    for c in candidates:
        score = difflib.SequenceMatcher(None, target, normalize_app_name(c)).ratio()
        if score > best_score:
            best_score = score
            best = c

    if best_score < 0.45:
        return None
    return best


def open_app_by_name(spoken_name: str):
    global APP_PATHS
    if not spoken_name:
        say("I didn't catch which app to open.")
        return

    best = find_best_matching_app(spoken_name)

    # "YouTube", "Gmail", ... are websites unless a real app with that name exists.
    site = web_actions.site_for(spoken_name)
    if site and (
        not best
        or difflib.SequenceMatcher(None, spoken_name.lower(), best.lower()).ratio() < 0.85
    ):
        web_actions.open_url(site)
        return

    if best:
        if APP_PATHS is None:
            APP_PATHS = _collect_shortcuts()
        lnk = (APP_PATHS or {}).get(best)
        print(f"[Windows Dispatcher] Opening app: {best} ({lnk})")
        try:
            if lnk and os.path.exists(lnk):
                os.startfile(lnk)  # type: ignore[attr-defined]
                return
        except Exception as e:
            print("[Windows Dispatcher] os.startfile failed:", e)

        subprocess.Popen(["cmd", "/c", "start", "", best], shell=False)
        return

    print(f"[Windows Dispatcher] No matching app found for: {spoken_name!r}")
    say(f"I couldn't find the app {spoken_name}.")


def _kill_process_by_name_guess(app_display_name: str) -> bool:
    guess = re.sub(r"[^A-Za-z0-9]+", "", app_display_name).lower()
    if not guess:
        return False

    ps = f"Get-Process -Name {guess} -ErrorAction SilentlyContinue | Stop-Process -Force"
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False)
    subprocess.run(["taskkill", "/F", "/IM", f"{guess}.exe"], check=False, capture_output=True, text=True)
    return True


def close_app_by_name(spoken_name: str):
    if not spoken_name:
        say("I didn't catch which app to close.")
        return

    best = find_best_matching_app(spoken_name) or spoken_name
    print(f"[Windows Dispatcher] Trying to close app like: {spoken_name!r} -> {best!r}")

    ok = _kill_process_by_name_guess(best)
    if not ok:
        say(f"I couldn't close {spoken_name}.")


# ---------------- Search helpers ----------------
def extract_search_query(text: str) -> str | None:
    if not text:
        return None
    lower = text.lower()
    if "search for " in lower:
        return text[lower.index("search for ") + len("search for ") :].strip()
    if "search " in lower:
        return text[lower.index("search ") + len("search ") :].strip()
    return text.strip()


def perform_app_search(app_name: str | None, query: str):
    if not query:
        webbrowser.open("https://www.google.com", new=2)
        return

    app_norm = (app_name or "").lower()
    if "youtube" in app_norm:
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
        webbrowser.open(url, new=2)
        return

    url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
    webbrowser.open(url, new=2)


# ---------------- Extra helpers mirroring mac_actions ----------------
def get_battery_percentage() -> int | None:
    try:
        out = subprocess.check_output(
            ["wmic", "path", "Win32_Battery", "get", "EstimatedChargeRemaining"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        m = re.search(r"(\d+)", out)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return None


def page_down():
    _press("pagedown")


def page_up():
    _press("pageup")


# ============================================================
# Gesture dispatcher (pywin32 preferred)
# ============================================================

def _win_move(x: int, y: int):
    if not _WIN32_OK or win32api is None:
        return
    win32api.SetCursorPos((int(x), int(y)))


def _win_click(button: str = "left"):
    if not _WIN32_OK or win32api is None or win32con is None:
        return

    if button == "right":
        down = win32con.MOUSEEVENTF_RIGHTDOWN
        up = win32con.MOUSEEVENTF_RIGHTUP
    else:
        down = win32con.MOUSEEVENTF_LEFTDOWN
        up = win32con.MOUSEEVENTF_LEFTUP

    win32api.mouse_event(down, 0, 0, 0, 0)
    win32api.mouse_event(up, 0, 0, 0, 0)


def _win_down(button: str = "left"):
    if not _WIN32_OK or win32api is None or win32con is None:
        return
    ev = win32con.MOUSEEVENTF_RIGHTDOWN if button == "right" else win32con.MOUSEEVENTF_LEFTDOWN
    win32api.mouse_event(ev, 0, 0, 0, 0)


def _win_up(button: str = "left"):
    if not _WIN32_OK or win32api is None or win32con is None:
        return
    ev = win32con.MOUSEEVENTF_RIGHTUP if button == "right" else win32con.MOUSEEVENTF_LEFTUP
    win32api.mouse_event(ev, 0, 0, 0, 0)


def dispatch_gesture(intent: str, params: Dict[str, Any] | None = None):
    """
    Gesture-only dispatcher for Windows.
    Mirrors the gesture pieces you have in mac_actions.py:
      - mouse_move
      - mouse_left_click / mouse_right_click
      - mouse_down / mouse_up (optional)
      - gesture_scroll_up / gesture_scroll_down (safe)
    """
    if params is None:
        params = {}

    backend = "pywin32" if _WIN32_OK else ("pyautogui" if pyautogui else None)
    print(f"[GestureDispatcher-Win] intent={intent}, params={params}, backend={backend}")

    # ---------------- Mouse clicks ----------------
    if intent == "mouse_left_click":
        if _WIN32_OK:
            _win_click("left")
        elif pyautogui:
            pyautogui.click(button="left")
        else:
            print("[GestureDispatcher-Win] No backend available for left click.")
        return

    if intent == "mouse_right_click":
        if _WIN32_OK:
            _win_click("right")
        elif pyautogui:
            pyautogui.click(button="right")
        else:
            print("[GestureDispatcher-Win] No backend available for right click.")
        return

    # ---------------- Drag hold (optional) ----------------
    if intent == "mouse_down":
        button = str(params.get("button", "left"))
        if _WIN32_OK:
            _win_down(button)
        elif pyautogui:
            pyautogui.mouseDown(button=button)
        else:
            print("[GestureDispatcher-Win] No backend available for mouse_down.")
        return

    if intent == "mouse_up":
        button = str(params.get("button", "left"))
        if _WIN32_OK:
            _win_up(button)
        elif pyautogui:
            pyautogui.mouseUp(button=button)
        else:
            print("[GestureDispatcher-Win] No backend available for mouse_up.")
        return

    # ---------------- Mouse move ----------------
    if intent == "mouse_move":
        x = params.get("x")
        y = params.get("y")
        if x is None or y is None:
            print("[GestureDispatcher-Win] mouse_move missing x/y.")
            return

        x = int(x); y = int(y)
        if _WIN32_OK:
            _win_move(x, y)
        elif pyautogui:
            pyautogui.moveTo(x, y)
        else:
            print("[GestureDispatcher-Win] No backend available for mouse_move.")
        return

    # ---------------- Gesture scroll (safe) ----------------
    # Keep same "safe" behavior as your mac gesture scroll mapping:
    # use key presses instead of OS scroll injection.
    if intent == "gesture_scroll_down":
        _press("down")
        return

    if intent == "gesture_scroll_up":
        _press("up")
        return

    print(f"[GestureDispatcher-Win] No handler for intent: {intent}")


# ============================================================
# Main voice/action dispatcher
# ============================================================

def dispatch(intent: str, text: str | None = None, params: Dict[str, Any] | None = None):
    if params is None:
        params = {}
    print(f"[Windows Dispatcher] Received intent: {intent}, params={params}")

    # VOLUME
    if intent == "volume_up":
        _press("volumeup"); return
    if intent == "volume_down":
        _press("volumedown"); return
    if intent == "mute_volume":
        _press("volumemute"); return
    if intent == "unmute_volume":
        _press("volumemute"); return  # toggles

    # BATTERY
    if intent == "query_battery":
        pct = get_battery_percentage()
        if pct is None:
            say("Sorry, I couldn't read the battery level.")
        else:
            say(f"Your battery is at {pct} percent.")
        return

    # TABS
    if intent == "next_tab":
        _hotkey("ctrl", "tab"); return
    if intent == "previous_tab":
        _hotkey("ctrl", "shift", "tab"); return
    if intent == "new_tab":
        _hotkey("ctrl", "t"); return
    if intent == "close_tab":
        _hotkey("ctrl", "w"); return

    # APP SWITCHING
    if intent == "next_app":
        _hotkey("alt", "tab"); return
    if intent == "previous_app":
        _hotkey("alt", "shift", "tab"); return

    # WINDOW SWITCHING
    if intent == "next_window":
        _hotkey("alt", "esc"); return
    if intent == "previous_window":
        _hotkey("alt", "shift", "esc"); return

    # CONTEXTUAL NEXT / PREVIOUS
    if intent == "next_action":
        _press("right"); return
    if intent == "previous_action":
        _press("left"); return

    # BRIGHTNESS
    if intent == "brightness_up":
        print("[Windows] brightness_up not universally supported via pyautogui/pywin32.")
        return
    if intent == "brightness_down":
        print("[Windows] brightness_down not universally supported via pyautogui/pywin32.")
        return

    # SCROLL
    if intent == "scroll_down":
        page_down(); return
    if intent == "scroll_up":
        page_up(); return

    # MEDIA
    if intent in ("pause_media", "play_media"):
        _press("playpause"); return

    # SCREENSHOT
    if intent == "capture_screen":
        _hotkey("win", "shift", "s"); return

    # LOCK SCREEN
    if intent == "lock_screen":
        _hotkey("win", "l"); return

    # TIMER / ALARM
    if intent == "set_timer":
        seconds = int(params.get("seconds") or 0)
        minutes = int(params.get("minutes") or 0)
        total = seconds + minutes * 60
        if total <= 0:
            say("How long should I set the timer for?")
            return
        set_timer(total)
        say(f"Timer set for {total//60} minutes." if total >= 60 else f"Timer set for {total} seconds.")
        return

    if intent == "set_alarm":
        hour = int(params.get("hour"))
        minute = int(params.get("minute", 0))
        ampm = (params.get("ampm") or "AM").upper()

        h24 = hour % 12
        if ampm == "PM":
            h24 += 12

        now = datetime.now()
        when = now.replace(hour=h24, minute=minute, second=0, microsecond=0)
        if when <= now:
            when += timedelta(days=1)

        set_alarm_for_datetime(when)
        say(f"Alarm set for {when.strftime('%I:%M %p').lstrip('0')}.")
        return

    # BLUETOOTH / WIFI
    if intent == "bluetooth_on":
        set_bluetooth(True); return
    if intent == "bluetooth_off":
        set_bluetooth(False); return
    if intent == "wifi_on":
        set_wifi(True); return
    if intent == "wifi_off":
        set_wifi(False); return

    # OPEN / CLOSE APP
    if intent == "open_app_generic":
        app_name = params.get("app_name") or text
        open_app_by_name(app_name or "")
        return

    if intent == "close_app_generic":
        app_name = params.get("app_name") or text
        close_app_by_name(app_name or "")
        return

    # TIME / DATE / WEATHER
    if intent == "what_time":
        speak(time_as_words()); return
    if intent == "what_date":
        speak(date_as_words()); return
    if intent == "what_weather":
        webbrowser.open("https://www.google.com/search?q=weather today", new=2); return

    # WEB / YOUTUBE / SPOTIFY / MAPS
    if intent == "open_website":
        web_actions.open_url(web_actions.normalize_url(params.get("url", ""))); return
    if intent == "web_search":
        query = params.get("query") or extract_search_query(text or "")
        if query:
            web_actions.web_search(query)
        return
    if intent == "maps_search":
        web_actions.maps_search(params.get("query") or "restaurants near me"); return
    if intent == "youtube_search":
        web_actions.youtube_search(params.get("query") or ""); return
    if intent == "youtube_play":
        query = params.get("query") or ""
        if query:
            web_actions.youtube_play(query, latest=bool(params.get("latest")))
        else:
            web_actions.open_url("https://www.youtube.com")
        return
    if intent in ("spotify_search", "spotify_play"):
        # Windows: open the Spotify search (playback control is macOS-only for now).
        query = params.get("query") or ""
        webbrowser.open("spotify:search:" + urllib.parse.quote(query) if query else "spotify:", new=2)
        return
    if intent in ("next_track", "previous_track"):
        _press("nexttrack" if intent == "next_track" else "prevtrack"); return

    # SEARCH
    if intent in ("search", "search_google", "search_youtube"):
        query = params.get("query") if params else None
        app_name = params.get("app_name") if params else None
        if not query and text:
            query = extract_search_query(text)

        if not query:
            if (app_name or "").lower() == "youtube":
                webbrowser.open("https://youtube.com", new=2)
            else:
                webbrowser.open("https://google.com", new=2)
        else:
            perform_app_search(app_name, query)
        return

    print(f"[Windows Dispatcher] No handler for intent: {intent}")