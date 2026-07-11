"""LLM factory with ``auto`` resolution + extractive fallback.

Auto-resolution priority (local-first, zero-cost):
  1. ollama   — if daemon is reachable (GPU/CPU handled by Ollama)
  2. slm      — llama-cpp-python GGUF (GPU when CUDA present, CPU otherwise)
  3. anthropic — if ANTHROPIC_API_KEY set and SDK installed
  4. openai   — if OPENAI_API_KEY set and SDK installed
  5. cohere   — if COHERE_API_KEY set and SDK installed
  6. extractive — citation-faithful quotation (always available, no generation)
"""

from __future__ import annotations

import functools
import importlib.util
import time

import httpx

from auralynq.config import get_settings
from auralynq.llm.base import LLM
from auralynq.llm.fallback import ExtractiveLLM
from auralynq.telemetry import get_logger

_log = get_logger("auralynq.llm")

# TTL cache for the Ollama reachability probe: resolved_provider() runs on every
# /health and provider-resolution call, and a blocking 0.5s probe per hit adds up.
_OLLAMA_PROBE_TTL = 30.0
_ollama_probe: dict[str, tuple[bool, float]] = {}


def _ollama_reachable(base_url: str) -> bool:
    now = time.monotonic()
    cached = _ollama_probe.get(base_url)
    if cached is not None and now - cached[1] < _OLLAMA_PROBE_TTL:
        return cached[0]
    try:  # pragma: no cover - network probe
        httpx.get(base_url.rstrip("/") + "/api/tags", timeout=0.5)
        ok = True
    except Exception:
        ok = False
    _ollama_probe[base_url] = (ok, now)
    return ok


def _slm_available() -> bool:
    """True when llama-cpp-python is installed (model is resolved lazily)."""
    return importlib.util.find_spec("llama_cpp") is not None


# Sensible per-provider default models. The global default (llama3.2:3b) targets
# Ollama; if the resolved provider is a commercial API and the configured model
# still looks like an Ollama tag, fall back to that provider's default so an
# OPENAI/ANTHROPIC key doesn't 404 on a local model name.
_PROVIDER_DEFAULT_MODEL = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-latest",
    "cohere": "command-r-08-2024",
    # HF Inference Providers — a strong, broadly-available default for PRO accounts.
    "huggingface": "meta-llama/Llama-3.3-70B-Instruct",
}
_OLLAMA_MODEL_HINTS = ("llama", "qwen", "mistral", "gemma", "phi", "deepseek", ":")


def _model_for(provider: str, configured: str) -> str:
    default = _PROVIDER_DEFAULT_MODEL.get(provider)
    if default is None:
        return configured
    # HF model ids are repo paths ("org/model") and legitimately contain the
    # ollama-ish substrings above — trust any "/"-shaped id, else use the default.
    if provider == "huggingface":
        return configured if "/" in configured else default
    looks_like_ollama = any(h in configured.lower() for h in _OLLAMA_MODEL_HINTS)
    if looks_like_ollama:
        _log.info("llm.model_defaulted", provider=provider, model=default, ignored=configured)
        return default
    return configured


def _build_slm() -> LLM | None:
    """Construct a SLMLlm, downloading the GGUF if not cached. Returns None on failure."""
    from auralynq.llm.slm import resolve_model_path, resolve_n_gpu_layers

    s = get_settings()
    path = resolve_model_path(s.llm.slm_repo, s.llm.slm_filename, s.huggingface_token)
    if path is None:
        return None
    n_layers = resolve_n_gpu_layers(s.llm.slm_n_gpu_layers)
    try:
        from auralynq.llm.providers import SLMLlm
        from auralynq.llm.resilient import ResilientLLM

        return ResilientLLM(SLMLlm(path, n_gpu_layers=n_layers, n_ctx=s.llm.slm_n_ctx))
    except Exception as exc:
        _log.warning("llm.slm_init_failed", error=str(exc))
        return None


def build_llm(provider: str | None = None) -> LLM:
    s = get_settings()
    provider = provider or s.llm.provider

    if provider == "auto":
        # Air-gap mode: external commercial providers are forbidden regardless of
        # which keys are present in the environment.
        if s.air_gapped:
            _log.info("llm.air_gapped", skipped=["anthropic", "openai", "cohere"])
            if _ollama_reachable(s.llm.base_url):
                provider = "ollama"
            elif _slm_available():
                provider = "slm"
            else:
                provider = "extractive"
        elif _ollama_reachable(s.llm.base_url):
            # Local Ollama: zero-cost, no data egress, works offline.
            provider = "ollama"
        elif _slm_available():
            # Local GGUF SLM: GPU when CUDA present, CPU otherwise.
            provider = "slm"
        elif s.anthropic_api_key and importlib.util.find_spec("anthropic"):
            provider = "anthropic"
        elif s.openai_api_key and importlib.util.find_spec("openai"):
            provider = "openai"
        elif s.cohere_api_key and importlib.util.find_spec("cohere"):
            provider = "cohere"
        else:
            provider = "extractive"

    # Hard-fail: if air-gapped and a commercial provider was explicitly configured,
    # refuse rather than silently sending data out.
    if s.air_gapped and provider in ("openai", "anthropic", "cohere", "huggingface"):
        _log.warning(
            "llm.air_gapped_block",
            provider=provider,
            action="falling back to extractive",
        )
        return ExtractiveLLM()

    # Networked/commercial providers are wrapped so a request-time failure (bad
    # key, inactive billing, rate limit, network blip) degrades to extractive
    # instead of 500-ing the query (ADR-0003).
    try:
        if provider == "ollama":
            from auralynq.llm.providers import OllamaLLM
            from auralynq.llm.resilient import ResilientLLM

            return ResilientLLM(OllamaLLM(s.llm.model, s.llm.base_url))

        if provider == "slm":
            slm = _build_slm()
            if slm is not None:
                return slm
            _log.warning("llm.slm_unavailable", fallback="extractive")
            return ExtractiveLLM()

        if provider == "openai":
            from auralynq.llm.providers import OpenAILLM
            from auralynq.llm.resilient import ResilientLLM

            return ResilientLLM(OpenAILLM(s.openai_api_key, _model_for("openai", s.llm.model)))

        if provider == "anthropic":
            from auralynq.llm.providers import AnthropicLLM
            from auralynq.llm.resilient import ResilientLLM

            return ResilientLLM(
                AnthropicLLM(s.anthropic_api_key, _model_for("anthropic", s.llm.model))
            )

        if provider == "cohere":
            from auralynq.llm.providers import CohereLLM
            from auralynq.llm.resilient import ResilientLLM

            return ResilientLLM(CohereLLM(s.cohere_api_key, _model_for("cohere", s.llm.model)))

        if provider == "huggingface":
            # Powerful hosted models via HF Inference Providers (OpenAI-compatible
            # router). Explicit-only: never auto-selected, so a token present for
            # gated *downloads* never silently routes generation to a paid API.
            from auralynq.llm.providers import HuggingFaceLLM
            from auralynq.llm.resilient import ResilientLLM

            if not s.huggingface_token:
                _log.warning("llm.huggingface_no_token", fallback="extractive")
                return ExtractiveLLM()
            return ResilientLLM(
                HuggingFaceLLM(s.huggingface_token, _model_for("huggingface", s.llm.model))
            )

    except Exception as exc:  # construction failure (e.g. missing sdk) → extractive
        _log.warning("llm.fallback_extractive", error=str(exc))

    _log.info("llm.using", provider="extractive")
    return ExtractiveLLM()


def resolved_provider() -> str:
    s = get_settings()
    if s.llm.provider != "auto":
        if s.air_gapped and s.llm.provider in ("openai", "anthropic", "cohere", "huggingface"):
            return "extractive"
        return s.llm.provider
    if s.air_gapped:
        if _ollama_reachable(s.llm.base_url):
            return "ollama"
        return "slm" if _slm_available() else "extractive"
    if _ollama_reachable(s.llm.base_url):
        return "ollama"
    if _slm_available():
        return "slm"
    if s.anthropic_api_key and importlib.util.find_spec("anthropic"):
        return "anthropic"
    if s.openai_api_key and importlib.util.find_spec("openai"):
        return "openai"
    if s.cohere_api_key and importlib.util.find_spec("cohere"):
        return "cohere"
    return "extractive"


@functools.lru_cache(maxsize=1)
def get_llm() -> LLM:
    return build_llm()
