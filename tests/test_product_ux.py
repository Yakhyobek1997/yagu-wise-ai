"""Tests for the product-quality layer: corpus-aware suggestions, structured
insufficient-evidence responses, trace-step serialization, evidence coverage and
the new status/corpus/observability endpoints."""

from __future__ import annotations

import pytest
from auralynq.pipeline import build_index
from auralynq.serving.app import create_app
from auralynq.serving.corpus import (
    corpus_summary,
    detect_entities,
    suggested_questions,
)
from auralynq.serving.observability import to_trace_steps, trace_summary
from fastapi.testclient import TestClient


@pytest.fixture
def client(corpus_dir):
    build_index(corpus_dir)
    from auralynq.agent import runner

    runner._CACHE.clear()
    return TestClient(create_app())


# --------------------------------------------------------------- corpus ----
def test_corpus_summary_reports_indexed(corpus_dir):
    build_index(corpus_dir)
    s = corpus_summary()
    assert s["indexed"] is True
    assert s["vector_count"] > 0
    assert s["entity_count"] > 0
    # Entities come from the actual corpus (PathRAG / France / …), not stale chips.
    names = {e["name"].lower() for e in s["top_entities"]}
    assert any("path" in n or "france" in n or "paris" in n for n in names)


def test_corpus_summary_reports_languages(corpus_dir):
    build_index(corpus_dir)
    s = corpus_summary()
    # Latin/English corpus → at least one language label, and the inventory
    # fields the UI renders are always present.
    assert "languages" in s and isinstance(s["languages"], list)
    assert "failed_files" in s and isinstance(s["failed_files"], list)
    assert s["languages"], "expected a detected language for an indexed corpus"


def test_detect_script_identifies_arabic():
    from auralynq.serving.corpus import _detect_script

    assert _detect_script("مرحبا هذا نص عربي طويل بما فيه الكفاية") == "Arabic"
    assert _detect_script("Hello, this is plain English text") is None
    assert _detect_script("Привет мир, как дела сегодня") == "Cyrillic"


def test_suggestions_are_corpus_aware(corpus_dir):
    build_index(corpus_dir)
    s = corpus_summary()
    qs = suggested_questions(3, s)
    assert 1 <= len(qs) <= 3
    top = s["top_entities"][0]["name"]
    # The strongest entity should drive at least one suggestion.
    assert any(top.split()[0].lower() in q.lower() for q in qs)


def test_suggestions_neutral_when_empty():
    # No index built in this test → corpus-neutral fallbacks, never geography chips.
    qs = suggested_questions(3, {"top_entities": []})
    assert len(qs) >= 1
    assert all("paris" not in q.lower() for q in qs)


def test_detect_entities_matches_corpus(corpus_dir):
    build_index(corpus_dir)
    s = corpus_summary()
    found = detect_entities("How are Paris and France related?", s)
    assert any("france" in f.lower() or "paris" in f.lower() for f in found)


# -------------------------------------------------------- trace steps ------
def test_to_trace_steps_serialization():
    raw = [
        {"name": "planner", "duration_ms": 1.0, "attributes": {}, "events": []},
        {
            "name": "evidence_gap_critic",
            "duration_ms": 2.0,
            "attributes": {"coverage": 0.2, "need_rewrite": True},
            "events": [],
        },
        {
            "name": "synthesizer",
            "duration_ms": 5.0,
            "attributes": {"provider": "extractive"},
            "events": [{"event": "exception", "error": "boom"}],
        },
    ]
    steps = to_trace_steps(raw)
    assert [s["label"] for s in steps] == [
        "Query planning",
        "Evidence sufficiency check",
        "Answer generation",
    ]
    assert steps[1]["status"] == "warning"  # low coverage / need_rewrite
    assert steps[2]["status"] == "failed"  # exception event
    assert steps[2]["provider"] == "extractive"
    assert steps[2]["warnings"]


def test_trace_summary_risk_buckets():
    raw = [
        {"name": "hybrid_retrieve", "duration_ms": 10.0, "attributes": {}, "events": []},
        {"name": "synthesizer", "duration_ms": 20.0, "attributes": {}, "events": []},
    ]
    answered = trace_summary(
        raw, route="fast", confidence=0.8, evidence_coverage=0.9, insufficient=False
    )
    assert answered["hallucination_risk"] == "low"
    assert answered["retrieval_latency_ms"] == 10.0
    assert answered["generation_latency_ms"] == 20.0
    assert answered["total_latency_ms"] == 30.0

    abstained = trace_summary(
        raw, route="fast", confidence=0.0, evidence_coverage=0.0, insufficient=True
    )
    assert abstained["hallucination_risk"] == "none"
    assert abstained["abstained"] is True


# ---------------------------------------------------- endpoints ------------
def test_status_endpoint(client):
    r = client.get("/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["corpus"]["indexed"] is True
    assert "tracing" in body
    assert any(p["subsystem"] == "llm" for p in body["providers"])


def test_corpus_summary_endpoint(client):
    r = client.get("/corpus/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["indexed_document_count"] >= 1
    assert body["entity_count"] >= 1


def test_suggestions_endpoint(client):
    r = client.get("/suggestions?limit=3")
    assert r.status_code == 200
    body = r.json()
    assert body["corpus_indexed"] is True
    assert 1 <= len(body["suggestions"]) <= 3


def test_observability_summary_endpoint(client):
    client.get("/health")
    r = client.get("/observability/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["requests_total"] >= 1
    assert "tracing_provider" in body


# ----------------------------------------- structured query response -------
def test_query_has_structured_fields(client):
    r = client.post("/query", json={"question": "What is PathRAG?"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"answered", "insufficient_evidence"}
    assert "evidence_coverage" in body
    assert isinstance(body["trace_steps"], list) and body["trace_steps"]
    assert isinstance(body["suggested_questions"], list)
    assert isinstance(body["provider_status"], list)


def test_insufficient_evidence_shape(client):
    # A question with no supporting evidence in this tiny corpus should abstain
    # and return a structured, trustworthy reason (not just a string).
    r = client.post(
        "/query",
        json={"question": "What were the quarterly revenue figures for Acme Corp in 2019?"},
    )
    assert r.status_code == 200
    body = r.json()
    if body["status"] == "insufficient_evidence":
        reason = body["insufficient_evidence_reason"]
        assert reason is not None
        assert "summary" in reason
        assert "route_attempted" in reason
        assert "why_insufficient" in reason
        assert isinstance(reason["suggested_questions"], list)
        assert isinstance(reason["detected_entities"], list)
        assert isinstance(reason["suggest_ingest"], bool)
    else:
        # If the extractive fallback still answered, the contract must hold:
        # no insufficient reason attached to a normal answer.
        assert body["insufficient_evidence_reason"] is None


def test_stream_final_carries_structured_fields(client):
    import json

    with client.stream("POST", "/query/stream", json={"question": "What is PathRAG?"}) as r:
        assert r.status_code == 200
        finals = []
        for line in r.iter_lines():
            if line and line.startswith("data:"):
                payload = json.loads(line[len("data:") :].strip())
                if payload.get("type") == "final":
                    finals.append(payload)
    assert finals
    final = finals[-1]
    assert "status" in final
    assert final.get("trace_steps")
    assert "evidence_coverage" in final
    assert "suggested_questions" in final
