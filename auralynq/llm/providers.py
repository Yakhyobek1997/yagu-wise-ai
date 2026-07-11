"""LLM provider implementations.

Local providers (no API key, no egress):
  OllamaLLM  — HTTP to a running Ollama daemon (GPU/CPU handled by the daemon).
  SLMLlm     — llama-cpp-python + GGUF; GPU layers when CUDA is present, CPU otherwise.

Cloud providers (require keys + network):
  OpenAILLM, AnthropicLLM, CohereLLM.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx

from auralynq.llm.base import LLM
from auralynq.telemetry import get_logger

_log = get_logger("auralynq.llm")


class OllamaLLM(LLM):
    name = "ollama"

    def __init__(self, model: str, base_url: str) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    def _payload(self, prompt: str, system: str | None, temperature, max_tokens, stream: bool):
        return {
            "model": self.model,
            "prompt": prompt,
            "system": system or "",
            "stream": stream,
            "options": {
                "temperature": temperature if temperature is not None else 0.1,
                "num_predict": max_tokens or 1024,
            },
        }

    def generate(self, prompt, *, system=None, temperature=None, max_tokens=None) -> str:
        resp = httpx.post(
            f"{self.base_url}/api/generate",
            json=self._payload(prompt, system, temperature, max_tokens, False),
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()

    def stream(self, prompt, *, system=None, temperature=None, max_tokens=None) -> Iterator[str]:
        import json as _json

        with httpx.stream(
            "POST",
            f"{self.base_url}/api/generate",
            json=self._payload(prompt, system, temperature, max_tokens, True),
            timeout=120,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = _json.loads(line)
                if chunk.get("response"):
                    yield chunk["response"]
                if chunk.get("done"):
                    break


class SLMLlm(LLM):  # pragma: no cover - requires llama-cpp-python install
    """Local GGUF Small Language Model via llama-cpp-python.

    n_gpu_layers controls hardware:
      -1  → offload all layers to GPU (fast; requires a CUDA/Metal build of llama-cpp-python)
       0  → pure CPU inference (slower but always works)
       N  → offload N transformer blocks to GPU (partial offload for low-VRAM cards)

    Use auralynq.llm.slm.resolve_n_gpu_layers() to auto-select 0 vs -1 based on
    nvidia-smi before constructing this class.
    """

    name = "slm"

    def __init__(self, model_path: str, n_gpu_layers: int = 0, n_ctx: int = 4096) -> None:
        from llama_cpp import Llama  # type: ignore[import-untyped]

        self._llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            verbose=False,
            chat_format="chatml",  # compatible with Qwen, Phi-3, LLaMA-3 chat GGUFs
        )
        self.model_path = model_path
        self.n_gpu_layers = n_gpu_layers
        _log.info("slm.loaded", model=model_path, n_gpu_layers=n_gpu_layers)

    def _messages(self, prompt: str, system: str | None) -> list[dict]:
        msgs: list[dict] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        return msgs

    def generate(self, prompt, *, system=None, temperature=None, max_tokens=None) -> str:
        # llama-cpp-python's create_chat_completion has strict TypedDict message
        # types and a union return; our plain-dict messages and indexing are
        # correct at runtime, so we treat the response as Any.
        resp: Any = self._llm.create_chat_completion(
            messages=self._messages(prompt, system),  # type: ignore[arg-type]
            temperature=temperature if temperature is not None else 0.1,
            max_tokens=max_tokens or 1024,
            stream=False,
        )
        return (resp["choices"][0]["message"]["content"] or "").strip()

    def stream(self, prompt, *, system=None, temperature=None, max_tokens=None) -> Iterator[str]:
        stream_resp: Any = self._llm.create_chat_completion(
            messages=self._messages(prompt, system),  # type: ignore[arg-type]
            temperature=temperature if temperature is not None else 0.1,
            max_tokens=max_tokens or 1024,
            stream=True,
        )
        for chunk in stream_resp:
            delta = chunk["choices"][0]["delta"].get("content", "")
            if delta:
                yield delta


class OpenAILLM(LLM):  # pragma: no cover - paid path
    name = "openai"

    def __init__(self, api_key: str, model: str, base_url: str | None = None) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, **({"base_url": base_url} if base_url else {}))
        self.model = model

    def generate(self, prompt, *, system=None, temperature=None, max_tokens=None) -> str:
        msgs = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=msgs,  # type: ignore[arg-type]
            temperature=temperature if temperature is not None else 0.1,
            max_tokens=max_tokens or 1024,
        )
        return resp.choices[0].message.content or ""

    def stream(self, prompt, *, system=None, temperature=None, max_tokens=None) -> Iterator[str]:
        msgs = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        for chunk in self._client.chat.completions.create(
            model=self.model,
            messages=msgs,  # type: ignore[arg-type]
            stream=True,
            temperature=temperature if temperature is not None else 0.1,
        ):
            delta = chunk.choices[0].delta.content  # type: ignore[union-attr]
            if delta:
                yield delta


class HuggingFaceLLM(OpenAILLM):  # pragma: no cover - paid path
    """Powerful hosted models via Hugging Face **Inference Providers**.

    HF exposes an OpenAI-compatible router, so we reuse the OpenAI client with a
    different ``base_url`` and the HF token as the key. Model ids are HF repo ids,
    e.g. ``meta-llama/Llama-3.3-70B-Instruct``. Most large models require a paid /
    PRO account. Optionally pin a specific backend with ``model:provider`` (e.g.
    ``deepseek-ai/DeepSeek-V3:together``); bare ids let HF pick.
    """

    name = "huggingface"
    ROUTER_URL = "https://router.huggingface.co/v1"

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(api_key=api_key, model=model, base_url=self.ROUTER_URL)


class AnthropicLLM(LLM):  # pragma: no cover - paid path
    name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def generate(self, prompt, *, system=None, temperature=None, max_tokens=None) -> str:
        resp = self._client.messages.create(
            model=self.model,
            system=system or "",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature if temperature is not None else 0.1,
            max_tokens=max_tokens or 1024,
        )
        return "".join(b.text for b in resp.content if b.type == "text")

    def stream(self, prompt, *, system=None, temperature=None, max_tokens=None) -> Iterator[str]:
        with self._client.messages.stream(
            model=self.model,
            system=system or "",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature if temperature is not None else 0.1,
            max_tokens=max_tokens or 1024,
        ) as stream:
            yield from stream.text_stream


class CohereLLM(LLM):  # pragma: no cover - paid path
    name = "cohere"

    def __init__(self, api_key: str, model: str = "command-r-08-2024") -> None:
        import cohere

        # Cohere's v2 client exposes a Chat API with role-based messages.
        self._client = cohere.ClientV2(api_key=api_key)
        self.model = model

    def _messages(self, prompt: str, system: str | None) -> list[dict]:
        msgs: list[dict] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        return msgs

    def generate(self, prompt, *, system=None, temperature=None, max_tokens=None) -> str:
        resp = self._client.chat(
            model=self.model,
            messages=self._messages(prompt, system),  # type: ignore[arg-type]
            temperature=temperature if temperature is not None else 0.1,
            max_tokens=max_tokens or 1024,
        )
        # v2 returns message.content as a list of typed blocks (text/thinking);
        # we only join the text blocks (getattr guards non-text variants).
        return "".join(
            getattr(block, "text", "") or "" for block in (resp.message.content or [])
        ).strip()

    def stream(self, prompt, *, system=None, temperature=None, max_tokens=None) -> Iterator[str]:
        for event in self._client.chat_stream(
            model=self.model,
            messages=self._messages(prompt, system),  # type: ignore[arg-type]
            temperature=temperature if temperature is not None else 0.1,
            max_tokens=max_tokens or 1024,
        ):
            if event.type == "content-delta":
                delta = event.delta.message.content.text  # type: ignore[union-attr]
                if delta:
                    yield delta
