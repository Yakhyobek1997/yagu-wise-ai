"""Contradiction detection for the Compounding Wiki.

When a new source changes what we know about an entity, we don't silently
overwrite: we compare the entity's *prior* page against the *new* synthesis and
flag factual contradictions. This is the compounding-wiki differentiator — no
mainstream RAG surfaces "a new source contradicts a prior claim."

Detection is LLM-based (structured prompt, temperature 0): a relevance
cross-encoder can't do this — two conflicting claims about one entity are both
highly *relevant*. Per the RAG-contradiction literature (arXiv 2504.00180) LLMs
are imperfect validators, so we (a) keep it advisory (flags, never auto-delete),
(b) require a JSON verdict, and (c) fall back to no-flag on any parse failure.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

from auralynq.telemetry import get_logger

if TYPE_CHECKING:
    from auralynq.llm.base import LLM

_log = get_logger("auralynq.wiki.contradiction")

CONTRA_SYSTEM = (
    "You compare two sets of notes about the SAME entity and report only direct "
    "FACTUAL CONTRADICTIONS (a claim that cannot be true if the other is). "
    "Ignore additions, rewordings, or extra detail — those are not contradictions. "
    "Respond with ONLY a JSON array (no prose). Each item: "
    '{"old_claim": "...", "new_claim": "...", "why": "..."}. '
    "If there are no contradictions, respond with []."
)


@dataclass
class Contradiction:
    entity: str
    old_claim: str
    new_claim: str
    why: str = ""
    # When the prior claim was flagged as superseded — the "valid until" signal
    # (invalidate-not-delete: the old claim is kept, dated, never removed).
    flagged_at: str = field(
        default_factory=lambda: _dt.datetime.now(tz=_dt.UTC).isoformat(timespec="seconds")
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    """Pull the first JSON array out of an LLM response; tolerant of surrounding
    prose or code fences. Returns [] on any failure (advisory feature — never
    raise into the ingest path)."""
    if not text:
        return []
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
        return [d for d in data if isinstance(d, dict)]
    except Exception:
        return []


def detect_contradictions(
    entity: str, old_text: str, new_text: str, llm: LLM
) -> list[Contradiction]:
    """Flag factual contradictions between an entity's prior page and its new
    synthesis. Empty when either side is missing or nothing conflicts."""
    old = (old_text or "").strip()
    new = (new_text or "").strip()
    if not old or not new:
        return []
    prompt = (
        f"ENTITY: {entity}\n\n"
        f"EXISTING NOTES:\n{old}\n\n"
        f"NEW NOTES:\n{new}\n\n"
        "Report factual contradictions between EXISTING and NEW as a JSON array."
    )
    try:
        out = llm.generate(prompt, system=CONTRA_SYSTEM, temperature=0.0, max_tokens=512)
    except Exception as e:  # pragma: no cover - provider failure is non-fatal
        _log.warning("wiki.contradiction_llm_failed", entity=entity, error=str(e))
        return []
    items = _extract_json_array(out)
    contradictions: list[Contradiction] = []
    for it in items:
        old_c = str(it.get("old_claim", "")).strip()
        new_c = str(it.get("new_claim", "")).strip()
        if old_c and new_c:
            contradictions.append(
                Contradiction(entity=entity, old_claim=old_c, new_claim=new_c, why=str(it.get("why", "")).strip())
            )
    return contradictions
