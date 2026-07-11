"""Core typed data models shared across ingestion, indexing and retrieval.

A ``Chunk`` is the atomic retrievable unit. It always carries enough provenance
to produce an honest citation: the source document, a character ``SourceSpan``,
and — for audio — an ``AudioSegment`` with speaker and timestamps.

Visual grounding fields (bbox, normalized_bbox, block_type) are stored in
chunk.metadata["visual_grounding"] and populated by layout-aware parsers.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from auralynq.utils import stable_id

# Bump this when grounding schema changes require re-ingest
VISUAL_GROUNDING_VERSION = 1


class LayoutBlock(BaseModel):
    """A positioned text/visual block on a PDF page."""

    block_id: str = ""
    page: int = 1
    bbox: list[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0, 1.0])
    normalized_bbox: list[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0, 1.0])
    text: str = ""
    block_type: str = "paragraph"  # paragraph|title|table|figure|caption|footer|header
    reading_order: int = 0
    confidence: float = 1.0
    page_width: float = 0.0
    page_height: float = 0.0


class SourceType(str, Enum):
    pdf = "pdf"
    docx = "docx"
    html = "html"
    markdown = "markdown"
    text = "text"
    audio = "audio"
    unknown = "unknown"


class SourceSpan(BaseModel):
    """Character offsets within the parsed document text (source-span tracking)."""

    start_char: int = 0
    end_char: int = 0
    page: int | None = None
    section: str | None = None

    def locator(self) -> str:
        if self.page is not None:
            return f"p.{self.page} [{self.start_char}:{self.end_char}]"
        return f"[{self.start_char}:{self.end_char}]"


class AudioSegment(BaseModel):
    """Timestamped, optionally speaker-labelled audio region (timestamp preservation)."""

    start_s: float = 0.0
    end_s: float = 0.0
    speaker: str | None = None

    def locator(self) -> str:
        who = f"{self.speaker} " if self.speaker else ""
        return f"{who}@ {_mmss(self.start_s)}–{_mmss(self.end_s)}"


def _mmss(seconds: float) -> str:
    m, s = divmod(round(seconds), 60)
    return f"{m:d}:{s:02d}"


class Chunk(BaseModel):
    """Atomic retrievable unit with full provenance."""

    id: str
    doc_id: str
    text: str
    ordinal: int = 0
    span: SourceSpan = Field(default_factory=SourceSpan)
    audio: AudioSegment | None = None
    title: str | None = None
    source: str = ""  # human-readable source path/name
    source_type: SourceType = SourceType.unknown
    metadata: dict[str, Any] = Field(default_factory=dict)

    def locator(self) -> str:
        """Citation locator: timestamp/speaker for audio, else page/char span."""
        if self.audio is not None:
            return self.audio.locator()
        return self.span.locator()

    def citation(self) -> dict[str, Any]:
        return {
            "chunk_id": self.id,
            "doc_id": self.doc_id,
            "source": self.source or self.title or self.doc_id,
            "locator": self.locator(),
            "source_type": self.source_type.value,
            "speaker": self.audio.speaker if self.audio else None,
            "start_s": self.audio.start_s if self.audio else None,
            "end_s": self.audio.end_s if self.audio else None,
            "page": self.span.page,
            "visual_grounding": self.metadata.get("visual_grounding"),
        }

    @staticmethod
    def make_id(doc_id: str, ordinal: int) -> str:
        return stable_id(doc_id, ordinal)


class Document(BaseModel):
    """A parsed source document and its chunks."""

    id: str
    source: str
    source_type: SourceType
    title: str | None = None
    content_hash: str = ""
    language: str = "en"
    metadata: dict[str, Any] = Field(default_factory=dict)
    chunks: list[Chunk] = Field(default_factory=list)
    # Visual grounding: list of (page, width, height) tuples stored as dicts
    page_dimensions: list[dict[str, Any]] = Field(default_factory=list)
    visual_grounding_version: int = 0  # 0 = no grounding; 1+ = grounding metadata present

    @property
    def n_chunks(self) -> int:
        return len(self.chunks)

    @property
    def has_visual_grounding(self) -> bool:
        return self.visual_grounding_version >= VISUAL_GROUNDING_VERSION


class IngestResult(BaseModel):
    n_documents: int = 0
    n_chunks: int = 0
    n_skipped: int = 0
    documents: list[Document] = Field(default_factory=list)

    def merge(self, other: IngestResult) -> IngestResult:
        return IngestResult(
            n_documents=self.n_documents + other.n_documents,
            n_chunks=self.n_chunks + other.n_chunks,
            n_skipped=self.n_skipped + other.n_skipped,
            documents=self.documents + other.documents,
        )
