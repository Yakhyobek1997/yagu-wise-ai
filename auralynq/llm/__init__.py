"""LLM providers: Ollama / OpenAI / Anthropic with extractive fallback."""

from __future__ import annotations

from auralynq.llm.base import LLM, Context, build_prompt
from auralynq.llm.factory import build_llm, get_llm, resolved_provider
from auralynq.llm.fallback import ExtractiveLLM

__all__ = [
    "LLM",
    "Context",
    "ExtractiveLLM",
    "build_llm",
    "build_prompt",
    "get_llm",
    "resolved_provider",
]
