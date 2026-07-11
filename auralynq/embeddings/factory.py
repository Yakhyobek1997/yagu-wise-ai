"""Embedder factory with ``auto`` resolution (ADR-0004).

Auto-resolution priority (highest → lowest):
  ollama (if reachable) → bge (if FlagEmbedding installed) → openai (if key) → hash
"""

from __future__ import annotations

import functools
import importlib.util
import time

import httpx

from auralynq.config import get_settings
from auralynq.embeddings.base import Embedder
from auralynq.embeddings.hashing import HashingEmbedder
from auralynq.telemetry import get_logger

_log = get_logger("auralynq.embeddings")

_OLLAMA_PROBE_TTL = 30.0
_ollama_probe: dict[str, tuple[bool, float]] = {}


def _have(pkg: str) -> bool:
    return importlib.util.find_spec(pkg) is not None


def _ollama_reachable(base_url: str) -> bool:
    now = time.monotonic()
    cached = _ollama_probe.get(base_url)
    if cached is not None and now - cached[1] < _OLLAMA_PROBE_TTL:
        return cached[0]
    try:
        httpx.get(base_url.rstrip("/") + "/api/tags", timeout=0.5)
        ok = True
    except Exception:
        ok = False
    _ollama_probe[base_url] = (ok, now)
    return ok


def build_embedder(provider: str | None = None) -> Embedder:
    s = get_settings()
    provider = provider or s.embedding.provider

    if provider == "auto":
        if not s.air_gapped and _ollama_reachable(s.llm.base_url):
            provider = "ollama"
        elif _have("FlagEmbedding"):
            provider = "bge"
        elif not s.air_gapped and s.openai_api_key and _have("openai"):
            provider = "openai"
        else:
            provider = "hash"

    # Air-gap hard-blocks on external providers.
    if s.air_gapped and provider in ("openai", "ollama"):
        _log.warning(
            "embeddings.air_gapped_block", provider=provider, action="falling back to hash"
        )
        provider = "bge" if _have("FlagEmbedding") else "hash"

    fallback_dim = min(s.embedding.dim, 256)

    if provider == "ollama":
        try:
            from auralynq.embeddings.ollama_embed import OllamaEmbedder
            from auralynq.embeddings.resilient import ResilientEmbedder

            return ResilientEmbedder(
                OllamaEmbedder(model=s.embedding.ollama_model, base_url=s.llm.base_url),
                fallback_dim=fallback_dim,
            )
        except Exception as exc:
            _log.warning("embeddings.ollama_failed", error=str(exc))
            provider = "bge" if _have("FlagEmbedding") else "hash"

    if provider == "bge":
        try:
            from auralynq.embeddings.bge import BGEM3Embedder
            from auralynq.embeddings.resilient import ResilientEmbedder

            return ResilientEmbedder(
                BGEM3Embedder(
                    model=s.embedding.model, device=s.embedding.device, dim=s.embedding.dim
                ),
                fallback_dim=fallback_dim,
            )
        except Exception as exc:  # pragma: no cover - heavy path
            _log.warning("embeddings.bge_failed_fallback_hash", error=str(exc))
            provider = "hash"

    if provider == "openai":  # pragma: no cover - paid path
        try:
            from auralynq.embeddings.openai_embed import OpenAIEmbedder
            from auralynq.embeddings.resilient import ResilientEmbedder

            return ResilientEmbedder(
                OpenAIEmbedder(api_key=s.openai_api_key), fallback_dim=fallback_dim
            )
        except Exception as exc:
            _log.warning("embeddings.openai_failed_fallback_hash", error=str(exc))
            provider = "hash"

    _log.info("embeddings.using", provider="hash")
    return HashingEmbedder(dim=fallback_dim)


@functools.lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return build_embedder()


def resolved_provider() -> str:
    s = get_settings()
    if s.embedding.provider != "auto":
        if s.air_gapped and s.embedding.provider in ("openai", "ollama"):
            return "bge" if _have("FlagEmbedding") else "hash"
        return s.embedding.provider
    if not s.air_gapped and _ollama_reachable(s.llm.base_url):
        return "ollama"
    if _have("FlagEmbedding"):
        return "bge"
    if not s.air_gapped and s.openai_api_key and _have("openai"):
        return "openai"
    return "hash"
