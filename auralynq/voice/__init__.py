"""Voice: ASR, diarization, VAD, TTS, and the push-to-talk loop.

``loop`` symbols are exposed lazily to avoid an import cycle (loop → agent →
pipeline → ingest → voice). Import ``auralynq.voice.loop`` directly, or access
``auralynq.voice.run_voice_turn`` which resolves on first use.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from auralynq.voice.asr import ASRSegment, Transcript
from auralynq.voice.factory import build_asr, build_tts, resolved_asr, resolved_tts

if TYPE_CHECKING:  # pragma: no cover
    from auralynq.voice.loop import VoiceTurnResult, run_voice_turn, transcribe

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
        from auralynq.voice import loop

        return getattr(loop, name)
    raise AttributeError(f"module 'auralynq.voice' has no attribute {name!r}")
