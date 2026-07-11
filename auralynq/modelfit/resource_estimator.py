"""VRAM/RAM and quantization resource estimator for Auralynq ModelFit Index.

These are ESTIMATES based on published memory formulas and community observations.
They are labelled as estimates throughout. Measured benchmark results always
override estimates when available.

Formula basis:
  VRAM ~ (params_b x bytes_per_param) + kv_cache_overhead + framework_overhead
  bytes_per_param: fp16=2, bf16=2, int8=1, q8≈1, q6≈0.75, q5≈0.625,
                   q4≈0.5, q3≈0.375, q2≈0.25
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

FitLevel = Literal["comfortable", "tight", "not_recommended", "impossible"]

# Verdict is the plain-language, UI-facing summary of the estimate. Unlike
# ``fit_level`` (kept for backward compatibility) it distinguishes GPU-resident
# from CPU-offloaded execution - matching how Ollama/llama.cpp actually behave
# when a model is slightly larger than VRAM (they split layers to system RAM
# and run slower rather than failing).
Verdict = Literal[
    "runs_great",  # fits in VRAM with comfortable headroom (≤80%)
    "runs_ok",  # fits in VRAM but tight (80-100%)
    "runs_offload",  # exceeds VRAM; spills layers to system RAM (works, slower)
    "runs_cpu",  # CPU-only machine, model fits comfortably in system RAM
    "runs_cpu_tight",  # CPU-only, fits but with little RAM headroom
    "too_big",  # cannot fit in VRAM + RAM at all
]

# bytes per parameter per quantization level
_BYTES_PER_PARAM: dict[str, float] = {
    "fp32": 4.0,
    "fp16": 2.0,
    "bf16": 2.0,
    "int8": 1.0,
    "q8": 1.0,
    "q6_k": 0.75,
    "q5_k": 0.625,
    "q5_1": 0.6875,
    "q4_k": 0.5,
    "q4_0": 0.5,
    "q3_k": 0.375,
    "q2_k": 0.25,
}

# Framework + activation + runtime overhead in GB. Research consensus (LM Studio,
# Ollama tuning guides, 2026) is that the runtime reserves ~1-1.5 GB beyond model
# weights for CUDA/Metal context, compute graph, and default KV allocation.
_FRAMEWORK_OVERHEAD_GB = 1.0

# KV cache per 1K context tokens per 1B params, held in fp16 (Ollama's default -
# KV precision is independent of weight quantization). Calibrated against modern
# GQA architectures: Llama-3-8B ≈ 0.5 GB at 4K, ≈1.1 GB at 8K; a 3B ≈ 0.2 GB at
# 4K. The KV cache - not weights - is what grows with context and causes OOM on
# long documents, so this is estimated explicitly.
_KV_CACHE_GB_PER_1K_TOKENS_PER_1B = 0.017

# Aim to keep steady-state VRAM use at ≤80% of capacity so there is headroom for
# the KV cache to grow and for the OS/display. Above this a model still runs but
# is "tight". (LM Studio's green/yellow guidance uses the same ~80% target.)
_VRAM_HEADROOM_TARGET = 0.80

# When a model exceeds VRAM, Ollama/llama.cpp offload the overflow to system RAM
# at a large speed penalty. We consider offload viable while the total still fits
# within VRAM plus this fraction of system RAM (leaving RAM for the OS).
_RAM_OFFLOAD_FRACTION = 0.80


def _kv_cache_gb(params_b: float, context_tokens: int, quantization: str) -> float:
    """Estimate KV cache size (fp16) for a given context length.

    KV precision is independent of weight quantization; Ollama keeps the cache in
    fp16 by default, so ``quantization`` is accepted for API stability but does
    not shrink the cache here.
    """
    del quantization  # KV cache precision is independent of weight quantization
    return params_b * (context_tokens / 1000) * _KV_CACHE_GB_PER_1K_TOKENS_PER_1B


def estimate_vram_gb(params_b: float, quantization: str, context_tokens: int = 4096) -> float:
    bpp = _BYTES_PER_PARAM.get(quantization, 0.5)
    model_gb = params_b * 1e9 * bpp / (1024**3)
    kv = _kv_cache_gb(params_b, context_tokens, quantization)
    return round(model_gb + kv + _FRAMEWORK_OVERHEAD_GB, 2)


def estimate_ram_gb(vram_estimate: float, has_gpu: bool) -> float:
    """Estimate host RAM needed (system RAM, not VRAM)."""
    if has_gpu:
        # With GPU: minimal host RAM needed beyond OS + process overhead
        return round(max(4.0, vram_estimate * 0.25 + 2.0), 1)
    else:
        # CPU inference: model must live in RAM
        return round(vram_estimate + 2.0, 1)


@dataclass
class ResourceEstimate:
    model_id: str
    quantization: str
    context_tokens: int
    estimated_vram_gb: float
    estimated_ram_gb: float
    estimated_disk_gb: float
    fit_level: FitLevel
    fits: bool
    recommended_context: int
    peak_vram_at_max_ctx_gb: float
    # UI-facing verdict + the signals behind it (see Verdict docstring above).
    verdict: Verdict = "runs_cpu"
    fits_in_vram: bool = False
    requires_cpu_offload: bool = False
    headroom_gb: float = 0.0  # free VRAM (GPU) or free RAM (CPU) after loading
    vram_free_gb: float | None = None  # live free VRAM used for the "fits now" check
    warnings: list[str] = field(default_factory=list)
    is_estimate: bool = True  # always True - only benchmarks produce measured values

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "quantization": self.quantization,
            "context_tokens": self.context_tokens,
            "estimated_vram_gb": self.estimated_vram_gb,
            "estimated_ram_gb": self.estimated_ram_gb,
            "estimated_disk_gb": self.estimated_disk_gb,
            "fit_level": self.fit_level,
            "fits": self.fits,
            "recommended_context": self.recommended_context,
            "peak_vram_at_max_ctx_gb": self.peak_vram_at_max_ctx_gb,
            "verdict": self.verdict,
            "fits_in_vram": self.fits_in_vram,
            "requires_cpu_offload": self.requires_cpu_offload,
            "headroom_gb": self.headroom_gb,
            "vram_free_gb": self.vram_free_gb,
            "warnings": self.warnings,
            "is_estimate": self.is_estimate,
        }


def estimate_disk_gb(params_b: float, quantization: str) -> float:
    bpp = _BYTES_PER_PARAM.get(quantization, 0.5)
    # GGUF files add ~5% overhead for metadata/tokenizer
    return round(params_b * 1e9 * bpp / (1024**3) * 1.05, 2)


@dataclass
class _Assessment:
    fit_level: FitLevel
    fits: bool
    verdict: Verdict
    fits_in_vram: bool
    requires_cpu_offload: bool
    headroom_gb: float


def _assess_fit(
    vram_needed: float,
    vram_available: float,
    ram_available: float,
    has_gpu: bool,
) -> _Assessment:
    """Classify how a model of ``vram_needed`` GB fits the given hardware.

    Mirrors real runtime behaviour: on a GPU the model is fast while it lives in
    VRAM, tolerable when tight, and - crucially - still *runnable* (just slow)
    when it overflows into system RAM via layer offload. CPU-only machines run
    everything from system RAM.
    """
    if not has_gpu or vram_available <= 0:
        # CPU-only: weights live in system RAM.
        headroom = round(ram_available - vram_needed, 1)
        ratio = vram_needed / ram_available if ram_available > 0 else 99.0
        if ratio <= 0.60:
            return _Assessment("comfortable", True, "runs_cpu", False, False, headroom)
        if ratio <= 0.90:
            return _Assessment("tight", True, "runs_cpu_tight", False, False, headroom)
        if ratio <= 1.0:
            return _Assessment("not_recommended", False, "runs_cpu_tight", False, False, headroom)
        return _Assessment("impossible", False, "too_big", False, False, headroom)

    # GPU present.
    headroom = round(vram_available - vram_needed, 1)
    ratio = vram_needed / vram_available
    if ratio <= _VRAM_HEADROOM_TARGET:
        return _Assessment("comfortable", True, "runs_great", True, False, headroom)
    if ratio <= 1.0:
        return _Assessment("tight", True, "runs_ok", True, False, headroom)
    # Exceeds VRAM - can the overflow spill to system RAM (Ollama splits layers)?
    if vram_needed <= vram_available + ram_available * _RAM_OFFLOAD_FRACTION:
        return _Assessment("not_recommended", True, "runs_offload", False, True, headroom)
    return _Assessment("impossible", False, "too_big", False, True, headroom)


def _recommend_context(params_b: float, quantization: str, vram_gb: float) -> int:
    """Suggest a safe context length that keeps KV cache within VRAM budget."""
    bpp = _BYTES_PER_PARAM.get(quantization, 0.5)
    model_gb = params_b * 1e9 * bpp / (1024**3)
    headroom = max(0.0, vram_gb - model_gb - _FRAMEWORK_OVERHEAD_GB)
    if headroom <= 0:
        return 512
    # Estimate max context from headroom
    per_1k = _kv_cache_gb(params_b, 1000, quantization)
    max_k = headroom / per_1k if per_1k > 0 else 128
    max_tokens = int(max_k * 1000)
    # Round down to common power-of-2 context lengths
    for ctx in [131072, 65536, 32768, 16384, 8192, 4096, 2048, 1024, 512]:
        if max_tokens >= ctx:
            return ctx
    return 512


def estimate_resources(
    model_id: str,
    params_b: float,
    quantization: str,
    available_vram_gb: float,
    available_ram_gb: float,
    context_tokens: int = 4096,
    available_vram_free_gb: float | None = None,
) -> ResourceEstimate:
    """Compute resource estimate for a model+quantization on given hardware.

    ``available_vram_free_gb`` (from ``nvidia-smi memory.free``, when known) is
    used for the live "will it fit right now" headroom while the total VRAM is
    used for the overall capability verdict.
    """
    quant = quantization.lower()
    if quant not in _BYTES_PER_PARAM:
        quant = "q4_k"

    has_gpu = available_vram_gb > 0
    vram_needed = estimate_vram_gb(params_b, quant, context_tokens)
    ram_needed = estimate_ram_gb(vram_needed, has_gpu)
    disk_needed = estimate_disk_gb(params_b, quant)

    assessment = _assess_fit(vram_needed, available_vram_gb, available_ram_gb, has_gpu)

    effective_vram = available_vram_gb if has_gpu else available_ram_gb
    rec_ctx = _recommend_context(params_b, quant, effective_vram)
    peak_vram = estimate_vram_gb(params_b, quant, 131072)

    warnings: list[str] = []
    warnings.append("Memory figures are estimates - actual usage varies by model implementation.")
    if assessment.verdict == "runs_offload":
        gpu_gb = min(vram_needed, available_vram_gb)
        warnings.append(
            f"Needs ~{vram_needed:.1f} GB but only {available_vram_gb:.1f} GB VRAM - "
            f"~{gpu_gb:.1f} GB on GPU, the rest offloaded to system RAM (much slower). "
            "A lower quantization or smaller model would run fully on the GPU."
        )
    elif not assessment.fits:
        avail = available_vram_gb if has_gpu else available_ram_gb
        unit = "VRAM" if has_gpu else "RAM"
        warnings.append(
            f"Model does not fit: needs ~{vram_needed:.1f} GB, "
            f"available ~{avail:.1f} GB {unit}. Try a lower quantization or smaller model."
        )
    if context_tokens > rec_ctx:
        warnings.append(
            f"Context {context_tokens} may cause OOM. Recommended max: {rec_ctx} tokens."
        )
    if peak_vram > effective_vram * 1.5:
        warnings.append("Maximum context (128K+) would greatly exceed VRAM. Use shorter context.")

    # Live headroom against *free* VRAM (if reported) beats the nominal total,
    # because other processes may already be holding some of the card.
    live_headroom = assessment.headroom_gb
    if has_gpu and available_vram_free_gb is not None:
        live_headroom = round(available_vram_free_gb - vram_needed, 1)
        if assessment.fits_in_vram and available_vram_free_gb < vram_needed:
            warnings.append(
                f"Only {available_vram_free_gb:.1f} GB VRAM is free right now "
                f"(needs ~{vram_needed:.1f} GB) - free some GPU memory before loading."
            )

    return ResourceEstimate(
        model_id=model_id,
        quantization=quant,
        context_tokens=context_tokens,
        estimated_vram_gb=vram_needed,
        estimated_ram_gb=ram_needed,
        estimated_disk_gb=disk_needed,
        fit_level=assessment.fit_level,
        fits=assessment.fits,
        recommended_context=rec_ctx,
        peak_vram_at_max_ctx_gb=round(peak_vram, 2),
        verdict=assessment.verdict,
        fits_in_vram=assessment.fits_in_vram,
        requires_cpu_offload=assessment.requires_cpu_offload,
        headroom_gb=live_headroom,
        vram_free_gb=available_vram_free_gb,
        warnings=warnings,
    )


def recommend_quantization(
    params_b: float,
    available_vram_gb: float,
    available_ram_gb: float,
    prefer_quality: bool = False,
) -> str:
    """Return the best quantization level that fits the available hardware."""
    # Try from highest quality to lowest
    candidates = (
        ["fp16", "q8", "q6_k", "q5_k", "q4_k", "q3_k", "q2_k"]
        if prefer_quality
        else ["q4_k", "q5_k", "q8", "q6_k", "q3_k", "q2_k"]
    )

    has_gpu = available_vram_gb > 0
    for quant in candidates:
        vram_needed = estimate_vram_gb(params_b, quant, 4096)
        assessment = _assess_fit(vram_needed, available_vram_gb, available_ram_gb, has_gpu)
        # Prefer a quant that lives fully in VRAM (GPU) or fits RAM comfortably (CPU).
        if assessment.fits_in_vram or (not has_gpu and assessment.fits):
            return quant

    return "q2_k"  # last resort
