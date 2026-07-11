"""FastAPI serving layer: SSE chat, WebSocket voice, ingest/query/eval endpoints."""

from __future__ import annotations

from auralynq.serving.app import app, create_app

__all__ = ["app", "create_app"]
