"""Snapshot ModelFit Index scores for the current hardware.

Non-interactive and offline-safe: scores every catalog model against a real
hardware probe (no Ollama server or model downloads required — scores are
estimates unless a prior `auralynq-modelfit benchmark` run already recorded
measured tok/s for a model). Writes reports/modelfit_bench_report.json with
provenance. This is a read-only snapshot of `auralynq-modelfit recommend`'s
underlying scoring, not a new benchmark methodology.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from auralynq.config import get_settings
from auralynq.eval.provenance import report_provenance
from auralynq.modelfit.hardware import probe_hardware
from auralynq.modelfit.model_registry import get_registry
from auralynq.modelfit.scoring import score_model


def run(task: str | None = None, limit: int = 10, write_report: bool = True) -> dict[str, Any]:
    s = get_settings()
    s.ensure_dirs()
    hw = probe_hardware()
    registry = get_registry()
    candidates = [m for m in registry.list_all() if not m.embedding and not m.reranker]
    if task:
        candidates = [m for m in candidates if task in m.tasks or not m.tasks]

    scored = sorted(
        (score_model(m, hw, requested_tasks=[task] if task else []) for m in candidates),
        key=lambda sc: sc.overall_score,
        reverse=True,
    )[:limit]

    report: dict[str, Any] = {
        "version": 1,
        "task": task,
        "hardware": hw.to_dict(),
        "rankings": [sc.to_dict() for sc in scored],
        "provenance": report_provenance(dataset_version=f"model_registry n={len(candidates)}"),
    }
    if write_report:
        out = s.reports_dir / "modelfit_bench_report.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default=None, help="e.g. rag, coding, summarization")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(run(task=args.task, limit=args.limit), indent=2))
