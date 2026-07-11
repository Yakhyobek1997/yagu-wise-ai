"""FastAPI router for Auralynq ModelFit Index endpoints.

All endpoints are read-only or require explicit user confirmation.
No models are downloaded automatically. No benchmarks run without confirmation.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from auralynq.modelfit.benchmark_runner import (
    get_run,
    list_runs,
    preview_benchmark,
    run_benchmark,
)
from auralynq.modelfit.community import (
    load_community_results,
    validate_community_result,
)
from auralynq.modelfit.hardware import probe_hardware
from auralynq.modelfit.model_registry import get_registry
from auralynq.modelfit.resource_estimator import estimate_resources, recommend_quantization
from auralynq.modelfit.scoring import score_model
from auralynq.telemetry import get_logger

_log = get_logger("auralynq.modelfit.router")

router = APIRouter(prefix="/api/modelfit", tags=["modelfit"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class EstimateRequest(BaseModel):
    model_id: str
    params_b: float = Field(..., gt=0, description="Parameter count in billions")
    quantization: str = "q4_k"
    context_tokens: int = Field(4096, ge=256, le=200000)


class ScoreRequest(BaseModel):
    model_id: str
    quantization: str | None = None
    requested_tasks: list[str] = Field(default_factory=list)
    context_tokens: int = 4096


class BenchmarkRunRequest(BaseModel):
    model_id: str
    quantization: str = "q4_k"
    task: str = "latency"
    num_examples: int = Field(10, ge=1, le=200)
    confirmed: bool = Field(
        False,
        description="Must be true to actually run. Use /preview first.",
    )


class DiscoverRequest(BaseModel):
    task: str | None = Field(None, description="Filter by task: rag, coding, chat, math, …")
    include_hf: bool = Field(True, description="Also query HuggingFace GGUF catalog")
    refresh: bool = Field(False, description="Bypass the 10-minute in-process cache")
    limit: int = Field(15, ge=1, le=50)


class PullRequest(BaseModel):
    model_id: str = Field(
        ...,
        description=(
            "ollama:<name>:<tag> to pull via Ollama, "
            "or hf:<repo_id>/<filename> to download from HF Hub"
        ),
    )
    confirmed: bool = Field(False, description="Must be true to execute the pull")


# ── Hardware ─────────────────────────────────────────────────────────────────


@router.get("/hardware")
async def get_hardware() -> dict[str, Any]:
    """Probe local hardware — CPU, RAM, GPU, VRAM, backend, Ollama, HF."""
    hw = probe_hardware()
    return hw.to_dict()


# ── Models ────────────────────────────────────────────────────────────────────


@router.get("/models")
async def list_models(
    source: str | None = Query(None, description="ollama|huggingface|local"),
    family: str | None = Query(None),
    task: str | None = Query(None),
    embedding_only: bool = Query(False),
    open_license: bool = Query(False),
    supports_adapters: bool | None = Query(None),
    q: str | None = Query(None, description="Free-text search"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """List models from static catalog. Optionally refreshed from live Ollama."""
    registry = get_registry()
    models = registry.search(
        query=q or "",
        source=source,
        family=family,
        task=task,
        embedding_only=embedding_only,
        open_license=open_license,
        supports_adapters=supports_adapters,
        limit=limit,
    )
    return {"models": registry.to_dict_list(models), "total": len(models)}


@router.get("/models/search")
async def search_models(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    refresh_ollama: bool = Query(False),
) -> dict[str, Any]:
    """Search models by name/family/task. Optionally sync live Ollama installs."""
    registry = get_registry()
    warnings: list[str] = []
    if refresh_ollama:
        warnings = await registry.refresh_from_ollama()
    models = registry.search(query=q, limit=limit)
    return {
        "models": registry.to_dict_list(models),
        "total": len(models),
        "warnings": warnings,
    }


@router.get("/models/installed")
async def list_installed() -> dict[str, Any]:
    """Sync and return locally installed Ollama models (read-only, no downloads)."""
    registry = get_registry()
    warnings = await registry.refresh_from_ollama()
    installed = registry.search(source="ollama", limit=100)
    return {
        "models": registry.to_dict_list(installed),
        "total": len(installed),
        "warnings": warnings,
    }


@router.get("/models/{model_id:path}")
async def get_model(model_id: str) -> dict[str, Any]:
    """Get metadata for a single model."""
    registry = get_registry()
    model = registry.get(model_id)
    if not model:
        raise HTTPException(404, f"Model '{model_id}' not found in registry.")
    return model.to_dict()


# ── Resource estimation ───────────────────────────────────────────────────────


@router.post("/estimate")
async def estimate(req: EstimateRequest) -> dict[str, Any]:
    """Estimate VRAM/RAM/disk for a model+quantization on current hardware."""
    hw = probe_hardware()
    result = estimate_resources(
        model_id=req.model_id,
        params_b=req.params_b,
        quantization=req.quantization,
        available_vram_gb=hw.total_vram_gb,
        available_ram_gb=hw.ram_gb,
        context_tokens=req.context_tokens,
    )
    return result.to_dict()


@router.post("/recommend-quantization")
async def recommend_quant(
    params_b: float = Query(..., gt=0),
    prefer_quality: bool = Query(False),
) -> dict[str, Any]:
    """Return best quantization for given param count on current hardware."""
    hw = probe_hardware()
    quant = recommend_quantization(
        params_b=params_b,
        available_vram_gb=hw.total_vram_gb,
        available_ram_gb=hw.ram_gb,
        prefer_quality=prefer_quality,
    )
    return {"recommended_quantization": quant, "is_estimate": True}


# ── ModelFit Score ────────────────────────────────────────────────────────────


@router.post("/score")
async def compute_score(req: ScoreRequest) -> dict[str, Any]:
    """Compute a ModelFit Score for a model on current hardware."""
    registry = get_registry()
    model = registry.get(req.model_id)
    if not model:
        raise HTTPException(404, f"Model '{req.model_id}' not found in registry.")
    hw = probe_hardware()
    fit = score_model(
        model=model,
        hw=hw,
        quantization=req.quantization,
        requested_tasks=req.requested_tasks,
        context_tokens=req.context_tokens,
    )
    return fit.to_dict()


@router.get("/recommendations")
async def get_recommendations(
    task: str | None = Query(None),
    limit: int = Query(5, ge=1, le=20),
) -> dict[str, Any]:
    """Return top model recommendations for current hardware."""
    hw = probe_hardware()
    registry = get_registry()

    # Score all non-embedding, non-reranker models
    candidates = [m for m in registry.list_all() if not m.embedding and not m.reranker]
    if task:
        candidates = [m for m in candidates if task in m.tasks or not m.tasks]

    scored = []
    for model in candidates:
        fit = score_model(model=model, hw=hw, requested_tasks=[task] if task else [])
        scored.append(fit)

    scored.sort(key=lambda s: s.overall_score, reverse=True)
    top = scored[:limit]

    return {
        "recommendations": [s.to_dict() for s in top],
        "hardware_summary": {
            "ram_gb": hw.ram_gb,
            "total_vram_gb": hw.total_vram_gb,
            "best_backend": hw.best_backend,
        },
        "task": task,
    }


# ── Benchmark ─────────────────────────────────────────────────────────────────


@router.post("/benchmark/preview")
async def benchmark_preview(req: BenchmarkRunRequest) -> dict[str, Any]:
    """Return a dry-run plan — no benchmark is executed."""
    plan = preview_benchmark(
        model_id=req.model_id,
        quantization=req.quantization,
        task=req.task,
        num_examples=req.num_examples,
    )
    return plan.to_dict()


@router.post("/benchmark/run")
async def benchmark_run(req: BenchmarkRunRequest) -> dict[str, Any]:
    """Run a benchmark against a locally available model.

    Requires confirmed=true. Never downloads models.
    """
    if not req.confirmed:
        raise HTTPException(
            400,
            "Set confirmed=true to run. Use /benchmark/preview to review the plan first.",
        )
    result = await run_benchmark(
        model_id=req.model_id,
        quantization=req.quantization,
        task=req.task,
        num_examples=req.num_examples,
    )
    return result.to_dict()


@router.get("/benchmark/runs")
async def get_runs() -> dict[str, Any]:
    """List all saved benchmark runs."""
    runs = list_runs()
    return {"runs": runs, "total": len(runs)}


@router.get("/benchmark/{run_id}")
async def get_benchmark_run(run_id: str) -> dict[str, Any]:
    """Get a specific benchmark run by ID."""
    result = get_run(run_id)
    if not result:
        raise HTTPException(404, f"Benchmark run '{run_id}' not found.")
    return result.to_dict()


# ── Community ─────────────────────────────────────────────────────────────────


@router.get("/community/results")
async def get_community_results(
    model_id: str | None = Query(None, description="Filter by model_id prefix"),
    verified_only: bool = Query(False, description="verified_local or official_benchmark only"),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """List community-contributed benchmark results.

    All results are clearly labelled with verified_status. Never auto-trusted.
    """
    results = load_community_results(verified_only=verified_only)
    if model_id:
        results = [r for r in results if r.model_id.startswith(model_id)]
    results = results[:limit]
    return {
        "results": [r.to_dict() for r in results],
        "total": len(results),
        "verified_only": verified_only,
        "disclaimer": (
            "Community results are self-reported and unverified unless "
            "verified_status is 'verified_local' or 'official_benchmark'."
        ),
    }


@router.post("/community/validate")
async def validate_community(data: dict[str, Any]) -> dict[str, Any]:
    """Validate a community result payload without saving it.

    Use this before submitting to catch schema errors.
    """
    errors = validate_community_result(data)
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "fields_checked": [
            "model_id",
            "quantization",
            "hardware",
            "benchmark_version",
            "task",
            "date",
            "source",
            "tok_per_sec",
            "peak_memory_gb",
        ],
    }


# ── Dynamic discovery ─────────────────────────────────────────────────────────


@router.post("/discover")
async def discover_models(req: DiscoverRequest) -> dict[str, Any]:
    """Probe hardware, query live Ollama registry + HuggingFace Hub, and rank.

    Returns models that actually fit the current hardware — including models
    not yet installed, with the exact pull command needed to acquire them.
    Results are cached for 10 minutes; pass refresh=true to bypass.
    """
    import asyncio

    from auralynq.modelfit.catalog_fetcher import (
        fetch_hf_gguf_catalog,
        fetch_ollama_catalog,
        invalidate_cache,
    )

    if req.refresh:
        invalidate_cache()

    hw = probe_hardware()
    vram_gb = hw.total_vram_gb or 0.0
    ram_gb = hw.ram_gb or 8.0

    coroutines = [fetch_ollama_catalog(vram_gb, ram_gb)]
    if req.include_hf:
        coroutines.append(fetch_hf_gguf_catalog(vram_gb))

    fetched = await asyncio.gather(*coroutines, return_exceptions=True)
    results = []
    for r in fetched:
        if isinstance(r, list):
            results.extend(r)
        elif isinstance(r, Exception):
            _log.warning("discover.catalog_error", error=str(r))

    # Filter embedding models unless task is "embedding"
    if req.task and req.task != "embedding":
        results = [m for m in results if not m.embedding]

    # Filter by task if specified
    if req.task:
        results = [m for m in results if req.task in (m.tasks or []) or not m.tasks]

    # Score each model against current hardware
    scored = []
    for model in results:
        fit = score_model(
            model=model,
            hw=hw,
            quantization=None,
            requested_tasks=[req.task] if req.task else [],
        )
        # Check if already installed in Ollama
        already_installed = model.ollama_tag is not None and any(
            n.startswith("Installed") for n in (model.notes or [])
        )
        pull_command: str | None = None
        if model.source == "ollama" and model.ollama_tag:
            pull_command = f"ollama pull {model.ollama_tag}"
        elif model.source == "huggingface" and model.hf_repo:
            pull_command = f"huggingface-cli download {model.hf_repo} --local-dir ./models"

        scored.append(
            {
                **fit.to_dict(),
                "model_meta": model.to_dict(),
                "already_installed": already_installed,
                "pull_command": pull_command,
                "source": model.source,
            }
        )

    scored.sort(key=lambda s: s["overall_score"], reverse=True)

    return {
        "hardware": {
            "os": hw.os_name,
            "cpu": hw.cpu_model,
            "cpu_cores_physical": hw.cpu_cores_physical,
            "cpu_cores_logical": hw.cpu_cores_logical,
            "arch": hw.cpu_arch,
            "avx2": hw.avx2,
            "avx512": hw.avx512,
            "ram_gb": hw.ram_gb,
            "total_vram_gb": hw.total_vram_gb,
            "total_vram_free_gb": hw.total_vram_free_gb,
            "gpus": [g.to_dict() for g in hw.gpus],
            "best_backend": hw.best_backend,
            "ollama_available": hw.ollama_available,
            "in_container": hw.in_container,
        },
        "task": req.task,
        "total_candidates": len(scored),
        "recommendations": scored[: req.limit],
        "note": (
            "Results from live Ollama registry + HuggingFace Hub. "
            "Models are ranked by hardware fit — not yet installed models include "
            "the exact pull_command to acquire them."
        ),
    }


@router.post("/pull")
async def pull_model(req: PullRequest) -> dict[str, Any]:
    """Pull a model from Ollama or download a GGUF from HuggingFace Hub.

    Requires confirmed=true. For Ollama models: runs `ollama pull <tag>`.
    For HF models: runs hf_hub_download into the local GGUF cache.
    """
    if not req.confirmed:
        raise HTTPException(
            400,
            "Set confirmed=true to execute the pull. "
            "Use POST /discover first to see what will be downloaded.",
        )

    model_id = req.model_id

    # Ollama pull: model_id starts with "ollama:"
    if model_id.startswith("ollama:"):
        tag = model_id.removeprefix("ollama:")
        from auralynq.modelfit.catalog_fetcher import pull_ollama_model

        _log.info("modelfit.pull.ollama", tag=tag)
        ok, msg = await pull_ollama_model(tag)
        if not ok:
            raise HTTPException(500, f"ollama pull failed: {msg}")
        return {"status": "pulled", "model_id": model_id, "message": msg}

    # HuggingFace GGUF download: model_id starts with "hf:"
    if model_id.startswith("hf:"):
        remainder = model_id.removeprefix("hf:")
        if "/" not in remainder:
            raise HTTPException(400, "HF model_id must be 'hf:<repo_id>/<filename>'")

        # Split: last segment is filename, rest is repo
        parts = remainder.rsplit("/", 1)
        if len(parts) != 2 or not parts[1].endswith(".gguf"):
            raise HTTPException(
                400,
                "HF model_id must be 'hf:<owner>/<repo>/<filename>.gguf' "
                "(last segment must be a .gguf filename)",
            )
        # Allow org/repo/filename or just owner+repo-as-path/filename
        # We need actual repo_id (owner/model) and filename separately
        # Convention: hf:owner/repo/file.gguf → repo_id=owner/repo, filename=file.gguf
        # But HF repos can have sub-paths; we take last token as filename
        filename = parts[1]
        repo_id_path = parts[0]  # may be "owner/repo" or more

        from auralynq.config.settings import get_settings
        from auralynq.modelfit.catalog_fetcher import pull_hf_gguf

        token = get_settings().huggingface_token or ""
        _log.info("modelfit.pull.hf", repo=repo_id_path, filename=filename)
        ok, result = pull_hf_gguf(repo_id_path, filename, token)
        if not ok:
            raise HTTPException(500, f"HF download failed: {result}")
        return {
            "status": "downloaded",
            "model_id": model_id,
            "local_path": result,
            "message": f"Downloaded to {result}",
        }

    raise HTTPException(
        400,
        f"Unrecognised model_id prefix in '{model_id}'. Must start with 'ollama:' or 'hf:'.",
    )
