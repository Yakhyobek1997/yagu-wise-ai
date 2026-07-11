"""Lightweight tracing.

Always-on, zero-dependency in-process tracer that records spans (name, timing,
attributes) so the agent trajectory can be surfaced in the API/UI even without
OpenTelemetry installed. When the ``telemetry`` extra is present and enabled,
spans are mirrored to OpenTelemetry / Phoenix.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from auralynq.telemetry.logging import get_logger

_log = get_logger("auralynq.trace")


@dataclass
class Span:
    name: str
    start_ms: float
    end_ms: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        if self.end_ms is None:
            return 0.0
        return round(self.end_ms - self.start_ms, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "events": self.events,
        }


@dataclass
class Trace:
    """Collects spans for a single request/trajectory."""

    trace_id: str
    spans: list[Span] = field(default_factory=list)
    _t0: float = field(default_factory=time.perf_counter)

    @contextlib.contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[Span]:
        sp = Span(name=name, start_ms=self._elapsed(), attributes=dict(attributes))
        self.spans.append(sp)
        otel_cm = _otel_span(name, attributes)
        otel_cm.__enter__()
        try:
            yield sp
        except Exception as exc:  # record and re-raise
            sp.events.append({"event": "exception", "error": repr(exc)})
            raise
        finally:
            sp.end_ms = self._elapsed()
            otel_cm.__exit__(None, None, None)

    def event(self, span: Span, message: str, **data: Any) -> None:
        span.events.append({"event": message, **data, "at_ms": self._elapsed()})

    def _elapsed(self) -> float:
        return (time.perf_counter() - self._t0) * 1000.0

    @property
    def total_ms(self) -> float:
        return round(self._elapsed(), 3)

    def to_list(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self.spans]


@contextlib.contextmanager
def _otel_span(name: str, attributes: dict[str, Any]) -> Iterator[None]:
    """Mirror to OpenTelemetry if available; otherwise a no-op."""
    try:  # pragma: no cover - exercised only when telemetry extra installed
        from opentelemetry import trace as ot

        tracer = ot.get_tracer("auralynq")
        with tracer.start_as_current_span(name) as sp:
            for k, v in attributes.items():
                with contextlib.suppress(Exception):
                    sp.set_attribute(k, v)
            yield
    except Exception:
        yield


_TELEMETRY_INITIALIZED = False


def init_telemetry(service_name: str = "auralynq", endpoint: str = "") -> bool:
    """Best-effort OpenTelemetry init. Returns True if wired, else False."""
    global _TELEMETRY_INITIALIZED
    if _TELEMETRY_INITIALIZED:
        return True
    try:  # pragma: no cover - optional extra
        from opentelemetry import trace as ot
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        if endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        ot.set_tracer_provider(provider)
        _TELEMETRY_INITIALIZED = True
        _log.info("telemetry.initialized", service=service_name, endpoint=endpoint or "in-process")
        return True
    except Exception as exc:
        _log.info("telemetry.disabled", reason=str(exc))
        return False
