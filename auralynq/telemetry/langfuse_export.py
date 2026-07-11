"""Langfuse trace export (optional hosted observability).

Best-effort exporter that mirrors a finished in-process :class:`Trace` to Langfuse
as a trace with one nested span per agent node (planner, router, retrievers,
synthesizer, …), plus the question as input and the answer + route/citations as
output/metadata. This complements the always-on local tracer and the OTel/Phoenix
mirror — it never replaces them.

Activated only when both ``LANGFUSE_PUBLIC_KEY`` and ``LANGFUSE_SECRET_KEY`` are
set AND the ``langfuse`` SDK is importable AND ``AURALYNQ_AIR_GAPPED`` is not true.
Everything here is wrapped so that a missing SDK, missing keys, or any export error
is a silent no-op — observability must never affect the answer path (ADR-0003/0019).

PII sanitization (ADR-0020): when ``AURALYNQ_TELEMETRY__PII_FILTER=true`` (default)
common identifiers are redacted from question/answer strings before export so that
raw user queries are not persisted on Langfuse Cloud.
"""

from __future__ import annotations

import functools
import importlib.util
import re
from typing import TYPE_CHECKING, Any

from auralynq.config import get_settings
from auralynq.telemetry.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from auralynq.telemetry.tracing import Trace

_log = get_logger("auralynq.telemetry.langfuse")

# ---------------------------------------------------------------------------
# PII redaction — lightweight regex pass before any external export
# ---------------------------------------------------------------------------

_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), "[EMAIL]"),
    # US/intl phone numbers in common formats
    (
        re.compile(r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b"),
        "[PHONE]",
    ),
    # Social Security Numbers
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    # Payment card numbers (13-16 digits, optionally spaced/dashed)
    (
        re.compile(r"\b(?:\d{4}[-\s]?){3}\d{1,4}\b"),
        "[CARD]",
    ),
    # IPv4 addresses
    (
        re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"),
        "[IP]",
    ),
]


def sanitize_pii(text: str) -> str:
    """Replace known PII patterns with redaction tokens."""
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _maybe_sanitize(text: str) -> str:
    s = get_settings()
    if s.telemetry.pii_filter:
        return sanitize_pii(text)
    return text


# ---------------------------------------------------------------------------
# Langfuse availability check
# ---------------------------------------------------------------------------


def langfuse_enabled() -> bool:
    """True iff Langfuse is configured (both keys), SDK is importable, and not air-gapped."""
    s = get_settings()
    if s.air_gapped:
        return False
    if not (s.langfuse_public_key and s.langfuse_secret_key):
        return False
    return importlib.util.find_spec("langfuse") is not None


@functools.lru_cache(maxsize=1)
def _client():  # pragma: no cover - requires the optional SDK
    from langfuse import Langfuse

    s = get_settings()
    return Langfuse(
        public_key=s.langfuse_public_key,
        secret_key=s.langfuse_secret_key,
        host=s.telemetry.langfuse_host,
    )


def export_trace(
    trace: Trace,
    *,
    question: str,
    answer: str = "",
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Push ``trace`` to Langfuse. Returns True if exported, False otherwise.

    Never raises — any failure is logged at debug and swallowed.
    """
    if not langfuse_enabled():
        return False
    try:  # pragma: no cover - exercised only with the optional SDK + keys
        client = _client()
        meta = dict(metadata or {})
        # Sanitize before sending to the external trace backend.
        safe_question = _maybe_sanitize(question)
        safe_answer = _maybe_sanitize(answer)
        root = client.trace(
            name="auralynq.answer",
            id=trace.trace_id,
            input={"question": safe_question},
            output={"answer": safe_answer},
            metadata={**meta, "total_ms": trace.total_ms},
            tags=["auralynq", meta.get("route", "")] if meta.get("route") else ["auralynq"],
        )
        for sp in trace.spans:
            root.span(
                name=sp.name,
                metadata={"attributes": sp.attributes, "events": sp.events},
                start_time=None,
                end_time=None,
            )
        # Flush so short-lived CLI/agent processes actually send before exit.
        with __import__("contextlib").suppress(Exception):
            client.flush()
        return True
    except Exception as exc:
        _log.debug("langfuse.export_failed", error=str(exc)[:200])
        return False
