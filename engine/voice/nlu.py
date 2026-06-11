# engine/voice/nlu.py  
import json
import os
from pathlib import Path
from typing import Dict, List, Any


try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# OpenAI client setup

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPENAI_KEY_PATH = PROJECT_ROOT / "openai_key.txt"


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
    print("[NLU] GPT-4.1 LLM enabled.")
else:
    client = None
    LLM_ENABLED = False
    if OpenAI is None:
        print("[NLU] openai package not installed, LLM NLU disabled.")
    else:
        print("[NLU] No OPENAI_API_KEY found, LLM NLU disabled.")


# Intent whitelist – must match what mac_actions.py can handle

INTENT_WHITELIST: List[str] = sorted({
    # volume / audio
    "volume_up", "volume_down", "mute_volume", "unmute_volume",

    # brightness / scroll
    "brightness_up", "brightness_down", "scroll_up", "scroll_down",

    # navigation
    "next_tab", "previous_tab",
    "next_app", "previous_app",
    "next_window", "previous_window",
    "next_action", "previous_action",

    # media
    "pause_media", "play_media",

    # connectivity
    "bluetooth_on", "bluetooth_off",
    "wifi_on", "wifi_off",

    # timers / alarms
    "set_timer",
    "set_alarm",

    # system
    "capture_screen", "lock_screen",

    # apps
    "open_chrome", "open_finder", "open_vs_code", "open_settings",
    "open_app_generic", "close_app_generic",

    # info
    "what_time", "what_date", "what_weather",

    # search
    "search", "search_google",

    # browser extras
    "new_tab", "close_tab",
})


# Core: LLM multi-intent + params

def _llm_intents_with_params(text: str) -> List[Dict[str, Any]]:
    """
    Ask GPT-4.1 to parse the user text into a list of
    {intent, confidence, params}.
    Returns [] on any error or if no intent fits.
    """
    if not LLM_ENABLED or not text:
        return []

    system_prompt = (
        "You are the NLU module for a desktop voice assistant on macOS.\n"
        "Your job is to map the user's natural language command into "
        "a small set of high-level intents plus parameters.\n\n"
        "You MUST respond with STRICT JSON, with NO explanations.\n"
        "Respond in ONE of these formats only:\n"
        "1) A bare JSON array:\n"
        "   [\n"
        "     {\"intent\": \"volume_up\", \"confidence\": 1.0, \"params\": {}},\n"
        "     {\"intent\": \"search\", \"confidence\": 0.9, "
        "      \"params\": {\"query\": \"who is cristiano ronaldo\"}}\n"
        "   ]\n"
        "OR\n"
        "2) An object with an 'intents' field:\n"
        "   {\"intents\": [ ...same as above... ]}\n\n"
        "Each element MUST have exactly:\n"
        "  - intent: one of the allowed intents\n"
        "  - confidence: number between 0.0 and 1.0\n"
        "  - params: an object with any extra info (may be empty)\n\n"
        f"Allowed intents are: {', '.join(INTENT_WHITELIST)}.\n\n"
        "Guidance:\n"
        "- For simple device control like volume/brightness/scroll, "
        "  choose the obvious intent, e.g. 'volume_up', 'brightness_down', 'scroll_up'.\n"
        "- For opening apps like 'open whatsapp' or 'launch spotify', "
        "  use 'open_app_generic' and set params.app_name to a clean macOS app name, "
        "  e.g. 'WhatsApp', 'Spotify', 'Visual Studio Code'.\n"
        "- For closing apps ('close this app', 'quit chrome'), use 'close_app_generic'.\n"
        "- For questions like 'what is the time' or 'what's today's date', "
        "  use 'what_time' or 'what_date'.\n"
        "If the user says “open X and search Y”, the search must have params.app_name = X. Do NOT default to browser if an app is specified.\n"
        "- For weather questions like 'will I need an umbrella today', use 'what_weather'.\n"
        "- For general knowledge or web questions like "
        "  'who is Jesus Christ', 'who is cristiano ronaldo', "
        "  'what is a black hole', 'what is AI', etc., "
        "  use the intent 'search' and put the full question into params.query.\n"
        "- For explicit Google search phrasing like 'search for laptops on google', "
        "  you may use 'search_google' with params.query = 'laptops'.\n"
        "- It's OK to return multiple intents in order for a long command, "
        "  e.g. 'open chrome and search for laptops' → "
        "  first 'open_app_generic', then 'search_google'.\n"
        "- For timers like 'set a timer for 10 minutes' or 'timer for 30 seconds', "
        "  use intent 'set_timer' and include ONE of:\n"
        "    params = {\"minutes\": <int>} OR params = {\"seconds\": <int>}.\n"
        "  Convert spoken numbers to integers.\n"

        "- For alarms like 'set an alarm for 7 PM' or 'wake me at 6:30 AM', "
        "  use intent 'set_alarm' with params:\n"
        "    {\n"
        "      \"hour\": <int>,\n"
        "      \"minute\": <int>,\n"
        "      \"ampm\": \"AM\" or \"PM\"\n"
        "    }\n"
        "  If minutes are not spoken, default minute to 0.\n"
        "- If nothing makes sense, return an empty list or an object with 'intents': [].\n"
        "Do NOT include any extra keys or text outside the JSON."
    )

    user_prompt = f'User command: "{text}"'

    try:
        resp = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )
        content = resp.choices[0].message.content.strip()

        # Parse JSON
        data = json.loads(content)

        # Accept both shapes: [ ... ] or { "intents": [ ... ] }
        if isinstance(data, list):
            intents_raw = data
        elif isinstance(data, dict):
            intents_raw = data.get("intents", [])
        else:
            intents_raw = []

        results: List[Dict[str, Any]] = []
        for item in intents_raw:
            if not isinstance(item, dict):
                continue
            intent = item.get("intent")
            if not intent or intent not in INTENT_WHITELIST:
                continue
            conf = float(item.get("confidence", 0.0))
            params = item.get("params", {}) or {}
            results.append(
                {"intent": intent, "confidence": conf, "params": params}
            )

        return results

    except Exception as e:
        print(f"[NLU] Error calling GPT-4.1: {e}")
        return []


# Public API

def predict_intents_with_params(
    text: str,
    min_llm_confidence: float = 0.55,
    max_intents: int = 4,
) -> List[Dict[str, Any]]:
    """
    Returns an ordered list:
      [{ "intent": ..., "params": {...}, "confidence": ... }, ...]
    Uses ONLY GPT-4.1. No fuzzy, no priority rules.
    """
    if not text:
        return []

    if not LLM_ENABLED:
        print("[NLU] LLM disabled; returning no intents.")
        return []

    llm_results = _llm_intents_with_params(text)
    print(f"[NLU] LLM multi raw={llm_results}")

    accepted: List[Dict[str, Any]] = []
    for it in llm_results:
        if it.get("confidence", 0.0) >= min_llm_confidence:
            accepted.append(
                {
                    "intent": it["intent"],
                    "params": it.get("params", {}),
                    "confidence": it["confidence"],
                }
            )

    return accepted[:max_intents]


def predict_intent(text: str) -> str | None:
    """
    Simple helper: return just the top intent or None.
    """
    items = predict_intents_with_params(text, max_intents=1)
    return items[0]["intent"] if items else None


if __name__ == "__main__":
    print("Type a sentence (or 'quit') to see predicted intents+params:")
    while True:
        s = input(">> ").strip()
        if s.lower() == "quit":
            break
        res = predict_intents_with_params(s)
        print("→", res)