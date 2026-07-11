"""TTS provider interface + Kokoro-82M backend + offline tone/silent fallback.

The fallback synthesises a short, deterministic audio cue (so the voice path is
exercised end-to-end without model downloads) and writes a real WAV file.
"""

from __future__ import annotations

import abc
import math
import struct
import wave
from dataclasses import dataclass
from pathlib import Path

from auralynq.telemetry import get_logger

_log = get_logger("auralynq.voice.tts")


@dataclass
class TTSResult:
    audio_path: Path
    sample_rate: int
    duration_s: float
    provider: str


class TTSProvider(abc.ABC):
    name = "base"

    @abc.abstractmethod
    def synthesize(self, text: str, out_path: Path) -> TTSResult: ...


class NullTTS(TTSProvider):
    """Writes a short, deterministic WAV (a soft beep) — no model required."""

    name = "null"

    def __init__(self, sample_rate: int = 16_000) -> None:
        self.sample_rate = sample_rate

    def synthesize(self, text: str, out_path: Path) -> TTSResult:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Duration proportional to text length, capped — purely indicative.
        duration = min(0.4 + len(text) / 400.0, 4.0)
        n = int(self.sample_rate * duration)
        with wave.open(str(out_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            frames = bytearray()
            for i in range(n):
                val = int(
                    3000 * math.sin(2 * math.pi * 440 * i / self.sample_rate) * math.exp(-3 * i / n)
                )
                frames += struct.pack("<h", val)
            wf.writeframes(bytes(frames))
        return TTSResult(out_path, self.sample_rate, duration, "null")


class KokoroTTS(TTSProvider):  # pragma: no cover - optional heavy path
    name = "kokoro"

    def __init__(self, voice: str = "af_heart", sample_rate: int = 24_000) -> None:
        from kokoro import KPipeline  # type: ignore

        self._pipe = KPipeline(lang_code="a")
        self.voice = voice
        self.sample_rate = sample_rate
        _log.info("tts.kokoro.loaded", voice=voice)

    def synthesize(self, text: str, out_path: Path) -> TTSResult:
        import numpy as np
        import soundfile as sf

        audio = np.concatenate([chunk for _, _, chunk in self._pipe(text, voice=self.voice)])
        sf.write(str(out_path), audio, self.sample_rate)
        return TTSResult(Path(out_path), self.sample_rate, len(audio) / self.sample_rate, "kokoro")
