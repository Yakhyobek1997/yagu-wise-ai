"""Vector store interface.

Stores expose dense and sparse search as *separate* primitives so the retrieval
layer can fuse them with Reciprocal Rank Fusion, plus a convenience weighted
hybrid search. Metadata filtering is supported via :class:`Filter`.
"""

from __future__ import annotations

import abc

from auralynq.embeddings.base import Embedding, EmbeddingBatch, SparseVector
from auralynq.ingest.models import Chunk
from auralynq.retrieval.models import Filter, ScoredChunk


class VectorStore(abc.ABC):
    backend: str = "base"

    @abc.abstractmethod
    def ensure_collection(self, dim: int) -> None: ...

    @abc.abstractmethod
    def upsert(self, chunks: list[Chunk], embeddings: EmbeddingBatch) -> int: ...

    @abc.abstractmethod
    def search_dense(self, dense, k: int, filt: Filter | None = None) -> list[ScoredChunk]: ...

    @abc.abstractmethod
    def search_sparse(
        self, sparse: SparseVector, k: int, filt: Filter | None = None
    ) -> list[ScoredChunk]: ...

    @abc.abstractmethod
    def count(self) -> int: ...

    @abc.abstractmethod
    def clear(self) -> None: ...

    def delete_by_doc_id(self, doc_id: str) -> int:
        """Remove all chunks belonging to *doc_id*. Returns number deleted."""
        return 0

    def get(self, chunk_id: str) -> Chunk | None:
        """Resolve a chunk by id (used by PathRAG to cite path provenance)."""
        return None

    def all_chunks(self) -> list[Chunk]:
        """Return every stored chunk (used to rebuild the KG over the full set)."""
        return []

    def search(
        self,
        query: Embedding,
        k: int,
        filt: Filter | None = None,
        dense_weight: float = 0.6,
        sparse_weight: float = 0.4,
    ) -> list[ScoredChunk]:
        """Convenience weighted-sum hybrid search (min-max normalised)."""
        dense = self.search_dense(query.dense, k * 2, filt)
        sparse = self.search_sparse(query.sparse, k * 2, filt)
        fused: dict[str, ScoredChunk] = {}

        def _norm(items: list[ScoredChunk]) -> dict[str, float]:
            if not items:
                return {}
            scores = [c.score for c in items]
            lo, hi = min(scores), max(scores)
            rng = (hi - lo) or 1.0
            return {c.chunk.id: (c.score - lo) / rng for c in items}

        dn, sn = _norm(dense), _norm(sparse)
        for c in dense + sparse:
            cid = c.chunk.id
            if cid not in fused:
                score = dense_weight * dn.get(cid, 0.0) + sparse_weight * sn.get(cid, 0.0)
                fused[cid] = c.model_copy(update={"score": score, "method": "hybrid"})
        ranked = sorted(fused.values(), key=lambda c: c.score, reverse=True)[:k]
        for i, c in enumerate(ranked):
            c.rank = i
        return ranked
