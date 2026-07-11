from __future__ import annotations

from auralynq.embeddings import get_embedder
from auralynq.retrieval.models import Filter
from auralynq.vectorstore.memory_store import MemoryStore


def _populate(tmp_path, chunks):
    emb = get_embedder()
    batch = emb.embed([c.text for c in chunks])
    store = MemoryStore(path=tmp_path / "ms")
    store.upsert(chunks, batch)
    return store, emb


def test_upsert_and_count(tmp_path, sample_chunks):
    store, _ = _populate(tmp_path, sample_chunks)
    assert store.count() == len(sample_chunks)


def test_hybrid_search_returns_relevant(tmp_path, sample_chunks):
    store, emb = _populate(tmp_path, sample_chunks)
    q = emb.embed_query("flow based pruning of relational paths")
    res = store.search(q, k=3)
    assert res
    assert "pruning" in res[0].chunk.text.lower() or "path" in res[0].chunk.text.lower()
    assert res[0].method == "hybrid"


def test_dense_and_sparse_primitives(tmp_path, sample_chunks):
    store, emb = _populate(tmp_path, sample_chunks)
    q = emb.embed_query("reciprocal rank fusion")
    dense = store.search_dense(q.dense, 3)
    sparse = store.search_sparse(q.sparse, 3)
    assert dense and dense[0].method == "dense"
    assert sparse and sparse[0].method == "sparse"


def test_metadata_filter(tmp_path, sample_chunks):
    store, emb = _populate(tmp_path, sample_chunks)
    q = emb.embed_query("anything")
    res = store.search_dense(q.dense, 10, filt=Filter(doc_ids=["nope"]))
    assert res == []


def test_persistence_roundtrip(tmp_path, sample_chunks):
    store, emb = _populate(tmp_path, sample_chunks)
    store.save()
    reloaded = MemoryStore(path=tmp_path / "ms")
    assert reloaded.count() == len(sample_chunks)
    q = emb.embed_query("paris france")
    assert reloaded.search(q, k=1)
