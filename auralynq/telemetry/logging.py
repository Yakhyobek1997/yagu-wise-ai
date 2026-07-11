"""Structured logging via structlog with stdlib fallback.

Idempotent: ``configure_logging`` can be called multiple times safely.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

_CONFIGURED = False


def configure_logging(level: str = "INFO", json: bool = False) -> None:
    global _CONFIGURED
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
        stream=sys.stderr,
    )
    try:
        import structlog
    except ImportError:  # pragma: no cover - structlog is a core dep
        _CONFIGURED = True
        return

    renderer = (
        structlog.processors.JSONRenderer()
        if json
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
    _CONFIGURED = True


def get_logger(name: str = "auralynq", **initial: Any):
    """Return a bound structured logger (or stdlib logger as fallback)."""
    if not _CONFIGURED:
        configure_logging()
    try:
        import structlog

        return structlog.get_logger(name).bind(**initial)
    except ImportError:  # pragma: no cover
        return logging.getLogger(name)
