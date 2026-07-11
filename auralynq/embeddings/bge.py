"""BAAI/bge-m3 embedder (optional, lazily imported).

bge-m3 natively produces dense + sparse (lexical) weights, which maps directly
onto Auralynq's hybrid retrieval. Requires the ``embeddings`` extra.
"""

from __future__ import annotations

import numpy as np

from auralynq.embeddings.base import Embedder, EmbeddingBatch, SparseVector
from auralynq.telemetry import get_logger

_log = get_logger("auralynq.embeddings.bge")


class BGEM3Embedder(Embedder):
    name = "bge"

    def __init__(self, model: str = "BAAI/bge-m3", device: str = "auto", dim: int = 1024) -> None:
        from FlagEmbedding import BGEM3FlagModel  # type: ignore

        use_fp16 = device != "cpu"
        resolved = None if device == "auto" else device
        self._model = BGEM3FlagModel(model, use_fp16=use_fp16, device=resolved)
        self.dim = dim
        _log.info("bge.loaded", model=model, device=device)

    def embed(self, texts: list[str]) -> EmbeddingBatch:
        out = self._model.encode(
            texts,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense = np.asarray(out["dense_vecs"], dtype=np.float32)
        sparse: list[SparseVector] = []
        for weights in out["lexical_weights"]:
            sparse.append({int(k): float(v) for k, v in weights.items()})
        self.dim = int(dense.shape[1])
        return EmbeddingBatch(dense=dense, sparse=sparse)
