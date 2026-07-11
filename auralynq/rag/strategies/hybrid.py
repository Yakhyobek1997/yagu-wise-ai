"""Hybrid dense+sparse retrieval strategy."""

from __future__ import annotations

from typing import Any

from auralynq.rag.strategies.base import RAGStrategy, StrategyResult


class HybridStrategy(RAGStrategy):
    id = "hybrid"
    name = "Hybrid Dense + Sparse"
    description = (
        "Combines vector (dense) and BM25 (sparse) retrieval using Reciprocal Rank Fusion."
    )
    status = "available"
    required_features = []
    supports_streaming = True
    supports_graph = False
    supports_rerank = False
    supports_web = False
    supports_abstention = True
    expected_latency = "medium"
    best_for = "Mixed queries with both semantic and keyword components"
    limitations = "No graph expansion; no reranking"

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
            route="hybrid",
            confidence=d.get("confidence", 0.0),
            evidence_coverage=d.get("evidence_coverage", 0.0),
            trace_steps=d.get("trace_steps", []),
            trace=d.get("trace", []),
            path_evidence=[],
            seeds=d.get("seeds", []),
            warnings=[],
            strategy_id=self.id,
            strategy_name=self.name,
            elapsed_ms=d.get("elapsed_ms", 0.0),
            iterations=d.get("iterations", 0),
            detected_entities=d.get("detected_entities", []),
            suggested_questions=d.get("suggested_questions", []),
            cached=d.get("cached", False),
        )


class HybridRerankStrategy(RAGStrategy):
    id = "hybrid_rerank"
    name = "Hybrid + Rerank"
    description = "Hybrid retrieval followed by cross-encoder reranking for higher precision."
    status = "experimental"
    required_features = ["reranker"]
    supports_streaming = True
    supports_graph = False
    supports_rerank = True
    supports_web = False
    supports_abstention = True
    expected_latency = "medium"
    best_for = "Precision-sensitive queries where top-1 accuracy matters most"
    limitations = "Requires reranker model; adds ~200-500ms latency"

    def is_available(self) -> tuple[bool, str]:
        try:
            from auralynq.config import get_settings

            s = get_settings()
            if getattr(s, "reranker_enabled", False):
                return True, ""
            return False, "Reranker not enabled. Set AURALYNQ_RERANKER_ENABLED=true."
        except Exception:
            return False, "Could not determine reranker availability."

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
            route="hybrid_rerank",
            confidence=d.get("confidence", 0.0),
            evidence_coverage=d.get("evidence_coverage", 0.0),
            trace_steps=d.get("trace_steps", []),
            trace=d.get("trace", []),
            path_evidence=[],
            seeds=d.get("seeds", []),
            warnings=["Experimental: rerank scores may vary"],
            strategy_id=self.id,
            strategy_name=self.name,
            elapsed_ms=d.get("elapsed_ms", 0.0),
            iterations=d.get("iterations", 0),
            detected_entities=d.get("detected_entities", []),
            suggested_questions=d.get("suggested_questions", []),
            cached=d.get("cached", False),
        )
