"""Knowledge-graph builder.

Deterministic, dependency-free extraction so the KG is reproducible and testable
offline (ADR-0003): proper-noun / capitalised phrase entities, and intra-sentence
relations labelled by the connecting verb/preposition phrase. Provenance (chunk,
span, speaker, timestamp) is recorded on every edge for honest citations.

An LLM-based extractor can be layered on later behind the same interface; this
rule-based path is the $0 default.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from auralynq.ingest.models import Chunk
from auralynq.retrieval.pathrag.graph import KnowledgeGraph, Provenance
from auralynq.utils import sentence_split

# Capitalised phrase (allows internal lowercase tokens for multiword names).
_ENTITY_RE = re.compile(r"\b([A-Z][\w’'-]*(?:\s+(?:of|the|de|van|von|al)?\s*[A-Z][\w’'-]*)*)\b")
_REL_STOP = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "of",
    "in",
    "on",
    "at",
    "to",
    "and",
    "or",
    "that",
    "which",
    "this",
    "it",
    "as",
}
_LEADING_DET = re.compile(r"^(The|A|An|This|That|These|Those|It|Its)\s+")
_REL_WORDS = re.compile(
    r"\b(is|are|was|were|has|have|uses?|prunes?|scores?|combines?|"
    r"removes?|flows?|capital|part|located|belongs?|produces?|"
    r"performs?|expands?|retrieves?|fuses?|ranks?)\b",
    re.IGNORECASE,
)


def _entities_in(sentence: str) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for m in _ENTITY_RE.finditer(sentence):
        raw = " ".join(m.group(1).split())  # collapse internal whitespace/newlines
        raw = _LEADING_DET.sub("", raw).strip()
        if len(raw) < 3 or raw.lower() in _REL_STOP:
            continue
        found.append((raw, m.start()))
    return found


def _relation_label(sentence: str, a_end: int, b_start: int) -> str:
    span = sentence[a_end:b_start].lower()
    m = _REL_WORDS.search(span)
    if m:
        # Capture a short phrase around the matched verb/preposition.
        words = [w for w in re.findall(r"[a-z]+", span) if w not in {"the", "a", "an"}]
        if words:
            return "_".join(words[:3])
        return m.group(1).lower()
    return "related_to"


def build_from_chunks(chunks: Iterable[Chunk]) -> KnowledgeGraph:
    kg = KnowledgeGraph()
    for ch in chunks:
        prov_loc = ch.locator()
        speaker = ch.audio.speaker if ch.audio else None
        start_s = ch.audio.start_s if ch.audio else None
        for sentence in sentence_split(ch.text):
            ents = _entities_in(sentence)
            for name, _ in ents:
                kg.add_entity(name, chunk_id=ch.id)
            # Pairwise relations between consecutive entities in the sentence.
            for i in range(len(ents) - 1):
                (a, a_start), (b, b_start) = ents[i], ents[i + 1]
                a_end = a_start + len(a)
                rel = _relation_label(sentence, a_end, b_start)
                prov = Provenance(
                    chunk_id=ch.id,
                    source=ch.source or ch.doc_id,
                    locator=prov_loc,
                    speaker=speaker,
                    start_s=start_s,
                )
                kg.add_relation(a, b, rel, prov)
    kg.finalize()
    return kg
