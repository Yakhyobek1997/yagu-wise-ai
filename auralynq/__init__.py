"""Auralynq — Talk to Your Data.

A local-first, agentic, voice-enabled RAG platform with PathRAG graph retrieval.
"""

from __future__ import annotations

__version__ = "0.2.0"

__all__ = ["Settings", "__version__", "get_settings"]


def __getattr__(name: str):  # pragma: no cover - thin lazy re-export
    # Lazy re-export keeps `import auralynq` cheap and side-effect free.
    if name in ("get_settings", "Settings"):
        from auralynq.config import Settings, get_settings

        return {"get_settings": get_settings, "Settings": Settings}[name]
    raise AttributeError(f"module 'auralynq' has no attribute {name!r}")
