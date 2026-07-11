"""Hybrid retriever: dense+sparse → RRF → cross-encoder rerank → MMR → reorder.

This is the 'fast path' the adaptive router uses for simple queries. Each stage
is optional/composable and recorded in the result metadata for the trace panel.
"""

from __future__ import annotations

import time

from auralynq.config import get_settings
from auralynq.embeddings.base import Embedder
from auralynq.embeddings.factory import get_embedder
from auralynq.retrieval.base import Retriever
from auralynq.retrieval.hybrid.fusion import reciprocal_rank_fusion
from auralynq.retrieval.hybrid.mmr import mmr_rerank
from auralynq.retrieval.hybrid.reorder import lost_in_the_middle_reorder
from auralynq.retrieval.hybrid.rerank import Reranker, build_reranker
from auralynq.retrieval.models import Filter, RetrievalResult
from auralynq.vectorstore.base import VectorStore
from auralynq.vectorstore.factory import get_store


class HybridRetriever(Retriever):
    name = "hybrid"

    def __init__(
        self,
        store: VectorStore | None = None,
        embedder: Embedder | None = None,
        reranker: Reranker | None = None,
        *,
        use_rerank: bool = True,
        use_mmr: bool = True,
        use_reorder: bool = True,
    ) -> None:
        self.store = store or get_store()
        self.embedder = embedder or get_embedder()
        self.reranker = reranker or build_reranker()
        self.use_rerank = use_rerank
        self.use_mmr = use_mmr
        self.use_reorder = use_reorder

    def retrieve(self, query: str, k: int, filt: Filter | None = None) -> RetrievalResult:
        s = get_settings()
        t0 = time.perf_counter()
        q = self.embedder.embed_query(query)
        pool = max(k * 4, s.retrieval.top_k)

        dense = self.store.search_dense(q.dense, pool, filt)
        sparse = self.store.search_sparse(q.sparse, pool, filt)

        fused = reciprocal_rank_fusion(
            [dense, sparse],
            k=s.retrieval.rrf_k,
            weights=[s.retrieval.dense_weight, s.retrieval.sparse_weight],
        )
        stages: dict[str, object] = {
            "dense": len(dense),
            "sparse": len(sparse),
            "rrf": len(fused),
        }

        candidates = fused[: max(k * 3, k)]
        if self.use_rerank and candidates:
            candidates = self.reranker.rerank(query, candidates, k=max(k * 2, k))
            stages["rerank"] = self.reranker.name

        if self.use_mmr and candidates:
            candidates = mmr_rerank(
                q.dense, candidates, self.embedder, k=k, lambda_mult=s.retrieval.mmr_lambda
            )
            stages["mmr"] = len(candidates)
        else:
            candidates = candidates[:k]

        if self.use_reorder:
            candidates = lost_in_the_middle_reorder(candidates)
            stages["reorder"] = "lost_in_the_middle"

        return RetrievalResult(
            query=query,
            method=self.name,
            chunks=candidates,
            took_ms=(time.perf_counter() - t0) * 1000,
            metadata=stages,
        )
