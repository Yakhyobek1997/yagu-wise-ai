"""Typed agent state flowing through the LangGraph loop (ADR-0008)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from auralynq.retrieval.models import PathEvidence, ScoredChunk
from auralynq.retrieval.router import Route


class AgentState(BaseModel):
    # inputs
    question: str
    original_question: str = ""
    final_k: int = 6
    route_hint: str = ""  # caller override: "fast" | "hybrid" | "graph" | "" (auto)

    # routing
    route: Route = Route.fast
    route_confidence: float = 0.0
    route_rationale: str = ""

    # working memory
    contexts: list[ScoredChunk] = Field(default_factory=list)
    path_evidence: list[PathEvidence] = Field(default_factory=list)
    seeds: list[str] = Field(default_factory=list)

    # control
    iteration: int = 0
    max_iters: int = 3
    need_rewrite: bool = False
    gaps: list[str] = Field(default_factory=list)
    coverage: float = 0.0
    semantic_coverage: float = 0.0  # cosine(query_emb, mean(context_embs))
    elapsed_ms: float = 0.0
    latency_budget_ms: int = 15_000

    # outputs
    answer: str = ""
    citations: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    # Per-signal breakdown for UI ConfidenceBar (paper §4.3, Eq. 6)
    confidence_signals: dict[str, float] = Field(default_factory=dict)
    cached: bool = False
    notes: list[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    def out_of_budget(self) -> bool:
        return self.elapsed_ms >= self.latency_budget_ms
