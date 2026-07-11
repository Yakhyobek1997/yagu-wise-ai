"""Turn raw trace spans into a product-grade Agent Trace.

The in-process :class:`~auralynq.telemetry.tracing.Trace` records low-level spans.
This module maps them to a stable, human-legible step list (status / duration /
provider / counts) plus a summary dashboard, so the frontend renders real
observability instead of a debug dump.
"""

from __future__ import annotations

from typing import Any

# span name (substring) -> (friendly label, ordering hint)
_LABELS: list[tuple[str, str]] = [
    ("plan", "Query planning"),
    ("rewrite", "Query rewrite"),
    ("route", "Route selection"),
    ("retriev", "Retrieval"),
    ("pathrag", "Graph expansion (PathRAG)"),
    ("graph", "Graph expansion (PathRAG)"),
    ("fus", "Rerank & fuse"),
    ("rerank", "Rerank & fuse"),
    ("critic", "Evidence sufficiency check"),
    ("synthes", "Answer generation"),
    ("self_check", "Self-check"),
    ("citation", "Citation validation"),
]


def _label_for(name: str) -> str:
    low = name.lower()
    for key, label in _LABELS:
        if key in low:
            return label
    return name.replace("_", " ").title()


def _status_for(span: dict[str, Any]) -> str:
    events = span.get("events") or []
    if any(e.get("event") == "exception" for e in events):
        return "failed"
    attrs = span.get("attributes") or {}
    if attrs.get("need_rewrite"):
        return "warning"
    cov = attrs.get("coverage")
    if isinstance(cov, (int, float)) and cov < 0.5:
        return "warning"
    return "success"


def to_trace_steps(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map raw spans to ordered, labelled steps with status + key metrics."""
    steps: list[dict[str, Any]] = []
    for i, span in enumerate(trace):
        attrs = span.get("attributes") or {}
        provider = attrs.get("provider")
        steps.append(
            {
                "id": i,
                "name": span.get("name", f"step_{i}"),
                "label": _label_for(span.get("name", "")),
                "status": _status_for(span),
                "duration_ms": round(float(span.get("duration_ms", 0.0)), 2),
                "provider": provider,
                "evidence_count": attrs.get("n_citations"),
                "warnings": [
                    e.get("error", "exception")
                    for e in (span.get("events") or [])
                    if e.get("event") == "exception"
                ],
                "attributes": {
                    k: v
                    for k, v in attrs.items()
                    if k in {"coverage", "need_rewrite", "route", "confidence", "iteration"}
                },
            }
        )
    return steps


def trace_summary(
    trace: list[dict[str, Any]],
    *,
    route: str,
    confidence: float,
    evidence_coverage: float,
    insufficient: bool,
    fallback_used: bool = False,
) -> dict[str, Any]:
    """Roll spans up into the summary-dashboard numbers."""
    total = round(sum(float(s.get("duration_ms", 0.0)) for s in trace), 2)

    def _bucket(*keys: str) -> float:
        return round(
            sum(
                float(s.get("duration_ms", 0.0))
                for s in trace
                if any(k in s.get("name", "").lower() for k in keys)
            ),
            2,
        )

    retrieval_ms = _bucket("retriev", "pathrag", "fuse", "rerank")
    generation_ms = _bucket("synthes")
    # Hallucination risk: answered with weak grounding is the danger zone; an
    # honest abstention is *low* risk by design.
    if insufficient:
        risk = "none"
    elif confidence >= 0.6 and evidence_coverage >= 0.6:
        risk = "low"
    elif confidence >= 0.4:
        risk = "medium"
    else:
        risk = "high"
    return {
        "total_latency_ms": total,
        "retrieval_latency_ms": retrieval_ms,
        "generation_latency_ms": generation_ms,
        "evidence_coverage": round(evidence_coverage, 3),
        "answer_confidence": round(confidence, 3),
        "hallucination_risk": risk,
        "route": route,
        "abstained": insufficient,
        "fallback_used": fallback_used,
    }
