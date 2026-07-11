"""Audio ingestion: transcribe → diarize → timestamped, speaker-labelled chunks."""

from __future__ import annotations

from pathlib import Path

from auralynq.ingest.models import AudioSegment, Chunk, SourceType
from auralynq.voice.asr import ASRSegment
from auralynq.voice.diarize import diarize_segments
from auralynq.voice.factory import build_asr


def transcribe_to_chunks(
    path: Path,
    doc_id: str,
    *,
    target_chars: int = 600,
    diarize: bool = True,
) -> tuple[str, str, list[Chunk]]:
    """Return (title, language, chunks) for an audio document.

    Consecutive ASR segments from the same speaker are packed into chunks (up to
    ``target_chars``) so each chunk carries a coherent timestamped, speaker-
    attributed span for citation.
    """
    asr = build_asr()
    transcript = asr.transcribe(path)
    segments: list[ASRSegment] = transcript.segments
    if diarize:
        segments = diarize_segments(path, segments)

    chunks: list[Chunk] = []
    buf: list[ASRSegment] = []
    ordinal = 0

    def flush() -> None:
        nonlocal ordinal
        if not buf:
            return
        text = " ".join(s.text.strip() for s in buf).strip()
        if not text:
            buf.clear()
            return
        seg = AudioSegment(start_s=buf[0].start_s, end_s=buf[-1].end_s, speaker=buf[0].speaker)
        # Paper §4.5 Eq. 1: grounding metadata for audio chunks stores
        # (t_start, t_end) in R+^2, analogous to normalized_bbox for PDFs.
        # The resolver uses this to emit support_type="segment" grounding.
        vg = {
            "grounding_version": 1,
            "source_modality": "audio",
            "t_start": seg.start_s,
            "t_end": seg.end_s,
            "speaker": seg.speaker,
            "has_bbox": False,
            "bbox": None,
            "normalized_bbox": None,
        }
        chunks.append(
            Chunk(
                id=Chunk.make_id(doc_id, ordinal),
                doc_id=doc_id,
                text=text,
                ordinal=ordinal,
                audio=seg,
                source=path.name,
                source_type=SourceType.audio,
                title=path.stem,
                metadata={
                    "asr_provider": transcript.provider,
                    "language": transcript.language,
                    "visual_grounding": vg,
                },
            )
        )
        ordinal += 1
        buf.clear()

    cur_len = 0
    cur_speaker = None
    for seg in segments:
        if (cur_speaker is not None and seg.speaker != cur_speaker) or cur_len > target_chars:
            flush()
            cur_len = 0
        buf.append(seg)
        cur_speaker = seg.speaker
        cur_len += len(seg.text)
    flush()
    return path.stem, transcript.language, chunks
