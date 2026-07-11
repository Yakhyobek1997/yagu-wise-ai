"""Hugging Face Inference Providers LLM — powerful hosted models via the
OpenAI-compatible router. No network: we assert wiring, model resolution and the
safety guards (explicit-only, token required, air-gap blocked)."""

from __future__ import annotations

from auralynq.config import reload_settings
from auralynq.llm.factory import _model_for, build_llm, resolved_provider


def test_model_for_keeps_hf_repo_ids():
    # HF repo ids (org/model) are trusted verbatim even when they contain
    # ollama-ish substrings like "llama"/"qwen"/"deepseek".
    assert _model_for("huggingface", "Qwen/Qwen2.5-72B-Instruct") == "Qwen/Qwen2.5-72B-Instruct"
    assert _model_for("huggingface", "deepseek-ai/DeepSeek-V3-0324") == "deepseek-ai/DeepSeek-V3-0324"
    # A bare ollama-style tag is not a valid HF id → fall back to the PRO default.
    assert _model_for("huggingface", "llama3.2:3b") == "meta-llama/Llama-3.3-70B-Instruct"


def test_hf_without_token_falls_back(monkeypatch):
    monkeypatch.setenv("AURALYNQ_LLM__PROVIDER", "huggingface")
    monkeypatch.setenv("HUGGINGFACE_TOKEN", "")
    reload_settings()
    assert build_llm().name == "extractive"


def test_hf_with_token_builds_provider(monkeypatch):
    monkeypatch.setenv("AURALYNQ_LLM__PROVIDER", "huggingface")
    monkeypatch.setenv("HUGGINGFACE_TOKEN", "hf_dummy_test_token")
    reload_settings()
    llm = build_llm()  # constructs the client but makes no network call
    assert llm.name == "huggingface"


def test_hf_is_explicit_only_never_auto(monkeypatch):
    # A token present for gated *downloads* must not silently route generation to
    # the paid HF API under provider=auto.
    monkeypatch.setenv("AURALYNQ_LLM__PROVIDER", "auto")
    monkeypatch.setenv("HUGGINGFACE_TOKEN", "hf_dummy_test_token")
    monkeypatch.setenv("AURALYNQ_LLM__BASE_URL", "http://127.0.0.1:1")  # no ollama
    reload_settings()
    assert resolved_provider() != "huggingface"


def test_hf_blocked_when_air_gapped(monkeypatch):
    monkeypatch.setenv("AURALYNQ_LLM__PROVIDER", "huggingface")
    monkeypatch.setenv("HUGGINGFACE_TOKEN", "hf_dummy_test_token")
    monkeypatch.setenv("AURALYNQ_AIR_GAPPED", "true")
    reload_settings()
    assert resolved_provider() == "extractive"
    assert build_llm().name == "extractive"
