"""Voice activity detection: Silero VAD (optional) + energy-based fallback."""

from __future__ import annotations

from dataclasses import dataclass

from auralynq.telemetry import get_logger

_log = get_logger("auralynq.voice.vad")


@dataclass
class SpeechRegion:
    start_s: float
    end_s: float


def detect_speech(samples, sample_rate: int = 16_000) -> list[SpeechRegion]:
    """Return speech regions. Tries Silero; falls back to RMS energy gating."""
    try:  # pragma: no cover - optional
        return _silero(samples, sample_rate)
    except Exception:
        return _energy(samples, sample_rate)


def _silero(samples, sample_rate):  # pragma: no cover - optional
    import torch
    from silero_vad import get_speech_timestamps, load_silero_vad

    model = load_silero_vad()
    ts = get_speech_timestamps(torch.as_tensor(samples), model, sampling_rate=sample_rate)
    return [SpeechRegion(t["start"] / sample_rate, t["end"] / sample_rate) for t in ts]


def _energy(samples, sample_rate: int) -> list[SpeechRegion]:
    import numpy as np

    arr = np.asarray(samples, dtype=np.float32)
    if arr.size == 0:
        return []
    if arr.max() > 1.5:  # int16 range → normalise
        arr = arr / 32768.0
    win = max(int(0.03 * sample_rate), 1)
    n_win = max(arr.size // win, 1)
    rms = np.array(
        [float(np.sqrt(np.mean(arr[i * win : (i + 1) * win] ** 2) + 1e-9)) for i in range(n_win)]
    )
    thresh = max(0.02, float(rms.mean()) * 0.6)
    active = rms > thresh
    regions: list[SpeechRegion] = []
    start = None
    for i, a in enumerate(active):
        t = i * win / sample_rate
        if a and start is None:
            start = t
        elif not a and start is not None:
            regions.append(SpeechRegion(start, t))
            start = None
    if start is not None:
        regions.append(SpeechRegion(start, arr.size / sample_rate))
    return regions
