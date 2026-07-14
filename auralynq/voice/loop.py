"""Push-to-talk voice loop: (VAD →) ASR → agent → grounded answer → TTS.

Works fully offline: with no ASR model installed, ``NullASR`` reads a sidecar
transcript so the end-to-end voice path is still exercised; with no TTS model,
``NullTTS`` writes a short deterministic WAV. The agent answer carries
speaker/timestamp citations when the indexed evidence is audio.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from auralynq.agent.runner import answer_question
from auralynq.config import get_settings
from auralynq.telemetry import get_logger
from auralynq.voice.asr import Transcript
from auralynq.voice.diarize import diarize_segments
from auralynq.voice.factory import build_asr, build_tts

_log = get_logger("auralynq.voice.loop")

# The full answer stays on screen; the spoken reply is a short, clean summary so
# TTS is fast and pleasant (no markdown symbols or citation markers read aloud).
import re as _re

_SPEECH_MAX_CHARS = 480


def _clean_for_speech(text: str) -> str:
    text = _re.sub(r"\[\d+\]", "", text or "")  # drop [1] citation markers
    text = _re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)  # [[link]] -> link
    text = _re.sub(r"[#*`_>|]+", " ", text)  # strip markdown symbols
    return " ".join(text.split())


def _speech_excerpt(text: str, max_chars: int = _SPEECH_MAX_CHARS) -> str:
    text = _clean_for_speech(text)
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    m = _re.search(r"^.*[.!?](?=\s|$)", cut)  # end on a sentence boundary if possible
    excerpt = m.group(0) if (m and m.end() >= max_chars * 0.5) else cut.rsplit(" ", 1)[0]
    return excerpt.strip() + " …"


class VoiceTurnResult(BaseModel):
    transcript: str = ""
    language: str = "en"
    answer: str = ""
    citations: list[dict[str, Any]] = Field(default_factory=list)
    audio_out_path: str | None = None
    asr_provider: str = "null"
    tts_provider: str | None = None
    route: str = "fast"
    trace: list[dict[str, Any]] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


def transcribe(audio_path: Path, diarize: bool | None = None) -> Transcript:
    s = get_settings()
    asr = build_asr()
    transcript = asr.transcribe(Path(audio_path))
    if diarize if diarize is not None else s.voice.diarize:
        transcript.segments = diarize_segments(audio_path, transcript.segments)
    return transcript


def run_voice_turn(
    audio_path: Path | None = None,
    *,
    text: str | None = None,
    speak: bool = True,
    final_k: int | None = None,
    voice: str | None = None,
) -> VoiceTurnResult:
    """Run one voice turn. Provide ``audio_path`` (preferred) or ``text``."""
    s = get_settings()
    if audio_path is not None:
        transcript = transcribe(Path(audio_path))
        question = transcript.text
        lang, asr_provider = transcript.language, transcript.provider
    elif text is not None:
        question, lang, asr_provider = text, "en", "text"
    else:
        raise ValueError("run_voice_turn requires either audio_path or text")

    if not question:
        return VoiceTurnResult(
            transcript="", answer="I couldn't hear any speech.", asr_provider=asr_provider
        )

    result = answer_question(question, final_k=final_k)

    out = VoiceTurnResult(
        transcript=question,
        language=lang,
        answer=result.answer,
        citations=result.citations,
        asr_provider=asr_provider,
        route=result.route,
        trace=result.trace,
    )

    if speak and result.answer:
        tts = build_tts()
        out_path = s.storage_dir / "tts_out.wav"
        tts_res = tts.synthesize(_speech_excerpt(result.answer), out_path, voice=voice)
        out.audio_out_path = str(tts_res.audio_path)
        out.tts_provider = tts_res.provider
    return out
