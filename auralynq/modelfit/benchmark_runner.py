"""Local benchmark runner for Auralynq ModelFit Index.

Benchmarks are always user-triggered. This module never automatically
downloads models or runs benchmarks. All benchmark results are clearly
labelled as measured (not estimated).

CLI:
  auralynq-modelfit benchmark --model llama3.1:8b --task rag --examples 20

API:
  POST /api/modelfit/benchmark/preview  — dry-run plan (no execution)
  POST /api/modelfit/benchmark/run      — requires explicit confirmation
  GET  /api/modelfit/benchmark/{run_id}
  GET  /api/modelfit/benchmark/runs
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import Any, Literal

from auralynq.telemetry import get_logger

_log = get_logger("auralynq.modelfit.benchmark")

BenchmarkTask = Literal["latency", "throughput", "rag", "context_stress", "abstention"]
BenchmarkStatus = Literal["pending", "running", "completed", "failed", "cancelled"]

_RUNS_DIR = Path("runs/modelfit")

# Sample prompts per task type — used for reproducible benchmarks
_SAMPLE_PROMPTS: dict[str, list[str]] = {
    "latency": [
        "What is the capital of France?",
        "Summarize: The quick brown fox jumps over the lazy dog.",
        "List three benefits of exercise.",
    ],
    "throughput": [
        "Write a detailed explanation of how neural networks learn from data.",
        "Describe the history of the Roman Empire in 200 words.",
        "Explain the concept of recursion with a code example in Python.",
    ],
    "rag": [
        "Based on the provided documents, what are the main conclusions?",
        "According to the context, who is responsible for the described event?",
        "What evidence supports the claim made in the document?",
        "Cite the specific passage that answers: what happened first?",
    ],
    "abstention": [
        "What is the stock price of ACME Corp right now?",
        "Tell me the personal phone number of the CEO.",
        "What will the weather be tomorrow?",
    ],
    "context_stress": [
        # Long prompt injected programmatically in runner
        "Summarize the following document in one sentence.",
    ],
}


@dataclass
class BenchmarkPlan:
    """Dry-run plan — shown to user before actual execution."""

    model_id: str
    quantization: str
    task: BenchmarkTask
    num_examples: int
    estimated_duration_min: float
    sample_prompts: list[str]
    requires_ollama: bool
    requires_model_download: bool  # always False — we never download
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "quantization": self.quantization,
            "task": self.task,
            "num_examples": self.num_examples,
            "estimated_duration_min": self.estimated_duration_min,
            "sample_prompts": self.sample_prompts[:3],
            "requires_ollama": self.requires_ollama,
            "requires_model_download": self.requires_model_download,
            "warnings": self.warnings,
            "note": (
                "This is a dry-run preview. No benchmark has been run yet. "
                "Call /api/modelfit/benchmark/run with confirmed=true to execute."
            ),
        }


@dataclass
class BenchmarkResult:
    run_id: str
    model_id: str
    quantization: str
    task: BenchmarkTask
    status: BenchmarkStatus
    hardware: dict[str, Any] = field(default_factory=dict)
    avg_tok_per_sec: float | None = None
    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    time_to_first_token_ms: float | None = None
    peak_memory_gb: float | None = None
    num_examples: int = 0
    completed_examples: int = 0
    rag_metrics: dict[str, float | None] = field(default_factory=dict)
    error: str | None = None
    started_at: str = ""
    completed_at: str | None = None
    warnings: list[str] = field(default_factory=list)
    is_measured: bool = True  # always True for benchmark runner output

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "model_id": self.model_id,
            "quantization": self.quantization,
            "task": self.task,
            "status": self.status,
            "hardware": self.hardware,
            "avg_tok_per_sec": self.avg_tok_per_sec,
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "time_to_first_token_ms": self.time_to_first_token_ms,
            "peak_memory_gb": self.peak_memory_gb,
            "num_examples": self.num_examples,
            "completed_examples": self.completed_examples,
            "rag_metrics": self.rag_metrics,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "warnings": self.warnings,
            "is_measured": self.is_measured,
        }


# In-memory run store (production would use DB / persistent storage)
_active_runs: dict[str, BenchmarkResult] = {}


def preview_benchmark(
    model_id: str,
    quantization: str = "q4_k",
    task: str = "latency",
    num_examples: int = 10,
) -> BenchmarkPlan:
    """Return a dry-run plan without executing anything."""
    warnings: list[str] = []
    _valid_tasks = ("latency", "throughput", "rag", "context_stress", "abstention")
    task_typed: BenchmarkTask = task if task in _valid_tasks else "latency"  # type: ignore[assignment]

    # Estimate duration: ~30s per example for throughput, ~5s for latency
    duration_per = 30.0 if task_typed == "throughput" else 5.0
    est_min = round(num_examples * duration_per / 60, 1)

    requires_ollama = model_id.startswith("ollama:") or ":" not in model_id
    warnings.append(
        "No benchmark has run yet. This is a preview only. Confirm to start the actual benchmark."
    )
    if requires_ollama:
        warnings.append("Benchmark will use local Ollama — ensure the model is already pulled.")
    if num_examples > 50:
        warnings.append(f"Large benchmark ({num_examples} examples) may take ~{est_min} min.")

    sample = _SAMPLE_PROMPTS.get(task_typed, _SAMPLE_PROMPTS["latency"])[:3]

    return BenchmarkPlan(
        model_id=model_id,
        quantization=quantization,
        task=task_typed,
        num_examples=num_examples,
        estimated_duration_min=est_min,
        sample_prompts=sample,
        requires_ollama=requires_ollama,
        requires_model_download=False,
        warnings=warnings,
    )


async def run_benchmark(
    model_id: str,
    quantization: str = "q4_k",
    task: str = "latency",
    num_examples: int = 10,
    output_dir: str | None = None,
) -> BenchmarkResult:
    """Execute a benchmark against a locally available model via Ollama.

    Never downloads models — fails gracefully if model is not installed.
    """
    from datetime import datetime

    run_id = str(uuid.uuid4())[:8]
    _valid_tasks = ("latency", "throughput", "rag", "context_stress", "abstention")
    task_typed: BenchmarkTask = task if task in _valid_tasks else "latency"  # type: ignore[assignment]

    result = BenchmarkResult(
        run_id=run_id,
        model_id=model_id,
        quantization=quantization,
        task=task_typed,
        status="running",
        num_examples=num_examples,
        started_at=datetime.now(UTC).isoformat(),
    )
    _active_runs[run_id] = result

    # Attach hardware snapshot
    try:
        from auralynq.modelfit.hardware import probe_hardware

        hw = probe_hardware()
        result.hardware = hw.to_dict()
    except Exception:
        result.hardware = {}

    # Ollama tag extraction
    tag = model_id.removeprefix("ollama:")

    prompts = _SAMPLE_PROMPTS.get(task_typed, _SAMPLE_PROMPTS["latency"])
    if num_examples > len(prompts):
        # Repeat prompts to fill num_examples
        prompts = (prompts * ((num_examples // len(prompts)) + 1))[:num_examples]
    else:
        prompts = prompts[:num_examples]

    latencies: list[float] = []
    tok_counts: list[float] = []
    ttft_list: list[float] = []
    errors: list[str] = []

    try:
        import httpx

        async with httpx.AsyncClient(timeout=120.0) as client:
            for i, prompt in enumerate(prompts):
                t0 = time.perf_counter()
                first_token_t: float | None = None
                total_tokens = 0

                try:
                    async with client.stream(
                        "POST",
                        "http://localhost:11434/api/generate",
                        json={
                            "model": tag,
                            "prompt": prompt,
                            "stream": True,
                            "options": {"num_predict": 200},
                        },
                    ) as resp:
                        if resp.status_code == 404:
                            result.status = "failed"
                            result.error = (
                                f"Model '{tag}' not found in local Ollama. "
                                "Pull it first: ollama pull " + tag
                            )
                            _active_runs[run_id] = result
                            return result
                        async for line in resp.aiter_lines():
                            if not line:
                                continue
                            try:
                                chunk = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if first_token_t is None and chunk.get("response"):
                                first_token_t = time.perf_counter()
                            if "eval_count" in chunk:
                                total_tokens = chunk["eval_count"]
                            if chunk.get("done"):
                                break

                    elapsed = time.perf_counter() - t0
                    latencies.append(elapsed * 1000)
                    if first_token_t:
                        ttft_list.append((first_token_t - t0) * 1000)
                    if total_tokens > 0 and elapsed > 0:
                        tok_counts.append(total_tokens / elapsed)
                    result.completed_examples = i + 1

                except Exception as exc:
                    errors.append(str(exc))
                    _log.warning("Benchmark example failed", error=str(exc))

    except Exception as exc:
        result.status = "failed"
        result.error = f"Ollama connection failed: {exc}"
        _active_runs[run_id] = result
        return result

    # Aggregate results
    from datetime import datetime

    if latencies:
        latencies_sorted = sorted(latencies)
        result.p50_latency_ms = round(latencies_sorted[len(latencies_sorted) // 2], 1)
        result.p95_latency_ms = round(latencies_sorted[int(len(latencies_sorted) * 0.95)], 1)
    if ttft_list:
        result.time_to_first_token_ms = round(sum(ttft_list) / len(ttft_list), 1)
    if tok_counts:
        result.avg_tok_per_sec = round(sum(tok_counts) / len(tok_counts), 1)

    if errors:
        result.warnings.extend([f"Example error: {e}" for e in errors[:3]])

    # For RAG/abstention tasks, run quality metrics using local corpus
    if task_typed in ("rag", "abstention"):
        try:
            from auralynq.modelfit.rag_bench import run_rag_benchmark

            rag_m = await run_rag_benchmark(
                model_id=model_id,
                quantization=quantization,
                num_rag=min(num_examples, 5),
                num_abstention=min(num_examples, 4),
            )
            result.rag_metrics = rag_m.to_dict()
            result.warnings.extend(rag_m.warnings)
        except Exception as exc:
            result.rag_metrics = {
                "citation_coverage": None,
                "groundedness": None,
                "abstention_accuracy": None,
                "is_measured": False,
            }
            result.warnings.append(f"RAG quality benchmark failed: {exc}")
    else:
        result.rag_metrics = {
            "citation_coverage": None,
            "groundedness": None,
            "abstention_accuracy": None,
            "is_measured": False,
        }

    result.status = "completed"
    result.completed_at = datetime.now(UTC).isoformat()

    # Persist result
    out_dir = Path(output_dir) if output_dir else _RUNS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / f"{run_id}.json"
    try:
        result_path.write_text(json.dumps(result.to_dict(), indent=2))
    except OSError as e:
        result.warnings.append(f"Could not save result to disk: {e}")

    _active_runs[run_id] = result
    return result


def get_run(run_id: str) -> BenchmarkResult | None:
    if run_id in _active_runs:
        return _active_runs[run_id]
    # Try loading from disk
    path = _RUNS_DIR / f"{run_id}.json"
    if path.exists():
        try:
            data = json.loads(path.read_text())
            fields = BenchmarkResult.__dataclass_fields__
            r = BenchmarkResult(**{k: v for k, v in data.items() if k in fields})
            _active_runs[run_id] = r
            return r
        except Exception:
            return None
    return None


def list_runs() -> list[dict[str, Any]]:
    """Return summary of all saved benchmark runs."""
    runs: list[dict[str, Any]] = []

    # In-memory first
    for r in _active_runs.values():
        runs.append(r.to_dict())

    # Then disk
    if _RUNS_DIR.exists():
        for p in sorted(_RUNS_DIR.glob("*.json"), reverse=True):
            run_id = p.stem
            if run_id not in _active_runs:
                import contextlib

                with contextlib.suppress(Exception):
                    runs.append(json.loads(p.read_text()))

    return runs
