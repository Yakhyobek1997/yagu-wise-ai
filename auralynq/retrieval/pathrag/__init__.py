"""PathRAG: relational graph retrieval with flow-based path pruning (ADR-0006).

``PathRAGRetriever`` is exposed lazily to avoid an import cycle (the retriever
imports the vector store, which imports ``retrieval.models`` → this package).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from auralynq.retrieval.pathrag.builder import build_from_chunks
from auralynq.retrieval.pathrag.graph import KnowledgeGraph, Provenance

if TYPE_CHECKING:  # pragma: no cover
    from auralynq.retrieval.pathrag.retriever import PathRAGRetriever

__all__ = ["KnowledgeGraph", "PathRAGRetriever", "Provenance", "build_from_chunks"]


def __getattr__(name: str):
    if name == "PathRAGRetriever":
        from auralynq.retrieval.pathrag.retriever import PathRAGRetriever

        return PathRAGRetriever
    raise AttributeError(f"module 'auralynq.retrieval.pathrag' has no attribute {name!r}")
