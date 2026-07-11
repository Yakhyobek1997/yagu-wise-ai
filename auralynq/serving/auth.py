"""Optional bearer-token authentication middleware.

When ``AURALYNQ_SERVE__API_KEY`` is empty (the default), the API is open — ideal
for the local/demo experience. When set, every endpoint except ``/health`` and
``/metrics`` (and CORS pre-flight ``OPTIONS``) requires
``Authorization: Bearer <key>``; otherwise a structured 401 is returned. Token
comparison is constant-time to avoid timing leaks (ADR-0011).
"""

from __future__ import annotations

import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_PUBLIC_PATHS = frozenset(
    {"/health", "/ready", "/version", "/metrics", "/docs", "/openapi.json", "/redoc"}
)


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key: str = "") -> None:
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next):
        if not self.api_key or request.method == "OPTIONS" or request.url.path in _PUBLIC_PATHS:
            return await call_next(request)
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(token, self.api_key):
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "unauthorized",
                        "message": "missing or invalid bearer token",
                        "details": {},
                        "trace_id": getattr(request.state, "request_id", ""),
                    }
                },
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)
