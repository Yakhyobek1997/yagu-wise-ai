from __future__ import annotations

import pytest
from auralynq.embeddings import get_embedder
from auralynq.ingest.models import Chunk, SourceType
from auralynq.retrieval.hybrid.fusion import reciprocal_rank_fusion
from auralynq.retrieval.hybrid.mmr import mmr_rerank
from auralynq.retrieval.hybrid.reorder import lost_in_the_middle_reorder
from auralynq.retrieval.hybrid.rerank import LexicalReranker
from auralynq.retrieval.hybrid.retriever import HybridRetriever
from auralynq.retrieval.models import ScoredChunk
from auralynq.retrieval.naive import NaiveRetriever
from auralynq.retrieval.router import Route, route_query
from auralynq.vectorstore.memory_store import MemoryStore


@pytest.fixture
def store(tmp_path, sample_chunks):
    emb = get_embedder()
    s = MemoryStore(path=tmp_path / "ms")
    s.upsert(sample_chunks, emb.embed([c.text for c in sample_chunks]))
    return s


def _sc(cid, text, score):
    return ScoredChunk(
        chunk=Chunk(id=cid, doc_id="d", text=text, source_type=SourceType.text), score=score
    )


def test_rrf_combines_rankings():
    a = [_sc("1", "x", 0.9), _sc("2", "y", 0.5)]
    b = [_sc("2", "y", 0.8), _sc("3", "z", 0.4)]
    fused = reciprocal_rank_fusion([a, b], k=60)
    ids = [c.chunk.id for c in fused]
    assert ids[0] == "2"  # appears high in both
    assert set(ids) == {"1", "2", "3"}


def test_reorder_places_best_at_edges():
    chunks = [_sc(str(i), f"t{i}", 1.0 - i * 0.1) for i in range(5)]
    out = lost_in_the_middle_reorder(chunks)
    assert out[0].chunk.id == "0"  # most relevant at the front
    assert out[-1].chunk.id == "1"  # second most relevant at the end


def test_mmr_reduces_redundancy():
    emb = get_embedder()
    cands = [
        _sc("a", "flow pruning paths", 1.0),
        _sc("b", "flow pruning paths", 0.9),
        _sc("c", "paris france capital", 0.8),
    ]
    q = emb.embed_query("flow pruning")
    out = mmr_rerank(q.dense, cands, emb, k=2, lambda_mult=0.5)
    ids = {c.chunk.id for c in out}
    assert "c" in ids  # diversity pulls in the dissimilar chunk


def test_mmr_caches_candidate_embeddings():
    # Repeated MMR over the same candidate texts must not re-embed them: a perf
    # guard for the bounded per-text embedding cache.
    import numpy as np
    from auralynq.embeddings.base import EmbeddingBatch

    class CountingEmbedder:
        model = "counting"

        def __init__(self) -> None:
            self.embedded = 0

        def embed(self, texts: list[str]) -> EmbeddingBatch:
            self.embedded += len(texts)
            rng = np.random.default_rng(7)
            return EmbeddingBatch(
                dense=rng.standard_normal((len(texts), 8)).astype("float32"),
                sparse=[{} for _ in texts],
            )

    emb = CountingEmbedder()
    cands = [_sc("a", "alpha beta", 1.0), _sc("b", "gamma delta", 0.9)]
    q = np.zeros(8, dtype="float32")
    mmr_rerank(q, cands, emb, k=2)  # first pass embeds both
    assert emb.embedded == 2
    mmr_rerank(q, cands, emb, k=2)  # second pass fully cached
    assert emb.embedded == 2


def test_lexical_reranker_orders_by_overlap():
    rr = LexicalReranker()
    chunks = [_sc("a", "the cat sat", 0.1), _sc("b", "flow based pruning of paths", 0.1)]
    out = rr.rerank("flow pruning paths", chunks, k=2)
    assert out[0].chunk.id == "b"


def test_naive_retriever(store):
    r = NaiveRetriever(store=store)
    res = r.retrieve("flow based pruning", k=3)
    assert res.method == "naive"
    assert res.chunks


def test_hybrid_retriever_pipeline(store):
    r = HybridRetriever(store=store)
    res = r.retrieve("flow based pruning of relational paths", k=3)
    assert res.method == "hybrid"
    assert 0 < len(res.chunks) <= 3
    assert "rrf" in res.metadata
    assert res.metadata.get("reorder") == "lost_in_the_middle"


def test_router_simple_vs_relational():
    simple = route_query("What is Paris?")
    assert simple.route == Route.fast
    relational = route_query(
        "How does the relationship between Paris and France connect through Europe?"
    )
    assert relational.route in (Route.graph, Route.hybrid)
