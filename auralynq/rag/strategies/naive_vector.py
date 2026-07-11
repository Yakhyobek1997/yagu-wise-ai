"""Naive vector-only RAG strategy."""

from __future__ import annotations

from typing import Any

from auralynq.rag.strategies.base import RAGStrategy, StrategyResult


class NaiveVectorStrategy(RAGStrategy):
    id = "naive_vector"
    name = "Naive Vector RAG"
    description = "Vector-only retrieval using cosine similarity. Fast, simple, no reranking."
    status = "available"
    required_features = []
    supports_streaming = True
    supports_graph = False
    supports_rerank = False
    supports_web = False
    supports_abstention = False
    expected_latency = "fast"
    best_for = "Simple factual questions with clear keyword overlap"
    limitations = "No keyword search; misses exact-match queries; no evidence sufficiency check"

    def run(
        self,
        query: str,
        final_k: int = 6,
        use_cache: bool = True,
        route_hint: str = "",
        **kwargs: Any,
    ) -> StrategyResult:
        from auralynq.agent.runner import answer_question

        res = answer_question(query, final_k=final_k, use_cache=use_cache, route_hint="fast")
        d = res.to_dict()
        return StrategyResult(
            answer=d.get("answer", ""),
            status=d.get("status", "answered"),
            citations=d.get("citations", []),
            route="naive_vector",
            confidence=d.get("confidence", 0.0),
            evidence_coverage=d.get("evidence_coverage", 0.0),
            trace_steps=d.get("trace_steps", []),
            trace=d.get("trace", []),
            path_evidence=[],
            seeds=d.get("seeds", []),
            warnings=["Strategy: naive_vector — no reranking or graph expansion"],
            strategy_id=self.id,
            strategy_name=self.name,
            elapsed_ms=d.get("elapsed_ms", 0.0),
            iterations=d.get("iterations", 0),
            detected_entities=d.get("detected_entities", []),
            suggested_questions=d.get("suggested_questions", []),
            cached=d.get("cached", False),
        )
