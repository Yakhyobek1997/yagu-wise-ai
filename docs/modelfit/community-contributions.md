# ModelFit Community Benchmark Contributions

## Overview

The Auralynq ModelFit Index accepts community-contributed benchmark results. These allow users to share real-world performance data from their hardware, building a corpus of reproducible local LLM measurements that is more useful than cloud benchmarks for local-first RAG deployment.

---

## How to Contribute

### Step 1: Run a benchmark

```bash
# Ensure you have an Ollama model installed locally (do NOT pull just for benchmarking):
ollama list

# Run a benchmark via the Auralynq CLI:
auralynq-modelfit benchmark \
  --model llama3.1:8b \
  --quantization q4_k \
  --task rag \
  --examples 20 \
  --output runs/modelfit/
```

Or via the API:
```
POST /api/modelfit/benchmark/preview   # review the plan first
POST /api/modelfit/benchmark/run       # run with confirmed=true
```

### Step 2: Export the result

The benchmark runner saves a JSON file to `runs/modelfit/<run_id>.json`. Review it before sharing.

### Step 3: Anonymize hardware metadata

Before contributing, ensure your hardware entry **does not contain**:
- Serial numbers
- MAC addresses
- UUIDs
- Hostnames
- Usernames or user directories

The validator will reject entries containing these fields.

### Step 4: Submit

Place your result file in `data/modelfit/community_results/` and open a pull request.

---

## Required Hardware Metadata

Every contributed result must include a `hardware` object with at minimum:

```json
{
  "cpu_model": "Intel Core i9-13900K",
  "ram_gb": 64,
  "gpus": [
    {
      "vendor": "nvidia",
      "name": "NVIDIA GeForce RTX 4090",
      "vram_gb": 24,
      "backend": "cuda"
    }
  ]
}
```

**Why required**: Hardware context is what makes a benchmark result meaningful. A tok/s number without hardware is worthless.

---

## Result Schema

```json
{
  "model_id": "ollama:llama3.1:8b",
  "quantization": "q4_k",
  "hardware": {
    "cpu_model": "...",
    "ram_gb": 32,
    "gpus": [...]
  },
  "benchmark_version": "auralynq-modelfit-0.1",
  "tok_per_sec": 28.4,
  "p50_latency_ms": 1200,
  "p95_latency_ms": 3600,
  "time_to_first_token_ms": 450,
  "peak_memory_gb": 5.2,
  "task": "rag",
  "notes": "Tested on Ubuntu 24.04, CUDA 12.4.",
  "date": "2026-06-23",
  "source": "auralynq-benchmark-runner",
  "verified_status": "self_reported"
}
```

---

## Verification Status

All contributed results are assigned a verification status:

| Status | Meaning |
|---|---|
| `self_reported` | User ran the benchmark themselves; not independently verified |
| `verified_local` | Result was reproduced by an Auralynq maintainer on equivalent hardware |
| `official_benchmark` | Result produced by the Auralynq CI benchmark suite |
| `unverified` | Data origin unclear; treat with caution |

Community contributions start as `self_reported`. They may be upgraded to `verified_local` by maintainers.

**Do not trust `self_reported` results as ground truth.** Use them as a guide.

---

## How to Avoid Fake Numbers

- Run the Auralynq benchmark runner — it produces `is_measured: true` results.
- Do not manually edit `avg_tok_per_sec` or `latency` fields.
- Do not extrapolate from different hardware ("my 3090 gets X, so the 4090 should get Y").
- Do not copy numbers from online posts without citing the source.
- Include the `benchmark_version` field from the runner output.

---

## Validation Rules

The validator rejects entries that:
- Are missing required fields (`model_id`, `quantization`, `hardware`, `benchmark_version`, `task`, `date`, `source`).
- Have `tok_per_sec > 10000` (implausible for local inference).
- Have `peak_memory_gb > 1000` (implausible).
- Contain negative values for any numeric metric.
- Contain sensitive hardware fields (`serial`, `uuid`, `mac_address`, `hostname`, `username`).

---

## How Results Are Used

Validated community results appear in:
- The ModelFit comparison table (labelled `self_reported`).
- The ModelFit score card's speed score when measured data is available.
- The benchmark lab's history view.

Unvalidated results are excluded until reviewed.
