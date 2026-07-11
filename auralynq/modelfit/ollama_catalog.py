"""Ollama model catalog for Auralynq ModelFit Index.

Fetches the list of locally installed models from Ollama's REST API.
Only reads data — never triggers downloads. If Ollama is not running,
returns an empty list with a warning rather than raising.
"""

from __future__ import annotations

from typing import Any

from auralynq.modelfit.model_metadata import ModelMetadata

_OLLAMA_BASE = "http://localhost:11434"

# Static knowledge about common Ollama model families
_FAMILY_HINTS: dict[str, str] = {
    "llama": "llama",
    "mistral": "mistral",
    "mixtral": "mistral",
    "gemma": "gemma",
    "phi": "phi",
    "qwen": "qwen",
    "deepseek": "deepseek",
    "falcon": "falcon",
    "nomic": "unknown",
    "mxbai": "unknown",
    "all-minilm": "unknown",
    "bge": "unknown",
}

_EMBEDDING_TAGS = {"nomic-embed", "mxbai-embed", "all-minilm", "bge-m3", "bge-large", "bge-small"}
_RERANKER_TAGS = {"bge-reranker", "jina-reranker"}

# Parameter count hints based on common Ollama tag suffixes
_PARAM_HINTS: dict[str, float] = {
    "1b": 1.0,
    "1.1b": 1.1,
    "1.5b": 1.5,
    "2b": 2.0,
    "2.7b": 2.7,
    "3b": 3.0,
    "3.8b": 3.8,
    "7b": 7.0,
    "8b": 8.0,
    "9b": 9.0,
    "13b": 13.0,
    "14b": 14.0,
    "27b": 27.0,
    "30b": 30.0,
    "32b": 32.0,
    "34b": 34.0,
    "70b": 70.0,
    "72b": 72.0,
    "110b": 110.0,
    "671b": 671.0,
}

_CONTEXT_HINTS: dict[str, int] = {
    "llama3": 128000,
    "llama3.1": 128000,
    "llama3.2": 128000,
    "llama3.3": 128000,
    "mistral": 32768,
    "mixtral": 32768,
    "gemma2": 8192,
    "gemma3": 131072,
    "phi3": 128000,
    "phi4": 16384,
    "qwen2": 32768,
    "qwen2.5": 131072,
    "deepseek": 65536,
}

_VISION_TAGS = {"llama3.2-vision", "llava", "bakllava", "moondream", "minicpm-v"}
_TOOL_CALLING_TAGS = {"llama3.1", "llama3.2", "llama3.3", "mistral", "qwen2", "qwen2.5"}


def _infer_family(tag: str) -> str:
    lower = tag.lower()
    for key, family in _FAMILY_HINTS.items():
        if key in lower:
            return family
    return "unknown"


def _infer_params(tag: str) -> float | None:
    lower = tag.lower()
    for suffix, count in _PARAM_HINTS.items():
        if f":{suffix}" in lower or f"-{suffix}" in lower:
            return count
    return None


def _infer_context(tag: str) -> int | None:
    lower = tag.lower()
    for key, ctx in _CONTEXT_HINTS.items():
        if key in lower:
            return ctx
    return None


def _is_embedding(tag: str) -> bool:
    lower = tag.lower()
    return any(e in lower for e in _EMBEDDING_TAGS)


def _is_reranker(tag: str) -> bool:
    lower = tag.lower()
    return any(r in lower for r in _RERANKER_TAGS)


def _is_vision(tag: str) -> bool:
    lower = tag.lower()
    return any(v in lower for v in _VISION_TAGS)


def _has_tool_calling(tag: str) -> bool:
    lower = tag.lower()
    return any(t in lower for t in _TOOL_CALLING_TAGS)


def _tag_to_metadata(tag: str, size_bytes: int | None = None) -> ModelMetadata:
    family = _infer_family(tag)
    params = _infer_params(tag)
    ctx = _infer_context(tag)
    embedding = _is_embedding(tag)
    reranker = _is_reranker(tag)
    vision = _is_vision(tag)
    tool_calling = _has_tool_calling(tag)

    tasks: list[Any] = []
    if not embedding and not reranker:
        tasks = ["chat", "rag", "summarization"]
        if tool_calling:
            tasks.append("agents")
        if vision:
            tasks.append("vision")

    quants: list[Any] = ["q4_k", "q8", "fp16"]

    return ModelMetadata(
        model_id=f"ollama:{tag}",
        source="ollama",
        display_name=tag,
        family=family,  # type: ignore[arg-type]
        parameter_count_b=params,
        context_length=ctx,
        license="varies",
        gated=False,
        tasks=tasks,
        available_quantizations=quants,
        embedding=embedding,
        reranker=reranker,
        supports_adapters=False,
        vision=vision,
        tool_calling=tool_calling,
        multilingual="qwen" in tag.lower() or "mistral" in tag.lower(),
        ollama_tag=tag,
        notes=[f"Disk size: {size_bytes // (1024**3):.1f} GB" if size_bytes else "Size unknown"],
    )


async def list_installed_models() -> tuple[list[ModelMetadata], list[str]]:
    """Fetch locally installed Ollama models without triggering any downloads."""
    warnings: list[str] = []
    models: list[ModelMetadata] = []

    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{_OLLAMA_BASE}/api/tags")
            if response.status_code != 200:
                warnings.append(f"Ollama returned HTTP {response.status_code}.")
                return models, warnings
            data = response.json()
    except Exception as exc:
        warnings.append(f"Ollama not reachable: {exc}")
        return models, warnings

    for entry in data.get("models", []):
        tag = entry.get("name", "")
        size = entry.get("size")
        if tag:
            models.append(_tag_to_metadata(tag, size))

    return models, warnings


async def get_model_details(tag: str) -> tuple[ModelMetadata | None, list[str]]:
    """Fetch show-info for a specific tag from local Ollama."""
    warnings: list[str] = []
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{_OLLAMA_BASE}/api/show",
                json={"name": tag},
            )
            if response.status_code != 200:
                warnings.append(f"Model '{tag}' not found in local Ollama.")
                return None, warnings
    except Exception as exc:
        warnings.append(f"Ollama not reachable: {exc}")
        return None, warnings

    meta = _tag_to_metadata(tag)
    return meta, warnings


def get_static_catalog() -> list[ModelMetadata]:
    """Return a curated list of well-known models with static metadata.

    These entries are not fabricated benchmark numbers — they are publicly
    documented model specs (parameter counts, context lengths, licenses).
    """
    catalog = [
        ModelMetadata(
            model_id="ollama:llama3.2:1b",
            source="ollama",
            display_name="Llama 3.2 1B",
            family="llama",
            parameter_count_b=1.0,
            context_length=128000,
            license="Llama 3.2 Community",
            gated=False,
            tasks=["chat", "rag", "summarization"],
            available_quantizations=["q4_k", "q8", "fp16"],
            supports_adapters=True,
            tool_calling=False,
            ollama_tag="llama3.2:1b",
            notes=["Ultra-lightweight; good for resource-constrained environments."],
        ),
        ModelMetadata(
            model_id="ollama:llama3.2:3b",
            source="ollama",
            display_name="Llama 3.2 3B",
            family="llama",
            parameter_count_b=3.0,
            context_length=128000,
            license="Llama 3.2 Community",
            gated=False,
            tasks=["chat", "rag", "summarization"],
            available_quantizations=["q4_k", "q8", "fp16"],
            supports_adapters=True,
            tool_calling=False,
            ollama_tag="llama3.2:3b",
            notes=["Excellent size/quality tradeoff for consumer hardware."],
        ),
        ModelMetadata(
            model_id="ollama:llama3.1:8b",
            source="ollama",
            display_name="Llama 3.1 8B",
            family="llama",
            parameter_count_b=8.0,
            context_length=128000,
            license="Llama 3.1 Community",
            gated=False,
            tasks=["chat", "rag", "summarization", "coding", "agents"],
            available_quantizations=["q4_k", "q5_k", "q8", "fp16"],
            supports_adapters=True,
            tool_calling=True,
            ollama_tag="llama3.1:8b",
            notes=["Strong general-purpose model with tool-calling support."],
        ),
        ModelMetadata(
            model_id="ollama:llama3.3:70b",
            source="ollama",
            display_name="Llama 3.3 70B",
            family="llama",
            parameter_count_b=70.0,
            context_length=128000,
            license="Llama 3.3 Community",
            gated=False,
            tasks=["chat", "rag", "summarization", "coding", "agents"],
            available_quantizations=["q4_k", "q8"],
            supports_adapters=True,
            tool_calling=True,
            ollama_tag="llama3.3:70b",
            notes=["High quality; requires ~40 GB VRAM at q4_k."],
        ),
        ModelMetadata(
            model_id="ollama:mistral:7b",
            source="ollama",
            display_name="Mistral 7B",
            family="mistral",
            parameter_count_b=7.0,
            context_length=32768,
            license="Apache-2.0",
            gated=False,
            tasks=["chat", "rag", "summarization", "coding"],
            available_quantizations=["q4_k", "q5_k", "q8", "fp16"],
            supports_adapters=True,
            tool_calling=True,
            multilingual=True,
            ollama_tag="mistral:7b",
            notes=["Efficient and multilingual; Apache-2.0 license."],
        ),
        ModelMetadata(
            model_id="ollama:gemma3:4b",
            source="ollama",
            display_name="Gemma 3 4B",
            family="gemma",
            parameter_count_b=4.0,
            context_length=131072,
            license="Gemma Terms",
            gated=False,
            tasks=["chat", "rag", "summarization"],
            available_quantizations=["q4_k", "q8", "fp16"],
            supports_adapters=True,
            ollama_tag="gemma3:4b",
            notes=["Long context (128K); compact and fast."],
        ),
        ModelMetadata(
            model_id="ollama:gemma3:12b",
            source="ollama",
            display_name="Gemma 3 12B",
            family="gemma",
            parameter_count_b=12.0,
            context_length=131072,
            license="Gemma Terms",
            gated=False,
            tasks=["chat", "rag", "summarization", "coding"],
            available_quantizations=["q4_k", "q8", "fp16"],
            supports_adapters=True,
            ollama_tag="gemma3:12b",
        ),
        ModelMetadata(
            model_id="ollama:qwen2.5:7b",
            source="ollama",
            display_name="Qwen 2.5 7B",
            family="qwen",
            parameter_count_b=7.0,
            context_length=131072,
            license="Qwen License",
            gated=False,
            tasks=["chat", "rag", "summarization", "coding", "agents"],
            available_quantizations=["q4_k", "q8", "fp16"],
            supports_adapters=True,
            tool_calling=True,
            multilingual=True,
            ollama_tag="qwen2.5:7b",
            notes=["Strong multilingual support; 128K context."],
        ),
        ModelMetadata(
            model_id="ollama:qwen2.5:14b",
            source="ollama",
            display_name="Qwen 2.5 14B",
            family="qwen",
            parameter_count_b=14.0,
            context_length=131072,
            license="Qwen License",
            gated=False,
            tasks=["chat", "rag", "summarization", "coding", "agents"],
            available_quantizations=["q4_k", "q8", "fp16"],
            supports_adapters=True,
            tool_calling=True,
            multilingual=True,
            ollama_tag="qwen2.5:14b",
        ),
        ModelMetadata(
            model_id="ollama:phi4:14b",
            source="ollama",
            display_name="Phi-4 14B",
            family="phi",
            parameter_count_b=14.0,
            context_length=16384,
            license="MIT",
            gated=False,
            tasks=["chat", "rag", "summarization", "coding", "math"],
            available_quantizations=["q4_k", "q8", "fp16"],
            supports_adapters=True,
            ollama_tag="phi4:14b",
            notes=["MIT license; strong at coding and math."],
        ),
        ModelMetadata(
            model_id="ollama:deepseek-r1:7b",
            source="ollama",
            display_name="DeepSeek-R1 7B",
            family="deepseek",
            parameter_count_b=7.0,
            context_length=65536,
            license="MIT",
            gated=False,
            tasks=["chat", "rag", "coding", "math"],
            available_quantizations=["q4_k", "q8", "fp16"],
            supports_adapters=True,
            ollama_tag="deepseek-r1:7b",
            notes=["Chain-of-thought reasoning model; MIT license."],
        ),
        ModelMetadata(
            model_id="ollama:nomic-embed-text",
            source="ollama",
            display_name="Nomic Embed Text",
            family="unknown",
            parameter_count_b=0.137,
            context_length=8192,
            license="Apache-2.0",
            gated=False,
            tasks=[],
            available_quantizations=["fp16"],
            embedding=True,
            ollama_tag="nomic-embed-text",
            notes=["High-quality local embedding model; Apache-2.0."],
        ),
        ModelMetadata(
            model_id="ollama:mxbai-embed-large",
            source="ollama",
            display_name="MxBai Embed Large",
            family="unknown",
            parameter_count_b=0.335,
            context_length=512,
            license="Apache-2.0",
            gated=False,
            tasks=[],
            available_quantizations=["fp16"],
            embedding=True,
            ollama_tag="mxbai-embed-large",
            notes=["MTEB top performer for local embeddings; Apache-2.0."],
        ),
        ModelMetadata(
            model_id="ollama:llama3.2-vision:11b",
            source="ollama",
            display_name="Llama 3.2 Vision 11B",
            family="llama",
            parameter_count_b=11.0,
            context_length=128000,
            license="Llama 3.2 Community",
            gated=False,
            tasks=["chat", "rag", "vision"],
            available_quantizations=["q4_k", "q8"],
            supports_adapters=True,
            vision=True,
            ollama_tag="llama3.2-vision:11b",
            notes=["Multimodal; supports image input for visual document QA."],
        ),
    ]
    return catalog
