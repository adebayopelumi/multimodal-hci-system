# engine/voice/history.py
import json
import datetime
from pathlib import Path
from typing import Optional, Dict, Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = PROJECT_ROOT / "voice_history.jsonl"


def _append_entry(entry: Dict[str, Any]) -> None:
    """
    Append a single JSON object as one line to voice_history.jsonl.
    Creates the file if it doesn't exist.
    """
    try:
        with HISTORY_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        # We never want history failures to crash the assistant
        print(f"[History] Failed to write entry: {e}")


def log_search(query: str,
               app_name: Optional[str] = None,
               raw_text: Optional[str] = None) -> None:
    """
    Log a search-type query (e.g., 'who is jesus christ').
    """
    entry = {
        "type": "search",
        "timestamp": datetime.datetime.now().isoformat(),
        "query": query,
        "app_name": app_name,
        "raw_text": raw_text,
    }
    _append_entry(entry)


if __name__ == "__main__":
    # Simple viewer: print all history lines
    if HISTORY_PATH.exists():
        print(f"--- Search history from {HISTORY_PATH} ---")
        with HISTORY_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    obj = line.strip()
                print(obj)
    else:
        print("No history file yet.")