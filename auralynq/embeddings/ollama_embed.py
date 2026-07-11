"""Ollama embedding provider — zero-cost local embeddings via nomic-embed-text."""

from __future__ import annotations

import numpy as np

from auralynq.embeddings.base import Embedder, EmbeddingBatch
from auralynq.telemetry import get_logger

_log = get_logger("auralynq.embeddings.ollama")


class OllamaEmbedder(Embedder):
    name = "ollama"

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._dim: int | None = None

    @property
    def dim(self) -> int:  # type: ignore[override]  # lazy dim vs base's plain int attr
        return self._dim or 768  # nomic-embed-text default

    def embed(self, texts: list[str]) -> EmbeddingBatch:
        import httpx

        vectors: list[list[float]] = []

        # Prefer the newer batch-capable /api/embed (Ollama >= 0.1.26).
        try:
            resp = httpx.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            vectors = data.get("embeddings", [])
        except Exception:
            # Fall back to the legacy single-text endpoint.
            for text in texts:
                resp = httpx.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                    timeout=60,
                )
                resp.raise_for_status()
                vectors.append(resp.json()["embedding"])

        dense = np.array(vectors, dtype=np.float32)
        if self._dim is None and dense.shape[0] > 0:
            self._dim = int(dense.shape[1])
        _log.debug("ollama.embed", n=len(texts), dim=self._dim)
        return EmbeddingBatch(dense=dense, sparse=[])
