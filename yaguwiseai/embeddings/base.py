"""Embedding interfaces.

An :class:`Embedder` produces *both* a dense vector and a sparse (lexical) vector
so the vector store can do true hybrid retrieval. ``SparseVector`` maps integer
term ids to weights.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

import numpy as np

SparseVector = dict[int, float]


@dataclass
class Embedding:
    dense: np.ndarray
    sparse: SparseVector = field(default_factory=dict)


@dataclass
class EmbeddingBatch:
    dense: np.ndarray  # shape (n, dim)
    sparse: list[SparseVector] = field(default_factory=list)

    def __len__(self) -> int:
        return int(self.dense.shape[0])


class Embedder(abc.ABC):
    """Abstract embedder. Implementations must be deterministic given a seed."""

    name: str = "base"
    dim: int = 0

    @abc.abstractmethod
    def embed(self, texts: list[str]) -> EmbeddingBatch:
        """Embed a batch of documents (dense + sparse)."""

    def embed_query(self, text: str) -> Embedding:
        batch = self.embed([text])
        sparse = batch.sparse[0] if batch.sparse else {}
        return Embedding(dense=batch.dense[0], sparse=sparse)

    @staticmethod
    def cosine(a: np.ndarray, b: np.ndarray) -> float:
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0.0:
            return 0.0
        return float(np.dot(a, b) / denom)
