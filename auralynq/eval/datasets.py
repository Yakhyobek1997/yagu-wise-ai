"""Golden eval set loading + a built-in frozen fallback set.

The frozen golden set is the source of truth for the drift check: results are
compared against a stored baseline so regressions are caught (ADR-0010).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from auralynq.config import get_settings


@dataclass
class GoldenItem:
    id: str
    question: str
    answer: str
    supporting: list[str] = field(default_factory=list)
    type: str = "single"


@dataclass
class ASRRef:
    audio: str
    reference: str


_BUILTIN = [
    GoldenItem("b1", "What is the capital of France?", "Paris", ["geography"], "single"),
    GoldenItem(
        "b2",
        "How does PathRAG prune relational paths?",
        "Flow-based resource-allocation pruning.",
        ["pathrag"],
        "single",
    ),
    GoldenItem(
        "b3",
        "What removes redundant retrieved chunks in Auralynq?",
        "Maximal marginal relevance.",
        ["auralynq"],
        "single",
    ),
]


def load_golden() -> list[GoldenItem]:
    path = get_settings().data_dir / "golden" / "golden_qa.json"
    if not path.exists():
        return list(_BUILTIN)
    data = json.loads(path.read_text(encoding="utf-8"))
    items = [
        GoldenItem(
            id=i["id"],
            question=i["question"],
            answer=str(i.get("answer", "")),
            supporting=i.get("supporting", []),
            type=i.get("type", "single"),
        )
        for i in data.get("items", [])
    ]
    return items or list(_BUILTIN)


def load_asr_refs() -> list[ASRRef]:
    path = get_settings().data_dir / "golden" / "asr_refs.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [ASRRef(audio=i["audio"], reference=i["reference"]) for i in data.get("items", [])]
