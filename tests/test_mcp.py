from __future__ import annotations

import pytest
from auralynq.mcp_server.tools import (
    TOOLS,
    graph_path_query,
    ingest_documents,
    search,
    talk_to_data,
)
from auralynq.pipeline import build_index


@pytest.fixture
def indexed(corpus_dir):
    build_index(corpus_dir)
    from auralynq.agent import runner

    runner._CACHE.clear()
    return corpus_dir


def test_all_seven_tools_registered():
    assert set(TOOLS) == {
        "ingest_documents",
        "search",
        "graph_path_query",
        "transcribe",
        "talk_to_data",
        "run_eval",
        "get_trace",
    }


def test_search_tool(indexed):
    out = search("flow based pruning", k=3)
    assert out["results"]
    assert "citation" in out["results"][0]


def test_graph_path_query_tool(indexed):
    out = graph_path_query("How are Paris and France related?", k=4)
    assert "paths" in out and "seeds" in out


def test_talk_to_data_tool(indexed):
    out = talk_to_data("What is the capital of France?")
    assert out["answer"]
    assert out["citations"]


def test_ingest_documents_tool(tmp_path):
    (tmp_path / "x.md").write_text("# X\n\nAuralynq indexes Qdrant vectors.", encoding="utf-8")
    out = ingest_documents(str(tmp_path))
    assert out["documents"] >= 1


def test_mcp_transport_resolution(monkeypatch):
    from auralynq.mcp_server.server import _resolve_transport

    monkeypatch.delenv("AURALYNQ_MCP_TRANSPORT", raising=False)
    assert _resolve_transport([]) == "stdio"  # default
    assert _resolve_transport(["--transport", "streamable-http"]) == "streamable-http"
    monkeypatch.setenv("AURALYNQ_MCP_TRANSPORT", "sse")
    assert _resolve_transport([]) == "sse"  # env honored
    # CLI flag overrides env
    assert _resolve_transport(["--transport", "stdio"]) == "stdio"
    import pytest

    with pytest.raises(SystemExit):
        _resolve_transport(["--transport", "carrier-pigeon"])
