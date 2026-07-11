"""LLM provider interface.

Generation is grounded-RAG oriented: the primary entry point is
``answer(question, contexts)`` / ``stream_answer(...)`` where ``contexts`` are
numbered evidence snippets. The default implementation builds a strict grounded
prompt and delegates to ``generate``/``stream``; the extractive fallback overrides
it to quote context directly (citation-faithful, no hallucination).
"""

from __future__ import annotations

import abc
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass
class Context:
    marker: int  # 1-based citation index
    text: str
    source: str = ""
    locator: str = ""


GROUNDED_SYSTEM = (
    "You are Auralynq, an evidence-based research assistant. "
    "Answer exclusively from the numbered evidence provided. "
    "Rules — follow them strictly:\n"
    "1. Open with a direct, complete answer to the question.\n"
    "2. Cite every factual claim inline with [n] markers — at least one per sentence.\n"
    "3. When multiple sources agree, merge them: 'IBM pledged [1][3]…'\n"
    "4. When sources conflict, acknowledge both: '[1] states X; [2] reports Y.'\n"
    "5. Write clear, natural prose — not bullet lists unless the question asks for a list.\n"
    "6. If evidence is insufficient, say exactly: "
    "'The indexed documents do not contain enough information to answer this.'\n"
    "7. Never invent facts. Never exceed what the evidence supports."
)


def build_prompt(question: str, contexts: list[Context]) -> str:
    lines = ["EVIDENCE:"]
    for c in contexts:
        header = f"[{c.marker}]"
        if c.source:
            loc_part = f" · {c.locator}" if c.locator else ""
            header += f"  ({c.source}{loc_part})"
        lines.append(header)
        lines.append(c.text)
        lines.append("")
    lines.append(f"QUESTION: {question}")
    lines.append("")
    lines.append("ANSWER (cite every claim with [n] markers from the evidence above):")
    return "\n".join(lines)


class LLM(abc.ABC):
    name = "base"

    @abc.abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str: ...

    def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        # Default: non-streaming providers yield the whole answer once.
        yield self.generate(prompt, system=system, temperature=temperature, max_tokens=max_tokens)

    def answer(self, question: str, contexts: list[Context], **kw) -> str:
        return self.generate(build_prompt(question, contexts), system=GROUNDED_SYSTEM, **kw)

    def stream_answer(self, question: str, contexts: list[Context], **kw) -> Iterator[str]:
        yield from self.stream(build_prompt(question, contexts), system=GROUNDED_SYSTEM, **kw)
