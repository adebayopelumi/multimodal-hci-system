# engine/dispatcher/mac_ui.py
"""
Generic macOS app automation, so voice commands work in (almost) any app:
bring an app to the front, press its keyboard shortcuts, type text, click
its menu bar items, or search inside it. Plus small helpers for scriptable
apps (Notes, Reminders, Mail, Finder, Shortcuts).

Keystrokes and menu clicks go through System Events, which needs the
Accessibility permission (System Settings > Privacy & Security >
Accessibility) for the app running the assistant.
"""

from __future__ import annotations

import os
import subprocess
import time
import urllib.parse

# Search shortcut per app; anything not listed uses Cmd+F.
SEARCH_SHORTCUTS = {
    "safari": "cmd+l",
    "google chrome": "cmd+l",
    "brave browser": "cmd+l",
    "microsoft edge": "cmd+l",
    "firefox": "cmd+l",
    "arc": "cmd+l",
    "slack": "cmd+k",
    "discord": "cmd+k",
    "notion": "cmd+p",
    "visual studio code": "cmd+p",
    "code": "cmd+p",
    "cursor": "cmd+p",
    "obsidian": "cmd+o",
    "notes": "cmd+option+f",
    "mail": "cmd+option+f",
    "finder": "cmd+f",
    "whatsapp": "cmd+f",
    "telegram": "cmd+f",
    "messages": "cmd+f",
    "music": "cmd+f",
    "spotify": "cmd+k",
    "system settings": "cmd+f",
    "app store": "cmd+f",
}

KEY_CODES = {
    "return": 36, "enter": 76, "tab": 48, "space": 49, "delete": 51, "backspace": 51,
    "forwarddelete": 117, "escape": 53, "esc": 53,
    "left": 123, "right": 124, "down": 125, "up": 126,
    "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
    "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
}
NAMED_CHARS = {"plus": "+", "minus": "-", "comma": ",", "period": ".", "slash": "/",
               "backtick": "`", "equals": "=", "semicolon": ";"}
MODIFIERS = {
    "cmd": "command down", "command": "command down",
    "shift": "shift down",
    "option": "option down", "opt": "option down", "alt": "option down",
    "ctrl": "control down", "control": "control down",
}

FOLDERS = {
    "home": "~", "desktop": "~/Desktop", "documents": "~/Documents", "downloads": "~/Downloads",
    "pictures": "~/Pictures", "photos": "~/Pictures", "music": "~/Music", "movies": "~/Movies",
    "videos": "~/Movies", "applications": "/Applications",
}


def _q(s: str) -> str:
    """AppleScript string literal."""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _osa(script: str) -> subprocess.CompletedProcess:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
    if r.returncode != 0:
        err = r.stderr.strip()
        print(f"[MacUI] AppleScript error: {err}", flush=True)
        if "assistive access" in err or "-1719" in err or "-25211" in err:
            print("[MacUI] Allow the assistant in System Settings > Privacy & Security > Accessibility.", flush=True)
    return r


def app_is_running(app: str) -> bool:
    r = subprocess.run(["osascript", "-e", f"return application {_q(app)} is running"],
                       capture_output=True, text=True, check=False)
    return r.stdout.strip() == "true"


def frontmost_process() -> str:
    r = subprocess.run(
        ["osascript", "-e", 'tell application "System Events" to get name of first process whose frontmost is true'],
        capture_output=True, text=True, check=False,
    )
    return r.stdout.strip()


def focus_app(app: str, timeout: float = 6.0) -> bool:
    """Launch/activate an app and wait until it's in front and ready for keystrokes."""
    was_running = app_is_running(app)
    subprocess.run(["open", "-a", app], check=False)
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = subprocess.run(["osascript", "-e", f"return frontmost of application {_q(app)}"],
                           capture_output=True, text=True, check=False)
        if r.stdout.strip() == "true":
            # A freshly launched app needs a moment to open its window.
            time.sleep(0.35 if was_running else 1.5)
            return True
        time.sleep(0.15)
    print(f"[MacUI] {app} didn't come to the front in time.", flush=True)
    return False


def press_keys(keys) -> bool:
    """keys: "cmd+shift+n", "return", or a list of combos pressed in order."""
    if isinstance(keys, (list, tuple)):
        ok = True
        for k in keys:
            ok = press_keys(k) and ok
            time.sleep(0.15)
        return ok

    parts = [p for p in str(keys).lower().replace(" ", "").split("+") if p]
    if not parts:
        return False
    *mods, key = parts
    using = [MODIFIERS[m] for m in mods if m in MODIFIERS]
    using_clause = f" using {{{', '.join(using)}}}" if using else ""
    key = NAMED_CHARS.get(key, key)

    if key in KEY_CODES:
        script = f'tell application "System Events" to key code {KEY_CODES[key]}{using_clause}'
    elif len(key) == 1:
        script = f'tell application "System Events" to keystroke {_q(key)}{using_clause}'
    else:
        print(f"[MacUI] Unknown key: {keys!r}", flush=True)
        return False
    return _osa(script).returncode == 0


def type_text(text: str) -> bool:
    """Type into the focused field. Non-ASCII text is pasted via the clipboard."""
    if not text:
        return True
    if text.isascii():
        return _osa(f'tell application "System Events" to keystroke {_q(text)}').returncode == 0

    old = subprocess.run(["pbpaste"], capture_output=True, text=True, check=False).stdout
    subprocess.run(["pbcopy"], input=text, text=True, check=False)
    ok = press_keys("cmd+v")
    time.sleep(0.3)
    subprocess.run(["pbcopy"], input=old, text=True, check=False)
    return ok


def click_menu(menu: str, item: str, app: str | None = None) -> bool:
    """Click a menu bar item, e.g. click_menu("File", "New Private Window", "Safari")."""
    if app:
        focus_app(app)
    proc = frontmost_process()
    if not proc:
        return False
    script = (
        f'tell application "System Events" to tell process {_q(proc)} to '
        f"click menu item {_q(item)} of menu {_q(menu)} of menu bar 1"
    )
    return _osa(script).returncode == 0


def app_search(app: str, query: str, shortcut: str | None = None, submit: bool = True) -> bool:
    """Search inside an app: focus it, press its search shortcut, type, and (optionally) Return."""
    if not focus_app(app):
        return False
    combo = shortcut or SEARCH_SHORTCUTS.get(app.strip().lower(), "cmd+f")
    press_keys(combo)
    time.sleep(0.4)
    press_keys("cmd+a")  # replace anything already in the search box
    type_text(query)
    if submit:
        time.sleep(0.6)  # let results appear before choosing the first one
        press_keys("return")
    return True


def music_play(query: str) -> bool:
    """
    Play from the Apple Music library if something matches; otherwise open the
    Apple Music catalog search for it. Returns True if playback started.
    """
    script = (
        'tell application "Music"\n'
        f"  set q to {_q(query)}\n"
        "  set hits to (every track of library playlist 1 whose name contains q or artist contains q or album contains q)\n"
        "  if (count of hits) > 0 then\n"
        "    play item 1 of hits\n"
        '    return "playing"\n'
        "  end if\n"
        "end tell\n"
        'return "none"'
    )
    r = _osa(script)
    if r.stdout.strip() == "playing":
        return True
    subprocess.run(["open", "music://music.apple.com/search?term=" + urllib.parse.quote(query)], check=False)
    return False


def notes_create(body: str, title: str | None = None) -> bool:
    title = title or (body.split(".")[0][:60] if body else "New note")
    html = f"<h1>{title}</h1><div>{body}</div>"
    script = (
        'tell application "Notes"\n'
        f"  set n to make new note with properties {{body:{_q(html)}}}\n"
        "  activate\n"
        "  try\n    show n\n  end try\n"
        "end tell"
    )
    return _osa(script).returncode == 0


def reminder_create(text: str) -> bool:
    script = f'tell application "Reminders" to make new reminder with properties {{name:{_q(text)}}}'
    return _osa(script).returncode == 0


def email_compose(to: str = "", subject: str = "", body: str = ""):
    """Opens a draft in the default mail app. It is not sent."""
    query = urllib.parse.urlencode({"subject": subject, "body": body}, quote_via=urllib.parse.quote)
    subprocess.run(["open", f"mailto:{urllib.parse.quote(to or '', safe='@,')}?{query}"], check=False)


def open_folder(path: str):
    path = FOLDERS.get((path or "").strip().lower().strip("~/ "), path or "~")
    subprocess.run(["open", os.path.expanduser(path)], check=False)


def run_shortcut(name: str) -> bool:
    r = subprocess.run(["shortcuts", "run", name], capture_output=True, text=True, check=False)
    if r.returncode != 0:
        print(f"[MacUI] Shortcut {name!r} failed: {r.stderr.strip()}", flush=True)
    return r.returncode == 0
