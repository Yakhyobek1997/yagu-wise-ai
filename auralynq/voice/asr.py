"""ASR provider interface + faster-whisper backend + offline NullASR fallback.

Shared by ingestion (audio documents) and the live voice loop. Diarization
(pyannote) and word alignment (WhisperX) are optional and layer on top.
"""

from __future__ import annotations

import abc
import json
import wave
from dataclasses import dataclass, field
from pathlib import Path

from auralynq.telemetry import get_logger

_log = get_logger("auralynq.voice.asr")


@dataclass
class ASRSegment:
    start_s: float
    end_s: float
    text: str
    speaker: str | None = None


@dataclass
class Transcript:
    segments: list[ASRSegment] = field(default_factory=list)
    language: str = "en"
    duration_s: float = 0.0
    provider: str = "null"

    @property
    def text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments if s.text.strip()).strip()


class ASRProvider(abc.ABC):
    name = "base"

    @abc.abstractmethod
    def transcribe(self, audio_path: Path) -> Transcript: ...


class NullASR(ASRProvider):
    """Offline fallback. Reads a sidecar transcript if present; else empty.

    Sidecar formats (checked in order):
      * ``<stem>.transcript.json`` — {"segments": [{start_s,end_s,text,speaker}], ...}
      * ``<stem>.txt`` — plain transcript (single segment spanning the audio).
    This lets the demo and tests run an end-to-end voice path with no models.
    """

    name = "null"

    def transcribe(self, audio_path: Path) -> Transcript:
        audio_path = Path(audio_path)
        sidecar = audio_path.with_suffix(".transcript.json")
        if sidecar.exists():
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            segs = [
                ASRSegment(
                    s.get("start_s", 0.0), s.get("end_s", 0.0), s.get("text", ""), s.get("speaker")
                )
                for s in data.get("segments", [])
            ]
            return Transcript(
                segments=segs,
                language=data.get("language", "en"),
                duration_s=_duration(audio_path),
                provider="null",
            )
        txt = audio_path.with_suffix(".txt")
        dur = _duration(audio_path)
        if txt.exists():
            return Transcript(
                segments=[ASRSegment(0.0, dur, txt.read_text(encoding="utf-8").strip())],
                duration_s=dur,
                provider="null",
            )
        _log.info("asr.null_no_transcript", path=str(audio_path))
        return Transcript(segments=[], duration_s=dur, provider="null")


class FasterWhisperASR(ASRProvider):
    name = "faster_whisper"

    def __init__(self, model: str = "base", device: str = "auto") -> None:
        from faster_whisper import WhisperModel  # type: ignore

        compute = "int8" if device == "cpu" else "auto"
        resolved = "cpu" if device == "cpu" else "auto"
        self._model = WhisperModel(model, device=resolved, compute_type=compute)
        _log.info("asr.faster_whisper.loaded", model=model)

    def transcribe(self, audio_path: Path) -> Transcript:
        segments, info = self._model.transcribe(
            str(audio_path), vad_filter=True, word_timestamps=True
        )
        segs = [ASRSegment(seg.start, seg.end, seg.text.strip()) for seg in segments]
        return Transcript(
            segments=segs,
            language=info.language,
            duration_s=getattr(info, "duration", 0.0),
            provider="faster_whisper",
        )


def _duration(path: Path) -> float:
    try:
        if path.suffix.lower() == ".wav":
            with wave.open(str(path), "rb") as wf:
                return wf.getnframes() / float(wf.getframerate() or 1)
    except Exception:  # pragma: no cover
        pass
    try:  # pragma: no cover - optional
        import soundfile as sf

        info = sf.info(str(path))
        return float(info.frames) / float(info.samplerate or 1)
    except Exception:
        return 0.0
