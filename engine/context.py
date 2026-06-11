# engine/context.py

from dataclasses import dataclass

@dataclass
class RuntimeContext:
    context_app: str | None = None

CTX = RuntimeContext()

def set_context_app(app: str | None):
    CTX.context_app = app

def get_context_app() -> str | None:
    return CTX.context_app