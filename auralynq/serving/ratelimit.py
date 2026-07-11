"""Minimal in-process fixed-window rate limiter (per client IP).

Sufficient for a local/demo single-instance deployment. For multi-instance,
swap for a Redis token bucket behind the same interface.
"""

from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit_per_min: int = 120) -> None:
        super().__init__(app)
        self.limit = limit_per_min
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health", "/metrics") or request.method == "OPTIONS":
            return await call_next(request)
        client = request.client.host if request.client else "anonymous"
        now = time.monotonic()
        window = self._hits[client]
        cutoff = now - 60.0
        window[:] = [t for t in window if t > cutoff]
        if len(window) >= self.limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "detail": f"max {self.limit} requests/min",
                    "request_id": getattr(request.state, "request_id", ""),
                },
                headers={"Retry-After": "60"},
            )
        window.append(now)
        return await call_next(request)
