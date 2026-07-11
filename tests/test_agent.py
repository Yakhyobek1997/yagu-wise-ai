from __future__ import annotations

import pytest
from auralynq.agent.cache import SemanticCache
from auralynq.agent.runner import answer_question, stream_answer_question
from auralynq.pipeline import build_index


@pytest.fixture
def indexed(corpus_dir):
    build_index(corpus_dir)
    # caches are process-global; clear between tests
    from auralynq.agent import runner

    runner._CACHE.clear()
    return corpus_dir


def test_answer_simple_question_is_grounded(indexed):
    res = answer_question("What is the capital of France?")
    assert res.answer
    assert res.citations, "grounded answer must have citations"
    assert res.route in ("fast", "hybrid", "graph")
    # every citation marker maps to a real source/locator
    for c in res.citations:
        assert c["source"] and "marker" in c


def test_relational_question_routes_to_graph_or_hybrid(indexed):
    res = answer_question("How is Paris connected to France and Europe through their relationship?")
    assert res.route in ("graph", "hybrid")
    # path evidence should be populated when PathRAG runs
    if res.route in ("graph", "hybrid"):
        assert isinstance(res.path_evidence, list)


def test_trace_has_all_core_nodes(indexed):
    res = answer_question("What is PathRAG?")
    names = {span["name"] for span in res.trace}
    assert {
        "planner",
        "router",
        "context_fusion",
        "synthesizer",
        "self_check",
        "citation_validator",
    } <= names


def test_citation_validator_strips_dangling_markers(indexed):
    res = answer_question("What is the capital of France?")
    import re

    markers = {int(m) for m in re.findall(r"\[(\d+)\]", res.answer)}
    assert all(1 <= m <= max(len(res.citations), 1) for m in markers) or not markers


def test_semantic_cache_hit():
    cache = SemanticCache(threshold=0.9)
    cache.store("what is pathrag", "PathRAG is graph retrieval. [1]", [{"marker": 1}])
    hit = cache.lookup("what is pathrag")
    assert hit is not None
    assert hit[0].startswith("PathRAG")


def test_streaming_yields_tokens_and_final(indexed):
    events = list(stream_answer_question("What is the capital of France?"))
    types = [e["type"] for e in events]
    assert types[0] == "meta"
    assert "token" in types
    assert types[-1] == "final"
    final = events[-1]
    assert "answer" in final and "citations" in final
