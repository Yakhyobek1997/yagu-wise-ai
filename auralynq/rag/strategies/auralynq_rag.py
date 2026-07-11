"""Auralynq-RAG: the primary orchestrated strategy (wraps the existing agent runner)."""

from __future__ import annotations

import time
from typing import Any

from auralynq.rag.strategies.base import RAGStrategy, StrategyResult


class AuralynqRAGStrategy(RAGStrategy):
    id = "auralynq_rag"
    name = "Auralynq-RAG"
    description = (
        "Observable, calibrated, agentic RAG with intent routing, evidence sufficiency "
        "control, citation validation, and hallucination risk scoring."
    )
    status = "available"
    required_features = []
    supports_streaming = True
    supports_graph = True
    supports_rerank = True
    supports_web = False
    supports_abstention = True
    expected_latency = "medium"
    best_for = "General corpus questions with citations and traceability"
    limitations = "Web search disabled by default; graph requires indexed entities"

    def run(
        self,
        query: str,
        final_k: int = 6,
        use_cache: bool = True,
        route_hint: str = "",
        **kwargs: Any,
    ) -> StrategyResult:
        from auralynq.agent.runner import answer_question

        t0 = time.perf_counter()
        res = answer_question(query, final_k=final_k, use_cache=use_cache, route_hint=route_hint)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        d = res.to_dict()
        return StrategyResult(
            answer=d.get("answer", ""),
            status=d.get("status", "answered"),
            citations=d.get("citations", []),
            route=d.get("route", "fast"),
            confidence=d.get("confidence", 0.0),
            evidence_coverage=d.get("evidence_coverage", 0.0),
            trace_steps=d.get("trace_steps", []),
            trace=d.get("trace", []),
            path_evidence=d.get("path_evidence", []),
            seeds=d.get("seeds", []),
            warnings=d.get("warnings", []),
            strategy_id=self.id,
            strategy_name=self.name,
            elapsed_ms=d.get("elapsed_ms", elapsed_ms),
            iterations=d.get("iterations", 0),
            detected_entities=d.get("detected_entities", []),
            suggested_questions=d.get("suggested_questions", []),
            cached=d.get("cached", False),
            route_confidence=d.get("route_confidence", 1.0),
            route_rationale=d.get("route_rationale", ""),
            confidence_signals=d.get("confidence_signals", {}),
        )
