#!/usr/bin/env python
"""Multi-hop RAG eval on the HotpotQA-derived corpus (paper-scale, not smoke).

Indexes ``data/corpus_hf`` (40 HotpotQA passages) and evaluates every retrieval
variant + the full agentic pipeline over ``data/golden/golden_qa_hf.json``
(40 multi-hop questions). Reuses the frozen eval internals so the metrics are
computed identically to ``make eval`` — only the corpus and golden set change.

Writes ``reports/eval_hotpotqa_report.json`` with full provenance. Numbers are
real (Ollama LLM + bge/ollama embeddings) — nothing hand-written.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from auralynq.config import get_settings
from auralynq.eval.datasets import GoldenItem
from auralynq.eval.provenance import report_provenance
from auralynq.eval.report import _agentic, _retrieval_variants
from auralynq.pipeline import build_index
from auralynq.telemetry import get_logger

_log = get_logger("auralynq.bench_hotpotqa")


def _load_hf_golden() -> list[GoldenItem]:
    path = get_settings().data_dir / "golden" / "golden_qa_hf.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        GoldenItem(
            id=i["id"],
            question=i["question"],
            answer=str(i.get("answer", "")),
            supporting=i.get("supporting", []),
            type=i.get("type", "multi"),
        )
        for i in data.get("items", [])
    ]


def main(limit: int | None = None) -> None:
    s = get_settings()
    s.ensure_dirs()
    corpus = s.data_dir / "corpus_hf"
    _log.info("bench_hotpotqa.indexing", corpus=str(corpus))
    stats = build_index(corpus, rebuild=True)
    _log.info("bench_hotpotqa.indexed", **{k: stats[k] for k in ("chunks_indexed", "documents") if k in stats})

    golden = _load_hf_golden()
    if limit:
        golden = golden[:limit]
    k = s.retrieval.final_k

    _log.info("bench_hotpotqa.eval_start", n_golden=len(golden), k=k)
    retrieval = _retrieval_variants(golden, k)
    agentic = _agentic(golden, k)

    report = {
        "version": 1,
        "dataset": "HotpotQA (distractor) 40-passage subset — multi-hop QA",
        "config": {"k": k, "n_golden": len(golden)},
        "retrieval": retrieval,
        "agentic": agentic,
        "provenance": report_provenance(
            dataset_version=f"golden_qa_hf.json n={len(golden)} (corpus_hf)"
        ),
    }
    out = s.reports_dir / "eval_hotpotqa_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _log.info("bench_hotpotqa.report_written", path=str(out))
    print(f"\nWrote {out}")
    print(json.dumps({"retrieval": retrieval, "ragas": agentic.get("ragas")}, indent=2))


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="cap number of golden items")
    args = ap.parse_args()
    main(limit=args.limit)
