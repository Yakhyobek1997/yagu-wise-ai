"""Voice: ASR, diarization, VAD, TTS, and the push-to-talk loop.

``loop`` symbols are exposed lazily to avoid an import cycle (loop → agent →
pipeline → ingest → voice). Import ``yaguwiseai.voice.loop`` directly, or access
``yaguwiseai.voice.run_voice_turn`` which resolves on first use.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from yaguwiseai.voice.asr import ASRSegment, Transcript
from yaguwiseai.voice.factory import build_asr, build_tts, resolved_asr, resolved_tts

if TYPE_CHECKING:  # pragma: no cover
    from yaguwiseai.voice.loop import VoiceTurnResult, run_voice_turn, transcribe

__all__ = [
    "ASRSegment",
    "Transcript",
    "VoiceTurnResult",
    "build_asr",
    "build_tts",
    "resolved_asr",
    "resolved_tts",
    "run_voice_turn",
    "transcribe",
]

_LAZY = {"VoiceTurnResult", "run_voice_turn", "transcribe"}


def __getattr__(name: str):
    if name in _LAZY:
        from yaguwiseai.voice import loop

        return getattr(loop, name)
    raise AttributeError(f"module 'yaguwiseai.voice' has no attribute {name!r}")
