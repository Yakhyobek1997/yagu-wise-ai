"""Ingestion: parsers, audio transcription/diarization, chunking, provenance."""

from __future__ import annotations

from auralynq.ingest.models import (
    AudioSegment,
    Chunk,
    Document,
    IngestResult,
    SourceSpan,
    SourceType,
)
from auralynq.ingest.pipeline import ingest_file, ingest_path

__all__ = [
    "AudioSegment",
    "Chunk",
    "Document",
    "IngestResult",
    "SourceSpan",
    "SourceType",
    "ingest_file",
    "ingest_path",
]
