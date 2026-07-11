from __future__ import annotations

from auralynq.cli import app
from auralynq.providers import describe_providers, health_snapshot
from auralynq.voice.asr import NullASR
from auralynq.voice.diarize import _heuristic
from auralynq.voice.factory import build_asr, build_tts
from typer.testing import CliRunner

runner = CliRunner()


def test_cli_version():
    res = runner.invoke(app, ["--version"])
    assert res.exit_code == 0
    assert "auralynq" in res.stdout


def test_cli_help_lists_commands():
    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0
    for cmd in ("ingest", "ask", "talk", "eval", "bench", "data", "serve", "mcp", "index"):
        assert cmd in res.stdout


def test_cli_ingest_and_ask(corpus_dir):
    res = runner.invoke(app, ["index", "--input", str(corpus_dir)])
    assert res.exit_code == 0, res.stdout
    from auralynq.agent import runner as ar

    ar._CACHE.clear()
    res2 = runner.invoke(app, ["ask", "What is the capital of France?", "--json"])
    assert res2.exit_code == 0, res2.stdout
    assert "answer" in res2.stdout


def test_cli_info(corpus_dir):
    res = runner.invoke(app, ["info"])
    assert res.exit_code == 0
    assert "embeddings" in res.stdout


def test_describe_providers_resolves_fallbacks(monkeypatch):
    import auralynq.llm.factory as lf

    # Force SLM unavailable so the chain reaches extractive deterministically.
    monkeypatch.setattr(lf, "_slm_available", lambda: False)
    monkeypatch.setattr(lf, "_ollama_reachable", lambda url: False)
    rows = {r["subsystem"]: r["provider"] for r in describe_providers()}
    assert rows["embeddings"] == "hash"
    assert rows["vector_store"] == "memory"
    assert rows["llm"] == "extractive"
    assert rows["asr"] == "null"


def test_health_snapshot():
    snap = health_snapshot()
    assert snap["status"] == "ok"
    assert "providers" in snap


def test_factory_fallbacks():
    assert build_asr().name == "null"
    assert build_tts().name == "null"
    assert isinstance(build_asr(), NullASR)


def test_diarize_heuristic_alternates_on_pause():
    from auralynq.voice.asr import ASRSegment

    segs = [ASRSegment(0.0, 1.0, "a"), ASRSegment(3.0, 4.0, "b")]  # >1s gap
    out = _heuristic(segs)
    assert out[0].speaker != out[1].speaker


def test_llm_model_defaulting_for_commercial_providers():
    """Ollama-style model tags must not leak into OpenAI/Anthropic (would 404)."""
    from auralynq.llm.factory import _model_for

    # Ollama-looking tag -> provider default
    assert _model_for("openai", "llama3.2:3b") == "gpt-4o-mini"
    assert _model_for("anthropic", "llama3.2:3b") == "claude-3-5-haiku-latest"
    # An explicit provider-appropriate model is respected
    assert _model_for("openai", "gpt-4o") == "gpt-4o"
    assert _model_for("anthropic", "claude-3-5-sonnet-latest") == "claude-3-5-sonnet-latest"
    # Unknown provider passes through unchanged
    assert _model_for("ollama", "llama3.2:3b") == "llama3.2:3b"


def test_resilient_llm_falls_back_on_runtime_error():
    """A provider that raises at request time must degrade to extractive, not crash."""
    from auralynq.llm.base import LLM, Context
    from auralynq.llm.resilient import ResilientLLM

    class _Boom(LLM):
        name = "boom"

        def generate(self, prompt, *, system=None, temperature=None, max_tokens=None):
            raise RuntimeError("billing_not_active")

    r = ResilientLLM(_Boom())
    ctx = [Context(marker=1, text="Paris is the capital of France.", source="geo.md")]
    out = r.answer("What is the capital of France?", ctx)
    assert out and "[1]" in out  # extractive fallback produced a cited answer
    assert r.last_fallback == "RuntimeError"
    # streaming also degrades cleanly
    streamed = "".join(r.stream_answer("What is the capital of France?", ctx))
    assert "[1]" in streamed


def test_llm_model_defaulting_for_cohere():
    from auralynq.llm.factory import _model_for

    assert _model_for("cohere", "llama3.2:3b") == "command-r-08-2024"
    assert _model_for("cohere", "command-r-plus") == "command-r-plus"


def test_llm_auto_resolves_cohere_when_only_cohere_key(monkeypatch):
    """With only a Cohere key + sdk present (and no Ollama), auto resolution selects cohere."""
    import sys
    import types

    from auralynq.config import reload_settings

    # The conftest blanks all secret envs; set just Cohere for this test.
    monkeypatch.setenv("AURALYNQ_LLM__PROVIDER", "auto")
    monkeypatch.setenv("COHERE_API_KEY", "test-cohere-key")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    reload_settings()

    # Stub the optional `cohere` SDK so importlib.util.find_spec() sees it without
    # installing it. find_spec requires a real __spec__ on the module object.
    import importlib.machinery
    import importlib.util

    if importlib.util.find_spec("cohere") is None:
        fake = types.ModuleType("cohere")
        fake.__spec__ = importlib.machinery.ModuleSpec("cohere", loader=None)
        fake.ClientV2 = lambda api_key: object()  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "cohere", fake)

    # Auto-resolution now prefers Ollama when reachable; simulate no local Ollama
    # to exercise the cloud-provider fallback path.
    import auralynq.llm.factory as lf

    monkeypatch.setattr(lf, "_ollama_reachable", lambda url: False)
    monkeypatch.setattr(lf, "_slm_available", lambda: False)

    from auralynq.llm.factory import resolved_provider

    assert resolved_provider() == "cohere"


def test_cohere_rerank_model_defaulting():
    """A local BGE reranker name must not be sent to Cohere's hosted reranker."""
    from auralynq.retrieval.hybrid.rerank import _cohere_rerank_model

    assert _cohere_rerank_model("BAAI/bge-reranker-v2-m3") == "rerank-v3.5"
    assert _cohere_rerank_model("bge-reranker-large") == "rerank-v3.5"
    assert _cohere_rerank_model("rerank-v3.5") == "rerank-v3.5"
    assert _cohere_rerank_model("rerank-english-v3.0") == "rerank-english-v3.0"
