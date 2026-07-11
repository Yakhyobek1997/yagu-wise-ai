"""Naive baseline retriever: single dense vector search, no fusion/rerank."""

from __future__ import annotations

import time

from auralynq.embeddings.base import Embedder
from auralynq.embeddings.factory import get_embedder
from auralynq.retrieval.base import Retriever
from auralynq.retrieval.models import Filter, RetrievalResult
from auralynq.vectorstore.base import VectorStore
from auralynq.vectorstore.factory import get_store


class NaiveRetriever(Retriever):
    name = "naive"

    def __init__(self, store: VectorStore | None = None, embedder: Embedder | None = None) -> None:
        self.store = store or get_store()
        self.embedder = embedder or get_embedder()

    def retrieve(self, query: str, k: int, filt: Filter | None = None) -> RetrievalResult:
        t0 = time.perf_counter()
        q = self.embedder.embed_query(query)
        chunks = self.store.search_dense(q.dense, k, filt)
        return RetrievalResult(
            query=query, method=self.name, chunks=chunks, took_ms=(time.perf_counter() - t0) * 1000
        )
