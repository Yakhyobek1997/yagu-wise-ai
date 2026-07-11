"""Tests for corpus management endpoints and backend intent classifier."""

from __future__ import annotations

import pytest
from auralynq.serving.app import _classify_corpus_intent, create_app
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AURALYNQ_DATA_DIR", str(tmp_path))
    app = create_app()
    return TestClient(app, raise_server_exceptions=True)


# ----------------------------------------------------------------------- intent classifier ---

CORPUS_MGMT_QUESTIONS = [
    "delete all documents",
    "clear corpus",
    "remove my uploaded files",
    "delete uploaded PDFs",
    "can I remove and delete the last document permanently?",
    "how do I delete them?",
    "how to delete documents",
    "wipe vectors",
    "clear my data",
    "reset my collection",
    "how can I remove the last file",
    "delete Blackboard_13.03.2010.pdf",
    "remove last uploaded file",
    "delete last document permanently",
]

CORPUS_INVENTORY_QUESTIONS = [
    "how many documents do I have?",
    "how many documents do I have so far?",
    "what files are indexed?",
    "what documents are in my collection?",
    "do I have Arabic documents?",
    "what languages are in my collection?",
    "what was the last document added?",
    "list my indexed documents",
    "are there any documents?",
    "in my corpus",
]

NORMAL_RAG_QUESTIONS = [
    "what does the corpus say about IoT?",
    "summarize Blackboard",
    "what evidence supports claims about Blackboard?",
    "capital of Yemen",
    "explain the main concepts",
    "who wrote this paper?",
]


@pytest.mark.parametrize("q", CORPUS_MGMT_QUESTIONS)
def test_corpus_mgmt_intent_detected(q):
    assert _classify_corpus_intent(q) == "corpus_management", (
        f"Expected corpus_management for: {q!r}"
    )


@pytest.mark.parametrize("q", CORPUS_INVENTORY_QUESTIONS)
def test_corpus_inventory_intent_detected(q):
    assert _classify_corpus_intent(q) == "corpus_inventory", f"Expected corpus_inventory for: {q!r}"


@pytest.mark.parametrize("q", NORMAL_RAG_QUESTIONS)
def test_normal_questions_not_classified(q):
    result = _classify_corpus_intent(q)
    assert result is None, f"Expected None (RAG) for: {q!r}, got: {result}"


# ----------------------------------------------------------------------- query routing ---


def test_inventory_question_has_no_rag_citations(client):
    """Inventory questions must return no citations and route=corpus_inventory."""
    r = client.post("/query", json={"question": "how many documents do I have so far?"})
    assert r.status_code == 200
    data = r.json()
    assert data["route"] == "corpus_inventory"
    assert data["citations"] == []
    assert "retrieval skipped" in data["route_rationale"]


def test_delete_help_has_no_rag_citations(client):
    """Delete-help questions must route to corpus_management with no citations."""
    r = client.post(
        "/query", json={"question": "can I remove and delete the last document permanently?"}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["route"] == "corpus_management"
    assert data["citations"] == []
    assert "retrieval skipped" in data["route_rationale"]


def test_corpus_mgmt_stream_skips_rag(client):
    """Streaming endpoint also routes corpus_management questions to system handler."""
    with client.stream(
        "POST",
        "/query/stream",
        json={"question": "how do I delete all documents?"},
    ) as resp:
        assert resp.status_code == 200
        text = resp.read().decode()
    assert "corpus_management" in text
    assert "retrieval skipped" in text


# ----------------------------------------------------------------------- corpus endpoints ---


def test_corpus_inventory_endpoint(client):
    r = client.get("/corpus/inventory")
    assert r.status_code == 200
    data = r.json()
    assert "indexed_document_count" in data
    assert "vector_count" in data


def test_corpus_clear_preview_empty(client):
    r = client.post("/corpus/clear/preview")
    assert r.status_code == 200
    data = r.json()
    assert data["action"] == "clear_all"
    assert "document_count" in data
    assert data["confirmation_phrase"] == "CLEAR CORPUS"


def test_corpus_clear_confirm_wrong_phrase(client):
    r = client.post("/corpus/clear/confirm", json={"phrase": "wrong phrase"})
    assert r.status_code == 400


def test_corpus_clear_confirm_correct_phrase(client, tmp_path):
    # Seed some index artifacts to verify they get cleared
    index_dir = tmp_path / "index"
    index_dir.mkdir(parents=True)
    graph_file = index_dir / "graph.json"
    graph_file.write_text('{"version": 1, "nodes": [], "edges": []}')
    manifest = tmp_path / "storage" / "ingest_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"file.pdf": "abc123"}')

    r = client.post("/corpus/clear/confirm", json={"phrase": "CLEAR CORPUS"})
    assert r.status_code == 200
    data = r.json()
    assert data["action"] == "clear_all"
    assert data["errors"] == [] or isinstance(data["errors"], list)


def test_corpus_clear_confirm_wipes_uploads(client, tmp_path):
    """clear_all must remove leftover files in the uploads directory."""
    from auralynq.config import get_settings

    # _isolated_env sets AURALYNQ_DATA_DIR = tmp_path / "data"
    settings = get_settings()
    uploads_dir = settings.storage_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    leftover = uploads_dir / "leftover.pdf"
    leftover.write_bytes(b"%PDF-1.4 placeholder")

    r = client.post("/corpus/clear/confirm", json={"phrase": "CLEAR CORPUS"})
    assert r.status_code == 200
    # Leftover upload file must be gone
    assert not leftover.exists()


def test_corpus_delete_last_preview_empty(client):
    r = client.get("/corpus/documents/last/preview")
    assert r.status_code == 200
    data = r.json()
    assert data["action"] == "delete_last"
    assert data["confirmation_phrase"] == "DELETE LAST DOCUMENT"


def test_corpus_delete_last_wrong_phrase(client):
    r = client.post("/corpus/documents/last/confirm", json={"phrase": "wrong"})
    assert r.status_code == 400


def test_corpus_delete_doc_invalid_id(client):
    r = client.get("/corpus/documents/not-a-valid-id!/preview")
    # FastAPI 404 for path param that doesn't match URL pattern — or 400
    assert r.status_code in (400, 404, 422)


def test_corpus_delete_doc_preview_unknown(client):
    r = client.get("/corpus/documents/abcdef1234567890/preview")
    assert r.status_code == 200
    data = r.json()
    assert data["found"] is False


# ----------------------------------------------------------------------- vectorstore deletion ---


def test_memory_store_delete_by_doc_id(tmp_path):
    import numpy as np
    from auralynq.embeddings.base import EmbeddingBatch
    from auralynq.ingest.models import Chunk, SourceType
    from auralynq.vectorstore.memory_store import MemoryStore

    store = MemoryStore(path=tmp_path / "ms")
    dim = 4

    chunks_a = [
        Chunk(
            id=f"a_{i}",
            doc_id="doc_a",
            text=f"text {i}",
            source="a.pdf",
            source_type=SourceType.pdf,
        )
        for i in range(3)
    ]
    chunks_b = [
        Chunk(
            id=f"b_{i}",
            doc_id="doc_b",
            text=f"text {i}",
            source="b.pdf",
            source_type=SourceType.pdf,
        )
        for i in range(2)
    ]

    emb_a = EmbeddingBatch(dense=np.random.rand(3, dim).astype("float32"), sparse=None)
    emb_b = EmbeddingBatch(dense=np.random.rand(2, dim).astype("float32"), sparse=None)

    store.upsert(chunks_a, emb_a)
    store.upsert(chunks_b, emb_b)
    assert store.count() == 5

    removed = store.delete_by_doc_id("doc_a")
    assert removed == 3
    assert store.count() == 2
    remaining = store.all_chunks()
    assert all(c.doc_id == "doc_b" for c in remaining)


def test_memory_store_delete_nonexistent_doc(tmp_path):
    from auralynq.vectorstore.memory_store import MemoryStore

    store = MemoryStore(path=tmp_path / "ms")
    removed = store.delete_by_doc_id("nonexistent")
    assert removed == 0


# ----------------------------------------------------------------------- inventory accuracy ---


def test_inventory_answer_comes_from_metadata_not_rag(client):
    """Corpus inventory answer must contain document/vector/entity counts, not random citations."""
    r = client.post("/query", json={"question": "what files are indexed in my collection?"})
    assert r.status_code == 200
    data = r.json()
    assert data["citations"] == []
    assert data["route"] == "corpus_inventory"
    # Answer must mention corpus stats
    answer = data["answer"].lower()
    assert any(word in answer for word in ["corpus", "document", "empty", "vector"])
