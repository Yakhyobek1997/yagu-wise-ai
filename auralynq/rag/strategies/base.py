"""Base class for all RAG strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StrategyResult:
    answer: str
    status: str
    citations: list[dict[str, Any]]
    route: str
    confidence: float
    evidence_coverage: float
    trace_steps: list[dict[str, Any]]
    trace: list[dict[str, Any]]
    path_evidence: list[dict[str, Any]]
    seeds: list[str]
    warnings: list[str]
    strategy_id: str
    strategy_name: str
    fallback_strategy: str | None = None
    fallback_reason: str | None = None
    strategy_warnings: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0
    iterations: int = 0
    detected_entities: list[str] = field(default_factory=list)
    suggested_questions: list[str] = field(default_factory=list)
    cached: bool = False
    route_confidence: float = 1.0
    route_rationale: str = ""
    # Per-signal confidence breakdown (paper §4.3): s_qual, s_cite, s_sem, s_tok
    confidence_signals: dict[str, float] = field(default_factory=dict)
    model_fit: dict[str, Any] | None = None


class RAGStrategy(ABC):
    id: str = ""
    name: str = ""
    description: str = ""
    status: str = "planned"  # available | experimental | planned
    required_features: list[str] = []
    supports_streaming: bool = True
    supports_graph: bool = False
    supports_rerank: bool = False
    supports_web: bool = False
    supports_abstention: bool = True
    expected_latency: str = "medium"  # fast | medium | slow
    best_for: str = ""
    limitations: str = ""

    def is_available(self) -> tuple[bool, str]:
        """Return (available, reason_if_not)."""
        return True, ""

    @abstractmethod
    def run(self, query: str, **kwargs: Any) -> StrategyResult: ...
