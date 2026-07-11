"""Deterministic hashing embedder — the $0 offline fallback (ADR-0003).

Uses the signed hashing trick for dense vectors and a hashed bag-of-words with
sublinear term frequency for sparse vectors. No model download, fully
reproducible, and good enough that token-overlap similarity ranks sensibly —
which is what the retrieval/agent unit tests rely on.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter

import numpy as np

from auralynq.embeddings.base import Embedder, EmbeddingBatch, SparseVector
from auralynq.utils import tokenize

_SPARSE_SPACE = 2**20


def _token_hash(token: str, salt: str = "") -> int:
    h = hashlib.blake2b((salt + token).encode("utf-8"), digest_size=8)
    return int.from_bytes(h.digest(), "little")


class HashingEmbedder(Embedder):
    """Stable embeddings with no external dependencies."""

    name = "hash"

    def __init__(self, dim: int = 256) -> None:
        # Keep the fallback dim small & fast; collection sizing reads this.
        self.dim = dim

    def embed(self, texts: list[str]) -> EmbeddingBatch:
        dense = np.zeros((len(texts), self.dim), dtype=np.float32)
        sparse: list[SparseVector] = []
        for i, text in enumerate(texts):
            tokens = tokenize(text)
            counts = Counter(tokens)
            vec = dense[i]
            sp: SparseVector = {}
            for tok, tf in counts.items():
                weight = 1.0 + math.log(tf)
                # Dense: two hashed buckets with sign for variance.
                h = _token_hash(tok)
                idx = h % self.dim
                sign = 1.0 if (h >> 1) & 1 else -1.0
                vec[idx] += sign * weight
                idx2 = _token_hash(tok, "b") % self.dim
                vec[idx2] += weight * 0.5
                # Sparse: hashed vocabulary id.
                sp[_token_hash(tok, "sparse") % _SPARSE_SPACE] = weight
            norm = float(np.linalg.norm(vec))
            if norm > 0:
                vec /= norm
            sparse.append(sp)
        return EmbeddingBatch(dense=dense, sparse=sparse)
