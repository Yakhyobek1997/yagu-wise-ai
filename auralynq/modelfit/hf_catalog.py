"""Hugging Face model catalog for Auralynq ModelFit Index.

Provides a curated static list of well-known HF models for local deployment.
Network access to the HF Hub is opt-in only — the static catalog works offline.
All metadata comes from official model cards, not fabricated estimates.
"""

from __future__ import annotations

from auralynq.modelfit.model_metadata import ModelMetadata


def get_static_hf_catalog() -> list[ModelMetadata]:
    """Return curated HF model entries with publicly documented specs."""
    return [
        ModelMetadata(
            model_id="hf:meta-llama/Meta-Llama-3.1-8B-Instruct",
            source="huggingface",
            display_name="Llama 3.1 8B Instruct (HF)",
            family="llama",
            parameter_count_b=8.0,
            context_length=128000,
            license="Llama 3.1 Community",
            gated=True,
            tasks=["chat", "rag", "summarization", "coding", "agents"],
            available_quantizations=["fp16", "bf16", "int8", "q4_k", "q8"],
            supports_adapters=True,
            tool_calling=True,
            hf_repo="meta-llama/Meta-Llama-3.1-8B-Instruct",
            notes=["Gated model — requires HF account approval.", "Run GGUF via Ollama."],
        ),
        ModelMetadata(
            model_id="hf:microsoft/Phi-3.5-mini-instruct",
            source="huggingface",
            display_name="Phi-3.5 Mini Instruct (HF)",
            family="phi",
            parameter_count_b=3.8,
            context_length=131072,
            license="MIT",
            gated=False,
            tasks=["chat", "rag", "summarization", "coding"],
            available_quantizations=["fp16", "bf16", "int8", "q4_k"],
            supports_adapters=True,
            hf_repo="microsoft/Phi-3.5-mini-instruct",
            notes=["MIT license; 128K context; very compact."],
        ),
        ModelMetadata(
            model_id="hf:Qwen/Qwen2.5-7B-Instruct",
            source="huggingface",
            display_name="Qwen 2.5 7B Instruct (HF)",
            family="qwen",
            parameter_count_b=7.0,
            context_length=131072,
            license="Qwen License",
            gated=False,
            tasks=["chat", "rag", "summarization", "coding", "agents"],
            available_quantizations=["fp16", "bf16", "int8", "q4_k", "q8"],
            supports_adapters=True,
            tool_calling=True,
            multilingual=True,
            hf_repo="Qwen/Qwen2.5-7B-Instruct",
        ),
        ModelMetadata(
            model_id="hf:mistralai/Mistral-7B-Instruct-v0.3",
            source="huggingface",
            display_name="Mistral 7B Instruct v0.3 (HF)",
            family="mistral",
            parameter_count_b=7.0,
            context_length=32768,
            license="Apache-2.0",
            gated=False,
            tasks=["chat", "rag", "summarization", "coding"],
            available_quantizations=["fp16", "bf16", "int8", "q4_k", "q8"],
            supports_adapters=True,
            tool_calling=True,
            multilingual=True,
            hf_repo="mistralai/Mistral-7B-Instruct-v0.3",
            notes=["Apache-2.0 license; function calling supported."],
        ),
        ModelMetadata(
            model_id="hf:BAAI/bge-m3",
            source="huggingface",
            display_name="BGE-M3 Embedding (HF)",
            family="unknown",
            parameter_count_b=0.568,
            context_length=8192,
            license="MIT",
            gated=False,
            tasks=[],
            available_quantizations=["fp16", "fp32"],
            embedding=True,
            multilingual=True,
            hf_repo="BAAI/bge-m3",
            notes=["Top multilingual embedding model; MIT license."],
        ),
        ModelMetadata(
            model_id="hf:BAAI/bge-reranker-v2-m3",
            source="huggingface",
            display_name="BGE Reranker v2 M3 (HF)",
            family="unknown",
            parameter_count_b=0.568,
            context_length=8192,
            license="MIT",
            gated=False,
            tasks=[],
            available_quantizations=["fp16", "fp32"],
            reranker=True,
            multilingual=True,
            hf_repo="BAAI/bge-reranker-v2-m3",
            notes=["Cross-encoder reranker; MIT license."],
        ),
        ModelMetadata(
            model_id="hf:google/gemma-2-9b-it",
            source="huggingface",
            display_name="Gemma 2 9B IT (HF)",
            family="gemma",
            parameter_count_b=9.0,
            context_length=8192,
            license="Gemma Terms",
            gated=True,
            tasks=["chat", "rag", "summarization"],
            available_quantizations=["fp16", "bf16", "int8", "q4_k"],
            supports_adapters=True,
            hf_repo="google/gemma-2-9b-it",
            notes=["Gated model — requires HF account approval."],
        ),
        ModelMetadata(
            model_id="hf:deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
            source="huggingface",
            display_name="DeepSeek-R1-Distill-Qwen-7B (HF)",
            family="deepseek",
            parameter_count_b=7.0,
            context_length=131072,
            license="MIT",
            gated=False,
            tasks=["chat", "rag", "coding", "math"],
            available_quantizations=["fp16", "bf16", "int8", "q4_k"],
            supports_adapters=True,
            hf_repo="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
            notes=["Chain-of-thought distillation; MIT license."],
        ),
    ]


async def search_hf_models(
    query: str,
    limit: int = 10,
) -> tuple[list[ModelMetadata], list[str]]:
    """Search HF Hub by keyword. Requires network access; degraded gracefully."""
    warnings: list[str] = []
    results: list[ModelMetadata] = []

    try:
        import httpx

        url = "https://huggingface.co/api/models"
        params = {"search": query, "limit": str(limit), "sort": "downloads", "direction": "-1"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                warnings.append(f"HF search returned HTTP {resp.status_code}.")
                return results, warnings
            data = resp.json()
    except Exception as exc:
        warnings.append(f"HF Hub not reachable: {exc}. Showing static catalog only.")
        return results, warnings

    for entry in data:
        repo_id = entry.get("modelId") or entry.get("id", "")
        if not repo_id:
            continue
        tags = entry.get("tags", [])
        gated = entry.get("gated", False)
        results.append(
            ModelMetadata(
                model_id=f"hf:{repo_id}",
                source="huggingface",
                display_name=repo_id,
                family="unknown",
                license=entry.get("license", "unknown"),
                gated=bool(gated),
                tasks=[],
                embedding="feature-extraction" in tags,
                hf_repo=repo_id,
                notes=["Retrieved live from HF Hub — metadata may be incomplete."],
            )
        )

    return results, warnings
