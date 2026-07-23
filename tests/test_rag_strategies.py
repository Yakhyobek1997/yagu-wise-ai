"""Tests for the RAG strategy registry and new endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from yaguwiseai.serving.app import create_app

    return TestClient(create_app())


def test_strategy_registry_lists_all():
    from yaguwiseai.rag import get_registry

    registry = get_registry()
    strategies = registry.list_all()
    assert len(strategies) >= 13
    ids = {s["id"] for s in strategies}
    assert "yaguwiseai_rag" in ids
    assert "naive_vector" in ids
    assert "hybrid" in ids
    assert "graph_rag" in ids
    assert "raptor" in ids


def test_strategy_registry_default_is_yaguwiseai_rag():
    from yaguwiseai.rag import get_registry

    registry = get_registry()
    assert registry.default_strategy_id == "yaguwiseai_rag"


def test_available_strategy_has_no_unavailable_reason():
    from yaguwiseai.rag import get_registry

    registry = get_registry()
    strategies = registry.list_all()
    yaguwiseai = next(s for s in strategies if s["id"] == "yaguwiseai_rag")
    assert yaguwiseai["available"] is True
    assert yaguwiseai["unavailable_reason"] is None


def test_planned_strategy_has_unavailable_reason():
    from yaguwiseai.rag import get_registry

    registry = get_registry()
    strategies = registry.list_all()
    raptor = next(s for s in strategies if s["id"] == "raptor")
    assert raptor["available"] is False
    assert raptor["unavailable_reason"] is not None
    assert len(raptor["unavailable_reason"]) > 0


def test_unknown_strategy_fallback():
    from yaguwiseai.rag import get_registry

    registry = get_registry()
    # Should fall back to yaguwiseai_rag, but we don't call run() in unit test
    strategy = registry.get("nonexistent_id")
    assert strategy is None


def test_get_rag_strategies_endpoint(client):
    resp = client.get("/rag/strategies")
    assert resp.status_code == 200
    data = resp.json()
    assert "strategies" in data
    assert "default_strategy" in data
    assert data["default_strategy"] == "yaguwiseai_rag"
    assert len(data["strategies"]) >= 13


def test_eval_last_returns_pending_before_query(client):
    resp = client.get("/eval/last")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "pending"


def test_eval_feedback_endpoint(client):
    resp = client.post(
        "/eval/feedback",
        json={"answer_rating": 4, "citation_correct": True, "notes": "test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "recorded"
    assert data["total"] >= 1


def test_eval_summary_endpoint(client):
    # Post some feedback first
    client.post("/eval/feedback", json={"answer_rating": 5})
    resp = client.get("/eval/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_feedback" in data


def test_eval_export_run_endpoint(client):
    resp = client.post("/eval/export-run")
    assert resp.status_code == 200
    data = resp.json()
    assert "last_eval" in data
    assert "feedback" in data


def test_strategy_info_has_required_fields():
    from yaguwiseai.rag import get_registry

    registry = get_registry()
    for s in registry.list_all():
        assert "id" in s
        assert "name" in s
        assert "description" in s
        assert "status" in s
        assert s["status"] in ("available", "experimental", "planned")
        assert "available" in s
        assert "expected_latency" in s
        assert s["expected_latency"] in ("fast", "medium", "slow")


def test_hybrid_strategy_available():
    from yaguwiseai.rag import get_registry

    registry = get_registry()
    strategies = registry.list_all()
    hybrid = next(s for s in strategies if s["id"] == "hybrid")
    assert hybrid["available"] is True
    assert hybrid["status"] == "available"


def test_hybrid_rerank_requires_reranker():
    from yaguwiseai.rag import get_registry

    registry = get_registry()
    strategies = registry.list_all()
    hr = next(s for s in strategies if s["id"] == "hybrid_rerank")
    # Without reranker enabled, should be unavailable
    assert "reranker" in hr["required_features"]
