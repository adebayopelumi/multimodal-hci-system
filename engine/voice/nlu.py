# engine/voice/nlu.py
"""
Turns what the user said into an ordered list of actions plus a short
spoken reply.

Two paths:
  1. Fast path: simple commands ("open Spotify", "volume up", "what time is
     it") are matched locally, so they run instantly with no network call.
  2. Planner: everything else goes to an OpenAI model that splits the
     sentence into every task it contains ("open YouTube, search MrBeast and
     play the newest video") and writes a short reply to speak.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPENAI_KEY_PATH = PROJECT_ROOT / "openai_key.txt"

# Override with MHCI_NLU_MODEL. gpt-5.4-mini planned every test command
# correctly with a ~1.0 s median, versus ~2.1 s for gpt-4.1 and ~1.4 s for
# gpt-4.1-mini / gpt-4o-mini (measured Nov 2026).
NLU_MODEL = os.environ.get("MHCI_NLU_MODEL", "gpt-5.4-mini")


def load_openai_key() -> str | None:
    """Load API key from env or openai_key.txt."""
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key.strip()
    if OPENAI_KEY_PATH.exists():
        return OPENAI_KEY_PATH.read_text(encoding="utf-8").strip()
    return None


OPENAI_API_KEY = load_openai_key()

if OpenAI is not None and OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
    LLM_ENABLED = True
    print(f"[NLU] Planner model: {NLU_MODEL}")
else:
    client = None
    LLM_ENABLED = False
    if OpenAI is None:
        print("[NLU] openai package not installed; only simple commands will work.")
    else:
        print("[NLU] No OPENAI_API_KEY found; only simple commands will work.")


# Intent whitelist – must match what the dispatchers can handle
INTENT_WHITELIST: List[str] = sorted({
    # volume / audio
    "volume_up", "volume_down", "mute_volume", "unmute_volume",
    # brightness / scroll
    "brightness_up", "brightness_down", "scroll_up", "scroll_down",
    # navigation
    "next_tab", "previous_tab", "new_tab", "close_tab",
    "next_app", "previous_app",
    "next_window", "previous_window",
    "next_action", "previous_action",
    # media
    "pause_media", "play_media", "next_track", "previous_track",
    # connectivity
    "bluetooth_on", "bluetooth_off", "wifi_on", "wifi_off",
    # timers / alarms
    "set_timer", "set_alarm",
    # system
    "capture_screen", "lock_screen",
    # apps and websites
    "open_app_generic", "close_app_generic", "open_website",
    # info
    "what_time", "what_date", "what_weather",
    # search / media services
    "web_search", "search", "search_google",
    "youtube_search", "youtube_play",
    "spotify_search", "spotify_play", "music_play",
    "maps_search",
    # generic app automation (any app)
    "app_search", "press_keys", "type_text", "click_menu", "wait",
    "notes_create", "reminder_create", "email_compose", "open_folder", "run_shortcut",
})


@dataclass
class Plan:
    actions: List[Dict[str, Any]] = field(default_factory=list)  # [{"intent", "params"}]
    say: str = ""
    source: str = "none"  # "fast", "llm" or "none"
    seconds: float = 0.0


#  1) Fast path

_PUNCT = re.compile(r"[^\w\s'&+-]")
_LEADING_FILLER = re.compile(
    r"^(?:(?:hey|ok|okay|yo)\s+)?(?:jarvis\s+)?"
    r"(?:(?:please|can you|could you|would you|will you)\s+)?"
)

# Anything that hints at more than one step or a search goes to the planner.
_COMPLEX = re.compile(
    r"\b(and|then|after|search|play|find|look up|near|for|on|in|to|with)\b|\d"
)

_EXACT: Dict[str, str] = {}
for _intent, _phrases in {
    "volume_up": ["volume up", "turn up the volume", "turn the volume up", "increase the volume", "louder"],
    "volume_down": ["volume down", "turn down the volume", "turn the volume down", "decrease the volume", "quieter"],
    "mute_volume": ["mute", "mute the volume", "mute volume", "mute the sound"],
    "unmute_volume": ["unmute", "unmute the volume", "unmute volume", "unmute the sound"],
    "pause_media": ["pause", "pause it", "pause the music", "pause music", "stop the music", "pause the video"],
    "play_media": ["resume", "resume the music", "resume music", "resume playing", "unpause"],
    "next_track": ["next song", "next track", "skip", "skip this song", "skip song", "skip track"],
    "previous_track": ["previous song", "previous track", "last song", "go back a song"],
    "what_time": ["what time is it", "what's the time", "whats the time", "what is the time", "tell me the time"],
    "what_date": ["what's the date", "whats the date", "what is the date", "what's today's date",
                  "what is today's date", "what day is it", "what day is it today"],
    "what_weather": ["what's the weather", "whats the weather", "what is the weather", "weather"],
    "capture_screen": ["take a screenshot", "screenshot", "take screenshot", "capture the screen"],
    "lock_screen": ["lock the screen", "lock screen", "lock my mac", "lock my computer"],
    "scroll_down": ["scroll down"],
    "scroll_up": ["scroll up"],
    "brightness_up": ["brightness up", "increase brightness", "increase the brightness", "make it brighter"],
    "brightness_down": ["brightness down", "decrease brightness", "decrease the brightness", "make it darker"],
    "new_tab": ["new tab", "open a new tab", "open new tab"],
    "close_tab": ["close tab", "close this tab", "close the tab"],
    "next_tab": ["next tab"],
    "previous_tab": ["previous tab", "last tab"],
    "close_app_generic": ["close this app", "close this", "close it", "quit this app", "quit this"],
}.items():
    for _p in _phrases:
        _EXACT[_p] = _intent

_OPEN = re.compile(r"^(?:open|launch)(?:\s+up)?\s+(?:the\s+|my\s+)?(?P<app>.{2,40}?)(?:\s+app(?:lication)?)?$")
_CLOSE = re.compile(r"^(?:close|quit|exit)\s+(?:the\s+|my\s+)?(?P<app>.{2,40}?)(?:\s+app(?:lication)?)?$")


def _normalize(text: str) -> str:
    t = _PUNCT.sub(" ", text.lower())
    t = re.sub(r"\s+", " ", t).strip()
    t = _LEADING_FILLER.sub("", t).strip()
    t = re.sub(r"\s+please$", "", t)
    return t


def _pretty_app(name: str) -> str:
    known = {"youtube": "YouTube", "whatsapp": "WhatsApp", "vs code": "VS Code", "chatgpt": "ChatGPT"}
    return known.get(name, " ".join(w if w.isupper() else w.capitalize() for w in name.split()))


def fast_path(text: str) -> Plan | None:
    t = _normalize(text)
    if not t:
        return None

    intent = _EXACT.get(t)
    if intent:
        return Plan(actions=[{"intent": intent, "params": {}}], source="fast")

    if _COMPLEX.search(t):
        return None

    m = _OPEN.match(t)
    if m:
        app = _pretty_app(m.group("app"))
        return Plan(
            actions=[{"intent": "open_app_generic", "params": {"app_name": app}}],
            say=f"Opening {app}.",
            source="fast",
        )

    m = _CLOSE.match(t)
    if m:
        app = _pretty_app(m.group("app"))
        return Plan(
            actions=[{"intent": "close_app_generic", "params": {"app_name": app}}],
            say=f"Closing {app}.",
            source="fast",
        )
    return None


#  2) LLM planner

SYSTEM_PROMPT = """You plan actions for a macOS voice assistant. Turn the user's spoken command into JSON:
{"actions": [{"intent": "<intent>", "params": {...}}], "say": "<short spoken reply>"}

Intents (params in braces):
- open_app_generic {app_name}: open a Mac app or a well-known website by name ("Spotify", "WhatsApp", "YouTube", "Gmail").
- close_app_generic {app_name}: omit app_name for "close this app".
- open_website {url, browser}
- web_search {query, answer, browser}: any question or "google X". answer: see the rules below.
- youtube_search {query}: only show results.
- youtube_play {query, latest}: play a video now (also "play the first/top video"). latest=true for the newest/most recent/latest upload; query is then the channel or creator.
- spotify_search {query}
- spotify_play {query, kind}: kind is "artist", "track", "album" or "playlist"; kind "random" (no query) for "play a random song" / "play some music". Only for Spotify (the default when no music app is named).
- music_play {query}: play a song/artist/album in Apple Music (the "Music" app).
- maps_search {query}: places, "near me", directions. e.g. {"query": "restaurants near me"}
- Any other app (use the app's real macOS shortcuts and menu names):
  - app_search {app_name, query, submit}: search inside an app (a WhatsApp/Telegram/Slack chat, a Finder file, a note, a song in Music). Opens the app itself. submit (default true) presses Return to open the first result.
  - press_keys {keys}: shortcut(s) in the front app: "cmd+n", "cmd+shift+n", "return", or a list ["cmd+t", "cmd+l"].
  - type_text {text}: type into the focused field.
  - click_menu {menu, item}: click a menu bar item of the front app, e.g. {"menu": "File", "item": "New Private Window"}.
  - wait {seconds}
  - notes_create {title, body}; reminder_create {text}; email_compose {to, subject, body}; open_folder {path} e.g. "~/Downloads"; run_shortcut {name}: run a Shortcuts-app shortcut.
- set_timer {minutes} or {seconds}
- set_alarm {hour, minute, ampm}
- No params: volume_up, volume_down, mute_volume, unmute_volume, brightness_up, brightness_down, scroll_up, scroll_down, play_media, pause_media, next_track, previous_track, new_tab, close_tab, next_tab, previous_tab, next_app, previous_app, next_window, previous_window, capture_screen, lock_screen, wifi_on, wifi_off, bluetooth_on, bluetooth_off, what_time, what_date, what_weather

Rules:
- Include every task in the sentence, in the order spoken.
- Use ONE action when it already covers several steps; never add open_app_generic before youtube_*, spotify_*, maps_search or web_search:
  "open YouTube and search for Mr Beast and play the most recent video" -> [{"intent":"youtube_play","params":{"query":"MrBeast","latest":true}}]
  "open Spotify and search for wizkid" -> [{"intent":"spotify_search","params":{"query":"Wizkid"}}]
  "open Spotify and play a random song" -> [{"intent":"spotify_play","params":{"kind":"random"}}]
  "search YouTube for jollof rice recipes and play the first video" -> [{"intent":"youtube_play","params":{"query":"jollof rice recipe","latest":false}}]
  "find the nearest restaurant close to me" -> [{"intent":"maps_search","params":{"query":"restaurants near me"}}]
  "open Safari and search for flights to Lagos" -> [{"intent":"web_search","params":{"query":"flights to Lagos","answer":"","browser":"Safari"}}]
  "open WhatsApp and search for Mum" -> [{"intent":"app_search","params":{"app_name":"WhatsApp","query":"Mum"}}]
  "message Tunde on WhatsApp saying I'm on my way" -> [{"intent":"app_search","params":{"app_name":"WhatsApp","query":"Tunde"}},{"intent":"type_text","params":{"text":"I'm on my way"}}]
  "open TextEdit and type hello world" -> [{"intent":"open_app_generic","params":{"app_name":"TextEdit"}},{"intent":"press_keys","params":{"keys":"cmd+n"}},{"intent":"type_text","params":{"text":"hello world"}}]
  "open Calculator and work out 25 times 4" -> [{"intent":"open_app_generic","params":{"app_name":"Calculator"}},{"intent":"type_text","params":{"text":"25*4="}}]
  "open Finder and go to my downloads" -> [{"intent":"open_folder","params":{"path":"~/Downloads"}}]
  "make a note saying buy milk and eggs" -> [{"intent":"notes_create","params":{"title":"Shopping","body":"Buy milk and eggs"}}]
- Prefer a dedicated intent (youtube_*, spotify_*, maps_search, web_search, notes_create, ...) when one fits; otherwise build the task from open_app_generic + app_search / press_keys / type_text / click_menu for ANY app.
- Use app names exactly as they appear in the installed apps list when possible.
- Messages, chats and emails: write them but NEVER press return or send; the user sends them. Then say e.g. "Your message to Tunde is ready to send." Never put placeholders like [Your Name] in them.
- web_search and open_website open their own tab: don't add new_tab or open_app_generic for the browser. Set params.browser ONLY when the user names a browser in this command; otherwise leave it out so the default browser is used.
- Questions ("what is the tallest building in the world") -> web_search with the question as query.
- web_search answer: one short sentence ONLY for stable facts that don't change over time (geography, science, history, definitions). For anything that can change (news, sports results, "latest"/"current"/"last", prices, weather, who holds an office, release dates), answer "" and say something like "Here's what I found." Your knowledge may be out of date (today's date is given below).
- Fix obvious speech-to-text spellings of names ("mr beast" -> "MrBeast", "wiz kid" -> "Wizkid").
- say: under 15 words, natural and friendly, describing what you're doing ("Playing the latest MrBeast video."). For web_search with an answer, say the answer.
- If nothing fits: {"actions": [], "say": "Sorry, I didn't catch that."}
Return only the JSON object."""


_INSTALLED_APPS: List[str] | None = None


def installed_apps() -> List[str]:
    """App names on this Mac, so the planner can pick real names ("VS Code" -> "Visual Studio Code")."""
    global _INSTALLED_APPS
    if _INSTALLED_APPS is None:
        names = set()
        for folder in ("/Applications", "/System/Applications", "/System/Applications/Utilities",
                       os.path.expanduser("~/Applications")):
            try:
                names.update(e[:-4] for e in os.listdir(folder) if e.endswith(".app"))
            except OSError:
                pass
        _INSTALLED_APPS = sorted(names, key=str.lower)
    return _INSTALLED_APPS


def _call_llm(text: str) -> Dict[str, Any]:
    # The big static prompt comes first so OpenAI can cache it; per-call details go after.
    context = f"Today's date: {date.today().isoformat()}."
    apps = installed_apps()
    if apps:
        context += " Installed apps: " + ", ".join(apps) + "."
    kwargs: Dict[str, Any] = dict(
        model=NLU_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": context},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
    )
    if NLU_MODEL.startswith("gpt-5"):
        kwargs["reasoning_effort"] = os.environ.get("MHCI_NLU_REASONING", "none")
    else:
        kwargs["temperature"] = 0.0
    resp = client.chat.completions.create(**kwargs)
    return json.loads(resp.choices[0].message.content)


# These open their own app/site, so a separate "open X" step right before them
# only adds waiting time.
_OPENS_ITSELF = {
    "web_search", "search", "search_google", "open_website", "maps_search",
    "youtube_search", "youtube_play", "spotify_search", "spotify_play", "music_play",
    "app_search", "notes_create", "reminder_create", "email_compose", "open_folder",
}


def _drop_redundant_opens(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for i, a in enumerate(actions):
        nxt = actions[i + 1] if i + 1 < len(actions) else None
        if a["intent"] == "open_app_generic" and nxt and nxt["intent"] in _OPENS_ITSELF:
            continue
        out.append(a)
    return out


def _clean_actions(raw: Any) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        intent = item.get("intent")
        if intent not in INTENT_WHITELIST:
            print(f"[NLU] Ignoring unknown intent: {intent!r}")
            continue
        params = item.get("params") or {}
        if not isinstance(params, dict):
            params = {}
        actions.append({"intent": intent, "params": params})
    return _drop_redundant_opens(actions)


def plan_command(text: str, max_actions: int = 6) -> Plan:
    t0 = time.time()
    plan = fast_path(text)
    if plan is None:
        if not LLM_ENABLED:
            plan = Plan(say="Sorry, I can only do simple commands without an OpenAI key.")
        else:
            try:
                data = _call_llm(text)
                plan = Plan(
                    actions=_clean_actions(data.get("actions")),
                    say=str(data.get("say") or "").strip(),
                    source="llm",
                )
            except Exception as e:
                print(f"[NLU] Planner error: {e}")
                plan = Plan(say="Sorry, I couldn't reach the planner.")
    plan.actions = plan.actions[:max_actions]
    plan.seconds = time.time() - t0
    return plan


#  Backwards-compatible API

def predict_intents_with_params(text: str, max_intents: int = 6) -> List[Dict[str, Any]]:
    """Returns [{"intent", "params", "confidence"}, ...] in order."""
    plan = plan_command(text, max_actions=max_intents)
    return [{**a, "confidence": 1.0} for a in plan.actions]


def predict_intent(text: str) -> str | None:
    items = predict_intents_with_params(text, max_intents=1)
    return items[0]["intent"] if items else None


if __name__ == "__main__":
    print("Type a sentence (or 'quit') to see the plan:")
    while True:
        s = input(">> ").strip()
        if s.lower() == "quit":
            break
        p = plan_command(s)
        print(f"→ [{p.source} {p.seconds:.2f}s] say={p.say!r}")
        for a in p.actions:
            print("   ", a)
