"""Extractive LLM — the $0, citation-faithful fallback (ADR-0003).

Selects the most query-relevant sentences from the provided context and stitches
them into a concise answer, attaching the originating ``[n]`` citation marker to
each. It never invents content, so the citation validator always passes and the
offline demo produces honest grounded answers.
"""

from __future__ import annotations

from collections.abc import Iterator

from auralynq.llm.base import LLM, Context
from auralynq.utils import sentence_split, tokenize

_INSUFFICIENT = "I don't have enough evidence in the indexed sources to answer that confidently."


class ExtractiveLLM(LLM):
    name = "extractive"

    def __init__(self, max_sentences: int = 3) -> None:
        self.max_sentences = max_sentences

    def generate(self, prompt: str, *, system=None, temperature=None, max_tokens=None) -> str:
        # Rarely used directly; return the most informative line of the prompt.
        lines = [ln for ln in prompt.splitlines() if ln.strip()]
        return lines[-1] if lines else ""

    def answer(self, question: str, contexts: list[Context], **kw) -> str:
        q = set(tokenize(question))
        scored: list[tuple[float, int, str]] = []
        for c in contexts:
            for sent in sentence_split(c.text) or [c.text]:
                toks = set(tokenize(sent))
                if not toks:
                    continue
                overlap = len(q & toks)
                # Jaccard-ish relevance with a small length normalisation.
                score = overlap / (len(q | toks) ** 0.5 + 1e-9)
                if overlap:
                    scored.append((score, c.marker, sent.strip()))
        if not scored:
            return _INSUFFICIENT
        scored.sort(reverse=True)
        chosen: list[tuple[int, str]] = []
        seen: set[str] = set()
        for _score, marker, sent in scored:
            key = sent.lower()[:60]
            if key in seen:
                continue
            seen.add(key)
            chosen.append((marker, sent))
            if len(chosen) >= self.max_sentences:
                break
        return " ".join(f"{sent} [{marker}]" for marker, sent in chosen)

    def stream_answer(self, question: str, contexts: list[Context], **kw) -> Iterator[str]:
        answer = self.answer(question, contexts, **kw)
        for token in answer.split(" "):
            yield token + " "
