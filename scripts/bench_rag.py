"""Run the RAG-quality benchmark (groundedness, citation coverage, abstention
accuracy) against a local Ollama model, writing reports/rag_bench_report.json
with provenance.

Requires Ollama running locally with the target model pulled — if it isn't
reachable, this still completes and writes a report noting the benchmark was
skipped (never fabricates numbers, never fails the offline smoke path).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from auralynq.config import get_settings
from auralynq.eval.provenance import report_provenance
from auralynq.modelfit.rag_bench import run_rag_benchmark


def run(
    model_id: str,
    quantization: str = "q4_k",
    num_rag: int = 5,
    num_abstention: int = 4,
    write_report: bool = True,
) -> dict[str, Any]:
    s = get_settings()
    s.ensure_dirs()
    metrics = asyncio.run(run_rag_benchmark(model_id, quantization, num_rag, num_abstention))
    report: dict[str, Any] = {
        "version": 1,
        "model_id": model_id,
        "quantization": quantization,
        "metrics": metrics.to_dict(),
        "provenance": report_provenance(
            dataset_version=f"rag_prompts={num_rag} abstention_prompts={num_abstention}"
        ),
    }
    if write_report:
        out = s.reports_dir / "rag_bench_report.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="ollama:llama3.2:3b", dest="model_id")
    parser.add_argument("--quantization", default="q4_k")
    parser.add_argument("--num-rag", type=int, default=5)
    parser.add_argument("--num-abstention", type=int, default=4)
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.model_id, args.quantization, args.num_rag, args.num_abstention), indent=2
        )
    )
