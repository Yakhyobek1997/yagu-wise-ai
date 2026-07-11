"""Retrieval: naive, hybrid, PathRAG, and the adaptive router.

Retriever implementations are exposed lazily: they import the vector store, while
``vectorstore.base`` imports ``retrieval.models`` — eager re-exports here would
create an import cycle. ``models`` and ``router`` are light and exported eagerly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from auralynq.retrieval.models import (
    Filter,
    PathEvidence,
    RetrievalResult,
    ScoredChunk,
)
from auralynq.retrieval.router import Route, RouteDecision, route_query

if TYPE_CHECKING:  # pragma: no cover
    from auralynq.retrieval.hybrid.retriever import HybridRetriever
    from auralynq.retrieval.naive import NaiveRetriever
    from auralynq.retrieval.pathrag.retriever import PathRAGRetriever

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
    "HybridRetriever": "auralynq.retrieval.hybrid.retriever",
    "NaiveRetriever": "auralynq.retrieval.naive",
    "PathRAGRetriever": "auralynq.retrieval.pathrag.retriever",
}


def __getattr__(name: str):
    if name in _LAZY:
        import importlib

        return getattr(importlib.import_module(_LAZY[name]), name)
    raise AttributeError(f"module 'auralynq.retrieval' has no attribute {name!r}")
