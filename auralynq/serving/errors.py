"""Structured error handling for the API.

Every error response — AuralynqError, a plain FastAPI/Starlette
HTTPException (404s, the auth middleware's 401), a 422 request-validation
error, or an unhandled exception — uses the same envelope so a client only
ever parses one shape:

    {"error": {"code": "...", "message": "...", "details": {...}, "trace_id": "..."}}

`trace_id` is the same per-request ID already exposed via the `X-Request-ID`
response header (see the request_id middleware in auralynq/serving/app.py).
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def _trace_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _envelope(code: str, message: str, details: dict[str, Any], trace_id: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details, "trace_id": trace_id}}


class AuralynqError(Exception):
    """Raise with a short machine-readable ``code`` and a human ``detail``."""

    def __init__(
        self,
        code: str,
        *,
        status_code: int = 400,
        detail: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.message = detail or code
        self.details = details or {}


async def auralynq_error_handler(request: Request, exc: AuralynqError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(exc.code, exc.message, exc.details, _trace_id(request)),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Covers plain `raise HTTPException(...)` calls and framework 404s/405s."""
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope("http_error", str(exc.detail), {}, _trace_id(request)),
        headers=getattr(exc, "headers", None),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_envelope(
            "validation_error",
            "Request validation failed",
            {"errors": exc.errors()},
            _trace_id(request),
        ),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=_envelope("internal_error", str(exc), {}, _trace_id(request)),
    )
