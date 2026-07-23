"""Retrieval: naive, hybrid, PathRAG, and the adaptive router.

Retriever implementations are exposed lazily: they import the vector store, while
``vectorstore.base`` imports ``retrieval.models`` — eager re-exports here would
create an import cycle. ``models`` and ``router`` are light and exported eagerly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from yaguwiseai.retrieval.models import (
    Filter,
    PathEvidence,
    RetrievalResult,
    ScoredChunk,
)
from yaguwiseai.retrieval.router import Route, RouteDecision, route_query

if TYPE_CHECKING:  # pragma: no cover
    from yaguwiseai.retrieval.hybrid.retriever import HybridRetriever
    from yaguwiseai.retrieval.naive import NaiveRetriever
    from yaguwiseai.retrieval.pathrag.retriever import PathRAGRetriever

__all__ = [
    "Filter",
    "HybridRetriever",
    "NaiveRetriever",
    "PathEvidence",
    "PathRAGRetriever",
    "RetrievalResult",
    "Route",
    "RouteDecision",
    "ScoredChunk",
    "route_query",
]

_LAZY = {
    "HybridRetriever": "yaguwiseai.retrieval.hybrid.retriever",
    "NaiveRetriever": "yaguwiseai.retrieval.naive",
    "PathRAGRetriever": "yaguwiseai.retrieval.pathrag.retriever",
}


def __getattr__(name: str):
    if name in _LAZY:
        import importlib

        return getattr(importlib.import_module(_LAZY[name]), name)
    raise AttributeError(f"module 'yaguwiseai.retrieval' has no attribute {name!r}")
