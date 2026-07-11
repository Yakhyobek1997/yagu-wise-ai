"""Central registry for all RAG strategies."""

from __future__ import annotations

from typing import Any

from auralynq.rag.strategies.auralynq_rag import AuralynqRAGStrategy
from auralynq.rag.strategies.base import RAGStrategy, StrategyResult
from auralynq.rag.strategies.graph import GraphRAGStrategy
from auralynq.rag.strategies.hybrid import HybridRerankStrategy, HybridStrategy
from auralynq.rag.strategies.naive_vector import NaiveVectorStrategy
from auralynq.rag.strategies.planned import (
    AdaptiveRAGStrategy,
    CRAGStrategy,
    KeywordBM25Strategy,
    LightRAGGlobalStrategy,
    LightRAGHybridStrategy,
    LightRAGLocalStrategy,
    RAPTORStrategy,
    SelfRAGStrategy,
)

_ALL_STRATEGIES: list[RAGStrategy] = [
    AuralynqRAGStrategy(),
    HybridStrategy(),
    NaiveVectorStrategy(),
    KeywordBM25Strategy(),
    HybridRerankStrategy(),
    GraphRAGStrategy(),
    LightRAGLocalStrategy(),
    LightRAGGlobalStrategy(),
    LightRAGHybridStrategy(),
    RAPTORStrategy(),
    SelfRAGStrategy(),
    CRAGStrategy(),
    AdaptiveRAGStrategy(),
]

_DEFAULT_STRATEGY_ID = "auralynq_rag"


def _attach_modelfit(result: StrategyResult) -> None:
    """Attach a ModelFit snapshot to a strategy result. Never raises."""
    try:
        from auralynq.agent.runner import _build_modelfit_snapshot
        from auralynq.config.settings import get_settings
        from auralynq.llm.factory import resolved_provider

        result.model_fit = _build_modelfit_snapshot(resolved_provider(), get_settings().llm.model)
    except Exception:
        pass


class RAGStrategyRegistry:
    def __init__(self, strategies: list[RAGStrategy]) -> None:
        self._strategies: dict[str, RAGStrategy] = {s.id: s for s in strategies}

    def get(self, strategy_id: str) -> RAGStrategy | None:
        return self._strategies.get(strategy_id)

    def list_all(self) -> list[dict[str, Any]]:
        result = []
        for s in self._strategies.values():
            available, unavailable_reason = s.is_available()
            result.append(
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "status": s.status,
                    "required_features": s.required_features,
                    "supports_streaming": s.supports_streaming,
                    "supports_graph": s.supports_graph,
                    "supports_rerank": s.supports_rerank,
                    "supports_web": s.supports_web,
                    "supports_abstention": s.supports_abstention,
                    "expected_latency": s.expected_latency,
                    "best_for": s.best_for,
                    "limitations": s.limitations,
                    "available": available,
                    "unavailable_reason": unavailable_reason if not available else None,
                }
            )
        return result

    def run(
        self,
        strategy_id: str,
        query: str,
        fallback_allowed: bool = True,
        force_strategy: bool = False,
        **kwargs: Any,
    ) -> StrategyResult:
        strategy = self.get(strategy_id)
        if strategy is None:
            if fallback_allowed:
                strategy = self.get(_DEFAULT_STRATEGY_ID)
                assert strategy is not None
                result = strategy.run(query, **kwargs)
                result.fallback_strategy = _DEFAULT_STRATEGY_ID
                result.fallback_reason = f"unknown_strategy: {strategy_id}"
                result.strategy_warnings = [
                    f"Unknown strategy '{strategy_id}'. Fell back to {_DEFAULT_STRATEGY_ID}."
                ]
                _attach_modelfit(result)
                return result
            raise ValueError(f"Unknown RAG strategy: {strategy_id}")

        available, reason = strategy.is_available()
        if not available:
            if fallback_allowed and not force_strategy:
                fallback = self.get(_DEFAULT_STRATEGY_ID)
                assert fallback is not None
                result = fallback.run(query, **kwargs)
                result.fallback_strategy = _DEFAULT_STRATEGY_ID
                result.fallback_reason = reason
                result.strategy_warnings = [
                    f"Requested {strategy_id}: {reason}. Fell back to {_DEFAULT_STRATEGY_ID}."
                ]
                _attach_modelfit(result)
                return result
            raise ValueError(f"Strategy {strategy_id} is not available: {reason}")

        result = strategy.run(query, **kwargs)
        _attach_modelfit(result)
        return result

    @property
    def default_strategy_id(self) -> str:
        return _DEFAULT_STRATEGY_ID


_registry: RAGStrategyRegistry | None = None


def get_registry() -> RAGStrategyRegistry:
    global _registry
    if _registry is None:
        _registry = RAGStrategyRegistry(_ALL_STRATEGIES)
    return _registry
