"""Voice provider factories (ASR/TTS) with ``auto`` resolution + fallbacks."""

from __future__ import annotations

import functools
import importlib.util

from auralynq.config import get_settings
from auralynq.telemetry import get_logger
from auralynq.voice.asr import ASRProvider, FasterWhisperASR, NullASR
from auralynq.voice.tts import KokoroTTS, NullTTS, TTSProvider

_log = get_logger("auralynq.voice")


def _have(pkg: str) -> bool:
    return importlib.util.find_spec(pkg) is not None


def build_asr(provider: str | None = None) -> ASRProvider:
    s = get_settings()
    provider = provider or s.voice.asr_provider
    if provider == "auto":
        provider = "faster_whisper" if _have("faster_whisper") else "null"
    if provider in ("faster_whisper", "whisperx"):
        try:
            return FasterWhisperASR(model=s.voice.asr_model, device=s.embedding.device)
        except Exception as exc:  # pragma: no cover
            _log.warning("asr.fallback_null", error=str(exc))
    return NullASR()


def build_tts(provider: str | None = None) -> TTSProvider:
    s = get_settings()
    provider = provider or s.voice.tts_provider
    if provider == "auto":
        provider = "kokoro" if _have("kokoro") else "null"
    if provider == "kokoro":
        try:
            return KokoroTTS(voice=s.voice.tts_voice)
        except Exception as exc:  # pragma: no cover
            _log.warning("tts.fallback_null", error=str(exc))
    return NullTTS(sample_rate=s.voice.sample_rate)


def resolved_asr() -> str:
    s = get_settings()
    if s.voice.asr_provider != "auto":
        return s.voice.asr_provider
    return "faster_whisper" if _have("faster_whisper") else "null"


def resolved_tts() -> str:
    s = get_settings()
    if s.voice.tts_provider != "auto":
        return s.voice.tts_provider
    return "kokoro" if _have("kokoro") else "null"


@functools.lru_cache(maxsize=1)
def get_asr() -> ASRProvider:
    return build_asr()


@functools.lru_cache(maxsize=1)
def get_tts() -> TTSProvider:
    return build_tts()
