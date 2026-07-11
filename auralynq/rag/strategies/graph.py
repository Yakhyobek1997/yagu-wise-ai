"""GraphRAG / PathRAG strategy."""

from __future__ import annotations

from typing import Any

from auralynq.rag.strategies.base import RAGStrategy, StrategyResult


class GraphRAGStrategy(RAGStrategy):
    id = "graph_rag"
    name = "GraphRAG / PathRAG"
    description = "Graph-based retrieval using entity relationships and PathRAG expansion."
    status = "experimental"
    required_features = ["graph_index"]
    supports_streaming = True
    supports_graph = True
    supports_rerank = False
    supports_web = False
    supports_abstention = True
    expected_latency = "slow"
    best_for = "Multi-hop questions requiring entity relationship traversal"
    limitations = "Requires graph index; slow for large corpora; requires entity extraction"

    def is_available(self) -> tuple[bool, str]:
        try:
            from auralynq.serving.corpus import corpus_summary

            summary = corpus_summary()
            if summary.get("entity_count", 0) > 0:
                return True, ""
            return (
                False,
                "No graph index available. Index documents with entity extraction enabled.",
            )
        except Exception:
            return False, "Could not determine graph availability."

    def run(
        self,
        query: str,
        final_k: int = 6,
        use_cache: bool = True,
        route_hint: str = "",
        **kwargs: Any,
    ) -> StrategyResult:
        from auralynq.agent.runner import answer_question

        res = answer_question(query, final_k=final_k, use_cache=use_cache, route_hint="pathrag")
        d = res.to_dict()
        return StrategyResult(
            answer=d.get("answer", ""),
            status=d.get("status", "answered"),
            citations=d.get("citations", []),
            route="graph_rag",
            confidence=d.get("confidence", 0.0),
            evidence_coverage=d.get("evidence_coverage", 0.0),
            trace_steps=d.get("trace_steps", []),
            trace=d.get("trace", []),
            path_evidence=d.get("path_evidence", []),
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
