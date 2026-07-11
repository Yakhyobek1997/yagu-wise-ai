"""Retrieval-side models: scored chunks and retrieval results."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from auralynq.ingest.models import Chunk


class ScoredChunk(BaseModel):
    """A chunk with a retrieval score and per-method score components."""

    chunk: Chunk
    score: float = 0.0
    method: str = "unknown"
    components: dict[str, float] = Field(default_factory=dict)
    rank: int = 0

    def with_score(self, score: float, method: str | None = None) -> ScoredChunk:
        return self.model_copy(update={"score": score, "method": method or self.method})


class RetrievalResult(BaseModel):
    """Result of a retrieval call, with the route/method used and timing."""

    query: str
    method: str
    chunks: list[ScoredChunk] = Field(default_factory=list)
    took_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def texts(self) -> list[str]:
        return [c.chunk.text for c in self.chunks]

    def top(self, k: int) -> list[ScoredChunk]:
        return self.chunks[:k]


class PathEvidence(BaseModel):
    """A PathRAG relational path rendered for the trace/UI."""

    nodes: list[str] = Field(default_factory=list)
    relations: list[str] = Field(default_factory=list)
    reliability: float = 0.0
    ppr_score: float = 0.0  # Personalised PageRank terminal-node authority (0-1)
    text: str = ""
    chunk_ids: list[str] = Field(default_factory=list)

    def as_arrow(self) -> str:
        parts: list[str] = []
        for i, node in enumerate(self.nodes):
            parts.append(node)
            if i < len(self.relations):
                parts.append(f"-[{self.relations[i]}]->")
        return " ".join(parts)


class Filter(BaseModel):
    """Lightweight metadata filter passed to vector/retrieval layers."""

    must: dict[str, Any] = Field(default_factory=dict)
    source_types: list[str] | None = None
    doc_ids: list[str] | None = None
