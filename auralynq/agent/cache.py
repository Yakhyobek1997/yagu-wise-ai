"""Semantic cache for the agent.

Caches (question embedding → finalized answer + citations). A new question that
is within ``threshold`` cosine of a cached one returns the cached result, marked
``cached=True``. Bounded LRU-ish via insertion order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from auralynq.embeddings.factory import get_embedder


@dataclass
class _Entry:
    vec: np.ndarray
    answer: str
    citations: list[dict[str, Any]]


@dataclass
class SemanticCache:
    threshold: float = 0.93
    max_entries: int = 256
    _entries: list[_Entry] = field(default_factory=list)

    def lookup(self, question: str) -> tuple[str, list[dict[str, Any]]] | None:
        if not self._entries:
            return None
        emb = get_embedder()
        q = emb.embed_query(question).dense
        best, best_sim = None, -1.0
        for e in self._entries:
            sim = emb.cosine(q, e.vec)
            if sim > best_sim:
                best, best_sim = e, sim
        if best is not None and best_sim >= self.threshold:
            return best.answer, best.citations
        return None

    def store(self, question: str, answer: str, citations: list[dict[str, Any]]) -> None:
        emb = get_embedder()
        q = emb.embed_query(question).dense
        self._entries.append(_Entry(vec=q, answer=answer, citations=citations))
        if len(self._entries) > self.max_entries:
            self._entries.pop(0)

    def clear(self) -> None:
        self._entries.clear()
