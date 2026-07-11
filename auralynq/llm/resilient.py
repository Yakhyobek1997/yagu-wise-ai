"""Resilient LLM wrapper.

Wraps a primary (commercial/networked) LLM and transparently falls back to the
offline :class:`ExtractiveLLM` if the primary raises at request time — e.g. an
expired key, inactive billing (429), rate limit, model-not-found, or a network
blip. This upholds ADR-0003's guarantee that a missing/broken paid backend never
breaks the grounded answer path; the answer just degrades to extractive instead
of 500-ing. The fallback event is logged and surfaced via ``last_fallback``.
"""

from __future__ import annotations

from collections.abc import Iterator

from auralynq.llm.base import LLM, Context
from auralynq.llm.fallback import ExtractiveLLM
from auralynq.telemetry import get_logger

_log = get_logger("auralynq.llm.resilient")


class ResilientLLM(LLM):
    def __init__(self, primary: LLM) -> None:
        self.primary = primary
        self._fallback = ExtractiveLLM()
        self.name = primary.name
        self.last_fallback: str | None = None

    def generate(self, prompt, *, system=None, temperature=None, max_tokens=None) -> str:
        try:
            return self.primary.generate(
                prompt, system=system, temperature=temperature, max_tokens=max_tokens
            )
        except Exception as exc:  # any provider/runtime error → degrade, don't 500
            self.last_fallback = type(exc).__name__
            _log.warning(
                "llm.runtime_fallback_extractive", provider=self.primary.name, error=str(exc)[:200]
            )
            return self._fallback.generate(prompt)

    def answer(self, question: str, contexts: list[Context], **kw) -> str:
        try:
            return self.primary.answer(question, contexts, **kw)
        except Exception as exc:
            self.last_fallback = type(exc).__name__
            _log.warning(
                "llm.runtime_fallback_extractive", provider=self.primary.name, error=str(exc)[:200]
            )
            return self._fallback.answer(question, contexts)

    def stream_answer(self, question: str, contexts: list[Context], **kw) -> Iterator[str]:
        # Buffer the primary stream so a mid-stream failure can cleanly switch to
        # the fallback without emitting a half-answer.
        try:
            chunks = list(self.primary.stream_answer(question, contexts, **kw))
        except Exception as exc:
            self.last_fallback = type(exc).__name__
            _log.warning(
                "llm.runtime_fallback_extractive", provider=self.primary.name, error=str(exc)[:200]
            )
            yield from self._fallback.stream_answer(question, contexts)
            return
        yield from chunks
