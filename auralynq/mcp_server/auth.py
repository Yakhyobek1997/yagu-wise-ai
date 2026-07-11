"""Bearer-token auth for the MCP HTTP transports (ADR-0016).

The stdio transport is inherently local (the client spawns the process) and needs
no network auth. The HTTP transports (``streamable-http`` / ``sse``) are remotely
reachable, so when a key is configured they require
``Authorization: Bearer <key>``.

Key resolution (first non-empty wins):
  1. ``AURALYNQ_MCP_API_KEY`` — a key dedicated to the MCP surface, OR
  2. ``AURALYNQ_SERVE__API_KEY`` — reuse the HTTP API's key.
Empty ⇒ open (local/demo). Comparison is constant-time.

The MCP protocol's own handshake endpoints stay reachable; auth is applied at the
ASGI layer in front of the FastMCP app so every MCP request is gated uniformly.
"""

from __future__ import annotations

import hmac
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


def resolve_mcp_api_key() -> str:
    """Return the configured MCP bearer key (dedicated key wins, else API key)."""
    return os.getenv("AURALYNQ_MCP_API_KEY") or os.getenv("AURALYNQ_SERVE__API_KEY") or ""


class MCPAuthMiddleware(BaseHTTPMiddleware):
    """Require a bearer token on the MCP HTTP surface when a key is configured."""

    def __init__(self, app, api_key: str = "") -> None:
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next):
        if not self.api_key or request.method == "OPTIONS":
            return await call_next(request)
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(token, self.api_key):
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "detail": "missing or invalid bearer token"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)
