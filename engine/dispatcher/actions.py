# engine/dispatcher/actions.py
from __future__ import annotations
import platform
from typing import Any, Dict

def dispatch(intent: str, text: str | None = None, params: Dict[str, Any] | None = None):
    system = platform.system()
    if system == "Darwin":
        from engine.dispatcher.mac_actions import dispatch as impl
    elif system == "Windows":
        from engine.dispatcher.windows_actions import dispatch as impl
    else:
        raise RuntimeError(f"Unsupported OS: {system}")

    return impl(intent, text=text, params=params)