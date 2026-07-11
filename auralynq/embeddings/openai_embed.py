"""OpenAI embeddings provider (optional, requires the ``llm`` extra + key).

OpenAI returns dense vectors only; for Auralynq's hybrid retrieval we pair them
with a deterministic hashed bag-of-words **sparse** vector (the same lexical
signal the hashing embedder uses), so dense+sparse fusion still works. Batches
are chunked to stay within the API's per-request limits. Falls back upstream to
the hashing embedder if the SDK/key is unavailable (see factory, ADR-0004).
"""

from __future__ import annotations

import functools

import numpy as np

from auralynq.embeddings.base import Embedder, EmbeddingBatch, SparseVector
from auralynq.embeddings.hashing import _SPARSE_SPACE, _token_hash
from auralynq.telemetry import get_logger
from auralynq.utils import tokenize

_log = get_logger("auralynq.embeddings.openai")

# Model → native dimension (used for collection sizing before the first call).
_MODEL_DIM = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


@functools.lru_cache(maxsize=8192)
def _sparse_items(text: str) -> tuple[tuple[int, float], ...]:
    """Cached tokenize+hash for the lexical vector (the per-call hot work)."""
    import math
    from collections import Counter

    return tuple(
        (_token_hash(tok, "sparse") % _SPARSE_SPACE, 1.0 + math.log(tf))
        for tok, tf in Counter(tokenize(text)).items()
    )


def _sparse_of(text: str) -> SparseVector:
    """Hashed bag-of-words lexical vector (mirrors HashingEmbedder.sparse)."""
    # Rebuild the dict each call so callers can't mutate the cached entry.
    return dict(_sparse_items(text))


class OpenAIEmbedder(Embedder):
    name = "openai"

    def __init__(
        self, api_key: str, model: str = "text-embedding-3-small", batch_size: int = 128
    ) -> None:
        from openai import OpenAI

        if not api_key:
            raise ValueError("OpenAIEmbedder requires an API key")
        self._client = OpenAI(api_key=api_key)
        self.model = model
        self.batch_size = batch_size
        self.dim = _MODEL_DIM.get(model, 1536)
        _log.info("openai_embed.init", model=model, dim=self.dim)

    def embed(self, texts: list[str]) -> EmbeddingBatch:
        if not texts:
            return EmbeddingBatch(dense=np.zeros((0, self.dim), dtype=np.float32), sparse=[])
        vectors: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            chunk = texts[i : i + self.batch_size]
            resp = self._client.embeddings.create(model=self.model, input=chunk)
            vectors.extend(d.embedding for d in resp.data)
        dense = np.asarray(vectors, dtype=np.float32)
        self.dim = int(dense.shape[1])
        sparse = [_sparse_of(t) for t in texts]
        return EmbeddingBatch(dense=dense, sparse=sparse)
