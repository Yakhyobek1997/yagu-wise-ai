"""Single source of truth for 'what is actually running' (ADR-0004).

Resolves every swappable backend to its concrete provider and reports status, so
``/health`` and ``auralynq info`` are honest about local-vs-upgraded execution.
"""

from __future__ import annotations

from typing import Any

from auralynq.config import get_settings


def describe_providers() -> list[dict[str, str]]:
    from auralynq.embeddings.factory import resolved_provider as emb_provider
    from auralynq.llm.factory import resolved_provider as llm_provider
    from auralynq.telemetry.langfuse_export import langfuse_enabled
    from auralynq.vectorstore.factory import resolved_backend as vec_backend
    from auralynq.voice.factory import resolved_asr, resolved_tts

    s = get_settings()
    tracing = "langfuse+phoenix" if langfuse_enabled() else "in-process"
    ep = emb_provider()
    vb = vec_backend()
    lp = llm_provider()
    # Show the model that is *actually* used for each resolved provider.
    emb_model = s.embedding.ollama_model if ep == "ollama" else s.embedding.model
    vec_status = f"dir={s.vector.chroma_persist_dir}" if vb == "chroma" else f"url={s.vector.url}"
    if lp == "slm":
        llm_model = f"{s.llm.slm_filename} (gpu_layers={s.llm.slm_n_gpu_layers})"
    else:
        llm_model = s.llm.model  # factory's _model_for() maps this to provider-specific name
    rows = [
        ("embeddings", ep, "model=" + emb_model),
        ("vector_store", vb, vec_status),
        ("rerank", _rerank_provider(), "model=" + s.rerank.model),
        ("llm", lp, "model=" + llm_model),
        ("asr", resolved_asr(), "model=" + s.voice.asr_model),
        ("tts", resolved_tts(), "voice=" + s.voice.tts_voice),
        ("tracing", tracing, "host=" + s.telemetry.langfuse_host),
    ]
    return [{"subsystem": name, "provider": prov, "status": status} for name, prov, status in rows]


def _rerank_provider() -> str:
    import importlib.util

    s = get_settings()
    if s.rerank.provider != "auto":
        return s.rerank.provider
    if s.cohere_api_key and importlib.util.find_spec("cohere"):
        return "cohere"
    if importlib.util.find_spec("FlagEmbedding"):
        return "bge"
    return "lexical"


def health_snapshot() -> dict[str, Any]:
    s = get_settings()
    return {
        "status": "ok",
        "version": __import__("auralynq").__version__,
        "env": s.env,
        "providers": describe_providers(),
        "hf_token_present": bool(s.huggingface_token),
    }
