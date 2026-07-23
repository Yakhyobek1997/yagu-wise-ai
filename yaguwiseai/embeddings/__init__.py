"""Embeddings: dense + sparse, provider-abstracted, with offline fallback."""

from __future__ import annotations

from yaguwiseai.embeddings.base import Embedder, Embedding, EmbeddingBatch, SparseVector
from yaguwiseai.embeddings.factory import build_embedder, get_embedder, resolved_provider
from yaguwiseai.embeddings.hashing import HashingEmbedder

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
