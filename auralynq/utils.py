"""Small shared utilities: deterministic IDs, seeding, text helpers."""

from __future__ import annotations

import hashlib
import os
import random
import re
import unicodedata
from collections.abc import Iterable


def stable_id(*parts: object, length: int = 16) -> str:
    """Deterministic short hex id from arbitrary parts (idempotency keys)."""
    h = hashlib.sha256("\x1f".join(str(p) for p in parts).encode("utf-8"))
    return h.hexdigest()[:length]


def content_hash(text: str) -> str:
    """Full content hash used to detect unchanged documents (idempotent ingest)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def seed_everything(seed: int = 42) -> None:
    """Seed Python/NumPy (and torch if present) for reproducibility."""
    os.environ.setdefault("PYTHONHASHSEED", str(seed))
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:  # pragma: no cover
        pass
    try:  # pragma: no cover - torch optional
        import torch

        torch.manual_seed(seed)
    except Exception:
        pass


_WORD_RE = re.compile(r"[a-z0-9]+")


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).strip()


def tokenize(text: str) -> list[str]:
    """Lowercase alnum tokenizer used by sparse/lexical components."""
    return _WORD_RE.findall(text.lower())


def sentence_split(text: str) -> list[str]:
    """Lightweight sentence splitter (no nltk dependency)."""
    text = normalize_text(text)
    if not text:
        return []
    # Split on sentence-ending punctuation followed by whitespace + capital/quote.
    parts = re.split(r"(?<=[.!?])\s+(?=[\"'(A-Z0-9])", text)
    return [p.strip() for p in parts if p.strip()]


def chunked(seq: list, size: int) -> Iterable[list]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]
