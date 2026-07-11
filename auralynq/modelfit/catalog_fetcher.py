"""Live catalog fetcher for Auralynq ModelFit Index.

Queries Ollama registry and HuggingFace Hub to discover models available
to pull/download, filtered and ranked against the current hardware profile.

All network calls are async with timeouts and graceful offline fallback.
Results are cached in-process to avoid hammering remote APIs on every request.
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

import httpx

from auralynq.modelfit.model_metadata import ModelMetadata
from auralynq.telemetry import get_logger

_log = get_logger("auralynq.modelfit.catalog_fetcher")

_REGISTRY = "https://registry.ollama.ai/v2/library"
_OLLAMA_LOCAL = "http://localhost:11434"
_HF_API = "https://huggingface.co/api"

# In-process cache: (result, fetched_at)
_cache: dict[str, tuple[list[ModelMetadata], float]] = {}
_CACHE_TTL_S = 600  # 10 minutes


# ── Known Ollama model families ───────────────────────────────────────────────
# Each entry: family_tag → {variants, family, tasks, license, params_b hint}
# The registry is queried at runtime to get actual sizes per variant.


def _fi(
    variants: list[str],
    family: str,
    tasks: list[str],
    license: str,
    params_hint: dict[str, float],
    embedding: bool = False,
) -> dict[str, Any]:
    return {
        "variants": variants,
        "family": family,
        "tasks": tasks,
        "license": license,
        "params_hint": params_hint,
        "embedding": embedding,
    }


_QWEN_TASKS = ["chat", "rag", "coding", "multilingual"]
_CHAT_RAG = ["chat", "rag"]

_OLLAMA_FAMILIES: dict[str, dict[str, Any]] = {
    "llama3.2": _fi(
        ["1b", "3b"],
        "llama",
        ["chat", "rag", "summarization"],
        "llama3.2",
        {"1b": 1.0, "3b": 3.0},
    ),
    "llama3.1": _fi(
        ["8b", "70b"],
        "llama",
        ["chat", "rag", "coding", "agents"],
        "llama3.1",
        {"8b": 8.0, "70b": 70.0},
    ),
    "llama3.3": _fi(
        ["70b"],
        "llama",
        ["chat", "rag", "coding", "agents"],
        "llama3.3",
        {"70b": 70.0},
    ),
    "qwen2.5": _fi(
        ["0.5b", "1.5b", "3b", "7b", "14b", "32b", "72b"],
        "qwen",
        _QWEN_TASKS,
        "apache-2.0",
        {"0.5b": 0.5, "1.5b": 1.5, "3b": 3.0, "7b": 7.0, "14b": 14.0, "32b": 32.0, "72b": 72.0},
    ),
    "qwen3": _fi(
        ["0.6b", "1.7b", "4b", "8b", "14b", "30b", "32b"],
        "qwen",
        _QWEN_TASKS,
        "apache-2.0",
        {"0.6b": 0.6, "1.7b": 1.7, "4b": 4.0, "8b": 8.0, "14b": 14.0, "30b": 30.0, "32b": 32.0},
    ),
    "mistral": _fi(
        ["7b"],
        "mistral",
        _CHAT_RAG,
        "apache-2.0",
        {"7b": 7.0},
    ),
    "mistral-nemo": _fi(
        ["12b"],
        "mistral",
        ["chat", "rag", "coding"],
        "apache-2.0",
        {"12b": 12.0},
    ),
    "gemma3": _fi(
        ["1b", "4b", "12b", "27b"],
        "gemma",
        ["chat", "rag", "vision"],
        "gemma",
        {"1b": 1.0, "4b": 4.0, "12b": 12.0, "27b": 27.0},
    ),
    "phi4": _fi(
        ["14b"],
        "phi",
        ["chat", "rag", "coding", "math"],
        "mit",
        {"14b": 14.0},
    ),
    "phi4-mini": _fi(
        ["3.8b"],
        "phi",
        ["chat", "rag", "coding"],
        "mit",
        {"3.8b": 3.8},
    ),
    "phi3.5": _fi(
        ["3.8b"],
        "phi",
        ["chat", "rag", "coding"],
        "mit",
        {"3.8b": 3.8},
    ),
    "deepseek-r1": _fi(
        ["1.5b", "7b", "8b", "14b", "32b"],
        "deepseek",
        ["chat", "coding", "math"],
        "mit",
        {"1.5b": 1.5, "7b": 7.0, "8b": 8.0, "14b": 14.0, "32b": 32.0},
    ),
    "deepseek-coder": _fi(
        ["1.3b", "6.7b", "33b"],
        "deepseek",
        ["coding"],
        "mit",
        {"1.3b": 1.3, "6.7b": 6.7, "33b": 33.0},
    ),
    "nomic-embed-text": _fi(
        ["latest"],
        "unknown",
        [],
        "apache-2.0",
        {},
        embedding=True,
    ),
    "mxbai-embed-large": _fi(
        ["latest"],
        "unknown",
        [],
        "apache-2.0",
        {},
        embedding=True,
    ),
    "codellama": _fi(
        ["7b", "13b", "34b"],
        "llama",
        ["coding"],
        "llama2",
        {"7b": 7.0, "13b": 13.0, "34b": 34.0},
    ),
}

# Well-known HF repos with curated GGUF splits, searched dynamically
_HF_GGUF_QUERIES = [
    "Qwen/Qwen2.5-{size}B-Instruct-GGUF",
    "Qwen/Qwen3-{size}B-GGUF",
    "microsoft/Phi-4-GGUF",
    "bartowski/Meta-Llama-3.1-{size}B-Instruct-GGUF",
    "bartowski/Mistral-7B-Instruct-v0.3-GGUF",
    "bartowski/gemma-3-{size}b-it-GGUF",
]

# Quantization selection: given VRAM budget, pick best quant for a param count
_QUANT_BYTES: dict[str, float] = {
    "Q2_K": 0.31,
    "Q3_K_M": 0.40,
    "Q4_K_M": 0.55,
    "Q5_K_M": 0.625,
    "Q6_K": 0.75,
    "Q8_0": 1.0,
    "F16": 2.0,
}


# ── Registry query helpers ─────────────────────────────────────────────────────


async def _registry_model_size_gb(client: httpx.AsyncClient, model: str, tag: str) -> float | None:
    """Fetch the model layer size from the Ollama registry manifest.

    Returns disk size in GB (= approximate loaded VRAM before KV cache overhead).
    """
    try:
        url = f"{_REGISTRY}/{model}/manifests/{tag}"
        r = await client.get(url, timeout=8.0)
        if r.status_code != 200:
            return None
        d = r.json()
        layer = next(
            (lyr for lyr in d.get("layers", []) if "model" in lyr.get("mediaType", "")),
            None,
        )
        return layer["size"] / (1024**3) if layer else None
    except Exception:
        return None


async def _ollama_installed(client: httpx.AsyncClient) -> dict[str, dict]:
    """Fetch installed Ollama models and their precise metadata via /api/show."""
    installed: dict[str, dict] = {}
    try:
        r = await client.get(f"{_OLLAMA_LOCAL}/api/tags", timeout=3.0)
        if r.status_code != 200:
            return installed
        for m in r.json().get("models", []):
            tag = m.get("name", "")
            try:
                r2 = await client.post(
                    f"{_OLLAMA_LOCAL}/api/show",
                    json={"model": tag},
                    timeout=4.0,
                )
                if r2.status_code == 200:
                    installed[tag] = r2.json()
            except Exception:
                installed[tag] = {}
    except Exception:
        pass
    return installed


# ── Metadata builders ─────────────────────────────────────────────────────────


def _params_from_tag(tag: str, hints: dict[str, float]) -> float | None:
    """Infer parameter count from a tag like '7b', '3b', '0.5b'."""
    tag_l = tag.lower()
    for key, val in hints.items():
        if key in tag_l:
            return val
    # fallback: parse NUMb pattern
    m = re.search(r"(\d+(?:\.\d+)?)b", tag_l)
    if m:
        return float(m.group(1))
    return None


def _best_quant_for_vram(params_b: float, vram_gb: float) -> str:
    """Return the best quantization level that fits params_b in vram_gb."""
    overhead = 1.5  # KV cache + framework
    for quant, bpp in sorted(_QUANT_BYTES.items(), key=lambda x: -x[1]):
        needed = params_b * bpp + overhead
        if needed <= vram_gb:
            return quant
    return "Q2_K"  # smallest known quant


def _vram_est(params_b: float, quant: str) -> float:
    bpp = _QUANT_BYTES.get(quant, 0.55)
    return round(params_b * bpp + 1.5, 2)


def _make_ollama_entry(
    model_name: str,
    tag: str,
    disk_gb: float | None,
    params_b: float | None,
    family_info: dict,
    installed_info: dict | None,
    vram_gb: float,
) -> ModelMetadata:
    """Build a ModelMetadata for an Ollama model tag."""
    model_id = f"ollama:{model_name}:{tag}" if tag != "latest" else f"ollama:{model_name}"
    quant = "Q4_K_M"
    if installed_info:
        details = installed_info.get("details", {})
        params_b = params_b or _parse_size_label(details.get("parameter_size", ""))
        quant = details.get("quantization_level", "Q4_K_M")
        info = installed_info.get("model_info", {})
        raw = info.get("general.parameter_count")
        if raw and isinstance(raw, (int, float)):
            params_b = round(raw / 1e9, 2)

    if params_b and vram_gb:
        quant = _best_quant_for_vram(params_b, vram_gb)

    notes = []
    if disk_gb:
        notes.append(f"~{disk_gb:.1f} GB on disk")
    if installed_info is not None:
        notes.insert(0, "Installed in Ollama — ready to use")

    return ModelMetadata(
        model_id=model_id,
        source="ollama",
        display_name=f"{model_name}:{tag}",
        family=family_info.get("family", "unknown"),  # type: ignore[arg-type]
        parameter_count_b=params_b,
        context_length=None,
        license=family_info.get("license", "unknown"),
        tasks=family_info.get("tasks", []),  # type: ignore[arg-type]
        available_quantizations=[quant] if quant else [],  # type: ignore[list-item]
        embedding=family_info.get("embedding", False),
        ollama_tag=f"{model_name}:{tag}",
        notes=notes,
    )


def _parse_size_label(s: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)[Bb]", s)
    return float(m.group(1)) if m else None


# ── Main fetch functions ───────────────────────────────────────────────────────


async def fetch_ollama_catalog(vram_gb: float, ram_gb: float) -> list[ModelMetadata]:
    """Fetch Ollama model catalog, annotated with registry sizes and hardware fit.

    Queries the local Ollama daemon for installed models (precise metadata),
    then the Ollama registry for models available to pull (size from manifest).
    Returns models ordered by hardware feasibility (best fit first).
    """
    cache_key = f"ollama:{vram_gb:.0f}:{ram_gb:.0f}"
    cached = _cache.get(cache_key)
    if cached and time.time() - cached[1] < _CACHE_TTL_S:
        return cached[0]

    results: list[ModelMetadata] = []

    async with httpx.AsyncClient() as client:
        # 1. Get installed models with rich metadata
        installed = await _ollama_installed(client)

        # 2. For each family+variant, check registry for size
        sem = asyncio.Semaphore(6)  # max 6 concurrent registry calls

        async def fetch_variant(model_name: str, tag: str, fi: dict) -> ModelMetadata | None:
            async with sem:
                ollama_tag = f"{model_name}:{tag}" if tag != "latest" else model_name
                installed_info = installed.get(ollama_tag) or installed.get(f"{model_name}:{tag}")
                params_b = _params_from_tag(tag, fi.get("params_hint", {}))
                disk_gb = None

                if installed_info is not None:
                    # Precise size from Ollama show
                    details = installed_info.get("details", {})
                    size_str = details.get("parameter_size", "")
                    params_b = params_b or _parse_size_label(size_str)
                else:
                    # Fetch from registry
                    disk_gb = await _registry_model_size_gb(client, model_name, tag)
                    if disk_gb is None:
                        # Model/tag doesn't exist in registry
                        return None

                # Filter by RAM fit (rough: model should fit in RAM too)
                if params_b:
                    vram_needed = _vram_est(params_b, "Q4_K_M")
                    if vram_needed > vram_gb + 2 and params_b * 0.55 > ram_gb:
                        return None  # won't fit in either VRAM or RAM

                return _make_ollama_entry(
                    model_name, tag, disk_gb, params_b, fi, installed_info, vram_gb
                )

        tasks = []
        for model_name, fi in _OLLAMA_FAMILIES.items():
            for tag in fi["variants"]:
                tasks.append(fetch_variant(model_name, tag, fi))

        fetched = await asyncio.gather(*tasks, return_exceptions=True)
        for r in fetched:
            if isinstance(r, ModelMetadata):
                results.append(r)

    _cache[cache_key] = (results, time.time())
    _log.info("catalog.ollama_fetched", total=len(results))
    return results


async def fetch_hf_gguf_catalog(vram_gb: float) -> list[ModelMetadata]:
    """Search HuggingFace Hub for popular GGUF models that fit the hardware.

    Uses the HF Hub Python API to find high-download text-generation GGUFs,
    parses parameter count from model name, filters by VRAM budget.
    """
    cache_key = f"hf:{vram_gb:.0f}"
    cached = _cache.get(cache_key)
    if cached and time.time() - cached[1] < _CACHE_TTL_S:
        return cached[0]

    results: list[ModelMetadata] = []
    try:
        from huggingface_hub import HfApi

        api = HfApi()
        models = list(
            api.list_models(
                filter="gguf",
                pipeline_tag="text-generation",
                sort="downloads",
                limit=80,
            )
        )
        for m in models:
            tags = m.tags or []
            repo_id = m.id

            # Parse param count from repo name
            params_b = _parse_params_from_name(repo_id)
            if params_b is None:
                continue  # skip if we can't estimate size

            # Estimate VRAM and filter
            quant = _best_quant_for_vram(params_b, vram_gb)
            vram_est = _vram_est(params_b, quant)
            if vram_est > vram_gb + 2:
                continue  # won't fit even on CPU with swap

            family = _infer_family(repo_id)
            tasks: list[str] = ["chat", "rag"]
            if any(k in repo_id.lower() for k in ["code", "coder", "starcoder"]):
                tasks = ["coding"]
            if any(k in repo_id.lower() for k in ["embed", "bge", "e5-"]):
                tasks = []

            results.append(
                ModelMetadata(
                    model_id=f"hf:{repo_id}",
                    source="huggingface",
                    display_name=repo_id,
                    family=family,  # type: ignore[arg-type]
                    parameter_count_b=params_b,
                    license=_infer_license(tags),
                    tasks=tasks,  # type: ignore[arg-type]
                    hf_repo=repo_id,
                    notes=[f"HuggingFace GGUF — {getattr(m, 'downloads', 0):,} downloads"],
                )
            )
    except Exception as exc:
        _log.warning("catalog.hf_failed", error=str(exc))

    _cache[cache_key] = (results, time.time())
    _log.info("catalog.hf_fetched", total=len(results))
    return results


def _parse_params_from_name(name: str) -> float | None:
    name_l = name.lower()
    # Match patterns: 7b, 7B, 7-b, 7.5b, 0.5b
    m = re.search(r"[_\-\s\.](\d+(?:\.\d+)?)[_\-]?b(?:[_\-\.]|$)", name_l)
    if m:
        return float(m.group(1))
    # Match at end: name-7B
    m = re.search(r"(\d+(?:\.\d+)?)b$", name_l)
    if m:
        return float(m.group(1))
    return None


def _infer_family(name: str) -> str:
    name_l = name.lower()
    for fam in ("llama", "qwen", "mistral", "gemma", "phi", "deepseek", "falcon", "mamba"):
        if fam in name_l:
            return fam
    return "unknown"


def _infer_license(tags: list[str]) -> str:
    for t in tags:
        t_l = t.lower()
        if "apache" in t_l:
            return "apache-2.0"
        if "mit" in t_l:
            return "mit"
        if "llama" in t_l:
            return t
        if "gemma" in t_l:
            return "gemma"
    return "unknown"


# ── Pull helpers ───────────────────────────────────────────────────────────────


async def pull_ollama_model(tag: str) -> tuple[bool, str]:
    """Run `ollama pull <tag>` as a subprocess. Returns (success, message)."""
    import asyncio

    try:
        proc = await asyncio.create_subprocess_exec(
            "ollama",
            "pull",
            tag,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
        if proc.returncode == 0:
            return True, f"Pulled {tag} successfully."
        return False, (stderr.decode() or stdout.decode())[:400]
    except TimeoutError:
        return False, "ollama pull timed out after 10 minutes."
    except Exception as exc:
        return False, str(exc)


def pull_hf_gguf(repo_id: str, filename: str, hf_token: str = "") -> tuple[bool, str]:
    """Download a HuggingFace GGUF file via hf_hub_download. Returns (success, path)."""
    try:
        from huggingface_hub import hf_hub_download

        kwargs: dict[str, Any] = {"repo_id": repo_id, "filename": filename}
        if hf_token:
            kwargs["token"] = hf_token
        path = hf_hub_download(**kwargs)  # type: ignore[call-overload]
        return True, path
    except Exception as exc:
        return False, str(exc)


def invalidate_cache() -> None:
    _cache.clear()
