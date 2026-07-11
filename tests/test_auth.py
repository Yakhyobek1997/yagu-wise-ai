from __future__ import annotations

import pytest
from auralynq.config import reload_settings
from auralynq.pipeline import build_index
from auralynq.serving.app import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def secured_client(corpus_dir, monkeypatch):
    build_index(corpus_dir)
    from auralynq.agent import runner

    runner._CACHE.clear()
    monkeypatch.setenv("AURALYNQ_SERVE__API_KEY", "s3cret-token")
    reload_settings()
    return TestClient(create_app())


def test_open_by_default(corpus_dir):
    build_index(corpus_dir)
    app = create_app()  # no API key set -> open
    r = TestClient(app).post("/query", json={"question": "What is the capital of France?"})
    assert r.status_code == 200


def test_health_and_metrics_are_public_even_when_secured(secured_client):
    assert secured_client.get("/health").status_code == 200
    assert secured_client.get("/metrics").status_code == 200


def test_protected_endpoint_requires_token(secured_client):
    r = secured_client.post("/query", json={"question": "hi"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
    assert r.headers.get("WWW-Authenticate") == "Bearer"


def test_valid_token_allows_access(secured_client):
    r = secured_client.post(
        "/query",
        json={"question": "What is the capital of France?"},
        headers={"Authorization": "Bearer s3cret-token"},
    )
    assert r.status_code == 200
    assert r.json()["answer"]


def test_wrong_token_rejected(secured_client):
    r = secured_client.post(
        "/query", json={"question": "hi"}, headers={"Authorization": "Bearer nope"}
    )
    assert r.status_code == 401
