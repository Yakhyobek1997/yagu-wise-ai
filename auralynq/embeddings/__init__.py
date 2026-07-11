"""Embeddings: dense + sparse, provider-abstracted, with offline fallback."""

from __future__ import annotations

from auralynq.embeddings.base import Embedder, Embedding, EmbeddingBatch, SparseVector
from auralynq.embeddings.factory import build_embedder, get_embedder, resolved_provider
from auralynq.embeddings.hashing import HashingEmbedder

__all__ = [
    "Embedder",
    "Embedding",
    "EmbeddingBatch",
    "HashingEmbedder",
    "SparseVector",
    "build_embedder",
    "get_embedder",
    "resolved_provider",
]
