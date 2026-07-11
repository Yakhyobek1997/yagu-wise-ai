"""Resilient embedder wrapper.

Mirrors :class:`auralynq.llm.resilient.ResilientLLM` for the embedding layer: wraps
a primary (commercial/networked) embedder and falls back to the deterministic
:class:`HashingEmbedder` if the primary raises at request time — e.g. inactive
billing (429), rate limit, expired key, or a network blip. This upholds ADR-0003:
a broken paid backend degrades the *quality* of retrieval rather than crashing the
whole pipeline (which is what `make demo` hit when OpenAI returned 429).

Dimension safety: embeddings of a single index must share one vector dimension.
So the fallback is **batch-atomic** (a failing batch is re-embedded wholly by the
fallback) and **sticky** (once fallen back, stay on the fallback for the rest of
this embedder's life), keeping every vector in the collection consistent.
"""

from __future__ import annotations

from auralynq.embeddings.base import Embedder, Embedding, EmbeddingBatch
from auralynq.embeddings.hashing import HashingEmbedder
from auralynq.telemetry import get_logger

_log = get_logger("auralynq.embeddings.resilient")


class ResilientEmbedder(Embedder):
    def __init__(self, primary: Embedder, fallback_dim: int = 256) -> None:
        self.primary = primary
        self._fallback = HashingEmbedder(dim=fallback_dim)
        self.name = primary.name
        self.dim = primary.dim
        self._degraded = False
        self.last_fallback: str | None = None

    def _go_fallback(self, exc: Exception) -> None:
        if not self._degraded:
            self._degraded = True
            self.name = f"{self.primary.name}->hash"
            self.dim = self._fallback.dim
            self.last_fallback = type(exc).__name__
            _log.warning(
                "embeddings.runtime_fallback_hash",
                provider=self.primary.name,
                error=str(exc)[:200],
            )

    def embed(self, texts: list[str]) -> EmbeddingBatch:
        if self._degraded:
            return self._fallback.embed(texts)
        try:
            batch = self.primary.embed(texts)
            self.dim = self.primary.dim
            return batch
        except Exception as exc:  # provider/runtime error → degrade, don't crash
            self._go_fallback(exc)
            return self._fallback.embed(texts)

    def embed_query(self, text: str) -> Embedding:
        # Must match whatever space the documents were embedded in.
        if self._degraded:
            return self._fallback.embed_query(text)
        try:
            return self.primary.embed_query(text)
        except Exception as exc:
            self._go_fallback(exc)
            return self._fallback.embed_query(text)
