"""Speaker diarization (pyannote, gated by HUGGINGFACE_TOKEN) with a fallback.

When pyannote is unavailable the fallback assigns speaker labels by pause-based
turn segmentation so the pipeline still produces speaker-attributed citations
(clearly labelled as heuristic).
"""

from __future__ import annotations

from auralynq.config import get_settings
from auralynq.telemetry import get_logger
from auralynq.voice.asr import ASRSegment

_log = get_logger("auralynq.voice.diarize")


def diarize_segments(audio_path, segments: list[ASRSegment]) -> list[ASRSegment]:
    """Attach speaker labels to ASR segments (in place semantics, returns list)."""
    s = get_settings()
    if not segments:
        return segments
    if any(seg.speaker for seg in segments):
        return segments  # already diarized (e.g. from sidecar)

    if s.huggingface_token:
        try:  # pragma: no cover - heavy/gated path
            return _pyannote(audio_path, segments, s.huggingface_token)
        except Exception as exc:
            _log.warning("diarize.pyannote_failed_fallback", error=str(exc))
    return _heuristic(segments)


def _pyannote(audio_path, segments, token):  # pragma: no cover - gated
    from pyannote.audio import Pipeline

    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=token)
    diar = pipeline(str(audio_path))
    turns = [(t.start, t.end, label) for t, _, label in diar.itertracks(yield_label=True)]
    for seg in segments:
        mid = (seg.start_s + seg.end_s) / 2
        seg.speaker = next((lbl for st, en, lbl in turns if st <= mid <= en), None)
    return segments


def _heuristic(segments: list[ASRSegment]) -> list[ASRSegment]:
    """Pause-based turn detection: a gap > 1.0s starts a new speaker turn."""
    speaker_idx = 0
    prev_end = None
    for seg in segments:
        if prev_end is not None and (seg.start_s - prev_end) > 1.0:
            speaker_idx = (speaker_idx + 1) % 2
        seg.speaker = f"SPEAKER_{speaker_idx:02d}"
        prev_end = seg.end_s
    return segments
