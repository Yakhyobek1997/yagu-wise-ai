"""Tests for LLM and embedder factory auto-resolution and air-gap blocking.

All provider probes (Ollama reachability, SDK presence) are faked so the
resolution logic is exercised deterministically and offline.
"""

from __future__ import annotations

from types import SimpleNamespace

import auralynq.embeddings.factory as embed_factory
import auralynq.llm.factory as llm_factory
from auralynq.embeddings.hashing import HashingEmbedder
from auralynq.llm.fallback import ExtractiveLLM


def _fake_settings(
    llm_provider: str = "auto",
    embed_provider: str = "auto",
    air_gapped: bool = False,
    anthropic_key: str = "",
    openai_key: str = "",
    cohere_key: str = "",
):
    return SimpleNamespace(
        air_gapped=air_gapped,
        anthropic_api_key=anthropic_key,
        openai_api_key=openai_key,
        cohere_api_key=cohere_key,
        huggingface_token="",
        llm=SimpleNamespace(
            provider=llm_provider,
            base_url="http://fake-ollama:11434",
            model="llama3.2:3b",
            slm_repo="fake/repo",
            slm_filename="fake.gguf",
            slm_n_ctx=2048,
            slm_n_gpu_layers=0,
        ),
        embedding=SimpleNamespace(
            provider=embed_provider,
            dim=384,
            ollama_model="nomic-embed-text",
            model="BAAI/bge-m3",
            device="cpu",
        ),
    )


# ── LLM factory ───────────────────────────────────────────────────────────────


def test_model_for_swaps_ollama_tag_for_provider_default():
    assert llm_factory._model_for("openai", "llama3.2:3b") == "gpt-4o-mini"
    assert llm_factory._model_for("anthropic", "qwen2.5:7b") == "claude-3-5-haiku-latest"
    assert llm_factory._model_for("openai", "gpt-4o") == "gpt-4o"
    assert llm_factory._model_for("ollama", "llama3.2:3b") == "llama3.2:3b"


def test_llm_resolved_provider_explicit(monkeypatch):
    monkeypatch.setattr(llm_factory, "get_settings", lambda: _fake_settings("ollama"))
    assert llm_factory.resolved_provider() == "ollama"


def test_llm_resolved_provider_air_gap_blocks_commercial(monkeypatch):
    monkeypatch.setattr(
        llm_factory, "get_settings", lambda: _fake_settings("openai", air_gapped=True)
    )
    assert llm_factory.resolved_provider() == "extractive"


def test_llm_resolved_provider_auto_prefers_ollama(monkeypatch):
    monkeypatch.setattr(llm_factory, "get_settings", lambda: _fake_settings())
    monkeypatch.setattr(llm_factory, "_ollama_reachable", lambda url: True)
    assert llm_factory.resolved_provider() == "ollama"


def test_llm_resolved_provider_auto_falls_to_extractive(monkeypatch):
    monkeypatch.setattr(llm_factory, "get_settings", lambda: _fake_settings())
    monkeypatch.setattr(llm_factory, "_ollama_reachable", lambda url: False)
    monkeypatch.setattr(llm_factory, "_slm_available", lambda: False)
    assert llm_factory.resolved_provider() == "extractive"


def test_llm_resolved_provider_auto_air_gap_skips_keys(monkeypatch):
    monkeypatch.setattr(
        llm_factory,
        "get_settings",
        lambda: _fake_settings(air_gapped=True, anthropic_key="sk-x", openai_key="sk-y"),
    )
    monkeypatch.setattr(llm_factory, "_ollama_reachable", lambda url: False)
    monkeypatch.setattr(llm_factory, "_slm_available", lambda: True)
    assert llm_factory.resolved_provider() == "slm"


def test_llm_resolved_provider_auto_anthropic_key(monkeypatch):
    monkeypatch.setattr(llm_factory, "get_settings", lambda: _fake_settings(anthropic_key="sk-x"))
    monkeypatch.setattr(llm_factory, "_ollama_reachable", lambda url: False)
    monkeypatch.setattr(llm_factory, "_slm_available", lambda: False)
    monkeypatch.setattr(
        "importlib.util.find_spec", lambda name: object() if name == "anthropic" else None
    )
    assert llm_factory.resolved_provider() == "anthropic"


def test_build_llm_auto_ollama(monkeypatch):
    monkeypatch.setattr(llm_factory, "get_settings", lambda: _fake_settings())
    monkeypatch.setattr(llm_factory, "_ollama_reachable", lambda url: True)
    llm = llm_factory.build_llm()
    assert type(llm).__name__ == "ResilientLLM"


def test_build_llm_air_gap_blocks_explicit_commercial(monkeypatch):
    monkeypatch.setattr(
        llm_factory, "get_settings", lambda: _fake_settings("anthropic", air_gapped=True)
    )
    assert isinstance(llm_factory.build_llm(), ExtractiveLLM)


def test_build_llm_auto_air_gap_extractive(monkeypatch):
    monkeypatch.setattr(llm_factory, "get_settings", lambda: _fake_settings(air_gapped=True))
    monkeypatch.setattr(llm_factory, "_ollama_reachable", lambda url: False)
    monkeypatch.setattr(llm_factory, "_slm_available", lambda: False)
    assert isinstance(llm_factory.build_llm(), ExtractiveLLM)


def test_build_llm_slm_unavailable_falls_back(monkeypatch):
    monkeypatch.setattr(llm_factory, "get_settings", lambda: _fake_settings("slm"))
    monkeypatch.setattr(llm_factory, "_build_slm", lambda: None)
    assert isinstance(llm_factory.build_llm(), ExtractiveLLM)


def test_build_llm_extractive_explicit(monkeypatch):
    monkeypatch.setattr(llm_factory, "get_settings", lambda: _fake_settings("extractive"))
    assert isinstance(llm_factory.build_llm(), ExtractiveLLM)


def test_ollama_probe_caches_result(monkeypatch):
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        raise ConnectionError("refused")

    monkeypatch.setattr(llm_factory.httpx, "get", fake_get)
    monkeypatch.setattr(llm_factory, "_ollama_probe", {})
    assert llm_factory._ollama_reachable("http://probe-test:11434") is False
    assert llm_factory._ollama_reachable("http://probe-test:11434") is False
    assert len(calls) == 1  # second call served from the TTL cache


# ── Embedder factory ──────────────────────────────────────────────────────────


def test_build_embedder_hash_explicit(monkeypatch):
    monkeypatch.setattr(
        embed_factory, "get_settings", lambda: _fake_settings(embed_provider="hash")
    )
    emb = embed_factory.build_embedder()
    assert isinstance(emb, HashingEmbedder)
    assert emb.dim == 256  # min(configured 384, 256)


def test_build_embedder_auto_ollama(monkeypatch):
    monkeypatch.setattr(embed_factory, "get_settings", lambda: _fake_settings())
    monkeypatch.setattr(embed_factory, "_ollama_reachable", lambda url: True)
    emb = embed_factory.build_embedder()
    assert type(emb).__name__ == "ResilientEmbedder"


def test_build_embedder_air_gap_blocks_ollama(monkeypatch):
    monkeypatch.setattr(
        embed_factory,
        "get_settings",
        lambda: _fake_settings(embed_provider="ollama", air_gapped=True),
    )
    monkeypatch.setattr(embed_factory, "_have", lambda pkg: False)
    assert isinstance(embed_factory.build_embedder(), HashingEmbedder)


def test_embed_resolved_provider_explicit(monkeypatch):
    monkeypatch.setattr(
        embed_factory, "get_settings", lambda: _fake_settings(embed_provider="hash")
    )
    assert embed_factory.resolved_provider() == "hash"


def test_embed_resolved_provider_air_gap_blocks_openai(monkeypatch):
    monkeypatch.setattr(
        embed_factory,
        "get_settings",
        lambda: _fake_settings(embed_provider="openai", air_gapped=True),
    )
    monkeypatch.setattr(embed_factory, "_have", lambda pkg: False)
    assert embed_factory.resolved_provider() == "hash"


def test_embed_resolved_provider_auto_ollama(monkeypatch):
    monkeypatch.setattr(embed_factory, "get_settings", lambda: _fake_settings())
    monkeypatch.setattr(embed_factory, "_ollama_reachable", lambda url: True)
    assert embed_factory.resolved_provider() == "ollama"


def test_embed_resolved_provider_auto_hash_fallback(monkeypatch):
    monkeypatch.setattr(embed_factory, "get_settings", lambda: _fake_settings())
    monkeypatch.setattr(embed_factory, "_ollama_reachable", lambda url: False)
    monkeypatch.setattr(embed_factory, "_have", lambda pkg: False)
    assert embed_factory.resolved_provider() == "hash"


def test_embed_ollama_probe_unreachable(monkeypatch):
    def fake_get(url, timeout):
        raise ConnectionError("refused")

    monkeypatch.setattr(embed_factory.httpx, "get", fake_get)
    monkeypatch.setattr(embed_factory, "_ollama_probe", {})
    assert embed_factory._ollama_reachable("http://probe-test:11434") is False
