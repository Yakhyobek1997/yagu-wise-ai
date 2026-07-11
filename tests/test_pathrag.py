from __future__ import annotations

import pytest
from auralynq.embeddings import get_embedder
from auralynq.ingest.models import Chunk, SourceType
from auralynq.retrieval.pathrag.builder import build_from_chunks
from auralynq.retrieval.pathrag.retriever import PathRAGRetriever
from auralynq.vectorstore.memory_store import MemoryStore


@pytest.fixture
def graph_and_store(tmp_path):
    chunks = [
        Chunk(
            id="c0",
            doc_id="d",
            ordinal=0,
            source="geo.txt",
            source_type=SourceType.text,
            text="Paris is the capital of France. France is located in Europe.",
        ),
        Chunk(
            id="c1",
            doc_id="d",
            ordinal=1,
            source="geo2.txt",
            source_type=SourceType.text,
            text="France is located in Europe. Europe contains many countries.",
        ),
        Chunk(
            id="c2",
            doc_id="d",
            ordinal=2,
            source="geo3.txt",
            source_type=SourceType.text,
            text="The Seine flows through Paris.",
        ),
    ]
    kg = build_from_chunks(chunks)
    emb = get_embedder()
    store = MemoryStore(path=tmp_path / "ms")
    store.upsert(chunks, emb.embed([c.text for c in chunks]))
    return kg, store


def test_seed_entities_found(graph_and_store):
    kg, store = graph_and_store
    r = PathRAGRetriever(kg, store=store)
    seeds = r.seed_entities("Tell me about Paris and France")
    assert seeds


def test_pathrag_returns_paths_and_chunks(graph_and_store):
    kg, store = graph_and_store
    r = PathRAGRetriever(kg, store=store, max_hops=3)
    res = r.retrieve("How is Paris connected to Europe through France?", k=5)
    assert res.method == "pathrag"
    assert res.metadata["seeds"]
    assert res.metadata["paths"], "expected at least one relational path"
    # Paths should be reliability-scored and rendered to text.
    first = res.metadata["paths"][0]
    assert "reliability" in first and first["text"]


def test_pathrag_flow_pruning_bounds_paths(graph_and_store):
    kg, store = graph_and_store
    r = PathRAGRetriever(kg, store=store, max_paths=2)
    res = r.retrieve("Paris France Europe relationship", k=5)
    assert len(res.metadata["paths"]) <= 2


def test_pathrag_empty_graph_is_safe(tmp_path):
    from auralynq.retrieval.pathrag.graph import KnowledgeGraph

    r = PathRAGRetriever(KnowledgeGraph(), store=MemoryStore(path=tmp_path / "ms"))
    res = r.retrieve("anything at all", k=5)
    assert res.chunks == []
    assert res.metadata["paths"] == []
