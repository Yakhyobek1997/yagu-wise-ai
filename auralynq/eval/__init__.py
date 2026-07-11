"""Evaluation: retrieval metrics, Ragas, ASR WER, benchmarks, drift check."""

from __future__ import annotations

from auralynq.eval.bench import run_bench
from auralynq.eval.report import run_eval

__all__ = ["run_bench", "run_eval"]
