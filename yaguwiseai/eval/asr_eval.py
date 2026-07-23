"""ASR evaluation: Word Error Rate via jiwer (optional) or a built-in Levenshtein."""

from __future__ import annotations

import re
from dataclasses import dataclass


def _normalize(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).split()


def _levenshtein_words(ref: list[str], hyp: list[str]) -> int:
    m, n = len(ref), len(hyp)
    if m == 0:
        return n
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        cur = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[n]


def word_error_rate(reference: str, hypothesis: str) -> float:
    try:  # pragma: no cover - optional
        import jiwer

        return float(jiwer.wer(reference, hypothesis))
    except ImportError:
        ref, hyp = _normalize(reference), _normalize(hypothesis)
        if not ref:
            return 0.0 if not hyp else 1.0
        return _levenshtein_words(ref, hyp) / len(ref)


@dataclass
class ASRScores:
    wer: float
    n: int
    provider: str


def evaluate_asr(pairs: list[tuple[str, str]], provider: str = "null") -> ASRScores:
    """pairs: [(reference, hypothesis)]."""
    if not pairs:
        return ASRScores(wer=0.0, n=0, provider=provider)
    total = sum(word_error_rate(ref, hyp) for ref, hyp in pairs) / len(pairs)
    return ASRScores(wer=round(total, 4), n=len(pairs), provider=provider)
