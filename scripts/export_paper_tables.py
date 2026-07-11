"""Render reports/*.json into Markdown tables for paper/README inclusion.

Reads whatever reports already exist under reports/ (produced by `make eval`,
`make bench`, `make bench-rag`, `make bench-modelfit`,
`make bench-visual-grounding`) and writes reports/paper_tables.md. Never
invents a table for a report that doesn't exist — missing reports are noted,
not backfilled with placeholder numbers.
"""

from __future__ import annotations

import json

from auralynq.config import get_settings


def _provenance_line(report: dict) -> str:
    p = report.get("provenance") or {}
    commit = p.get("git_commit", "unknown")[:12]
    ts = p.get("generated_at", "unknown")
    dataset = p.get("dataset_version", "unknown")
    return f"*commit `{commit}` · generated {ts} · dataset: {dataset}*"


def _eval_table(report: dict) -> str:
    lines = [
        "### Retrieval comparison\n",
        "| Metric | " + " | ".join(report["retrieval"].keys()) + " |",
    ]
    lines.append("|---|" + "---|" * len(report["retrieval"]))
    metrics = ["recall_at_k", "ndcg_at_10", "mrr", "precision_at_k", "latency_p50_ms"]
    for m in metrics:
        row = [str(report["retrieval"][variant].get(m, "—")) for variant in report["retrieval"]]
        lines.append(f"| {m} | " + " | ".join(row) + " |")
    lines.append("")
    lines.append(_provenance_line(report))
    return "\n".join(lines)


def _hotpotqa_table(report: dict) -> str:
    variants = report["retrieval"]
    lines = [
        "### Retrieval comparison — multi-hop HotpotQA\n",
        "| Metric | " + " | ".join(variants.keys()) + " |",
        "|---|" + "---|" * len(variants),
    ]
    for m in ["recall_at_k", "ndcg_at_10", "mrr", "precision_at_k", "latency_p50_ms"]:
        row = [str(variants[v].get(m, "—")) for v in variants]
        lines.append(f"| {m} | " + " | ".join(row) + " |")
    ragas = (report.get("agentic") or {}).get("ragas") or {}
    if ragas:
        lines.append("")
        lines.append("### Answer quality — full agentic pipeline (RAGAS proxy)\n")
        lines.append("| Faithfulness | Answer relevancy | Context precision |")
        lines.append("|---:|---:|---:|")
        lines.append(
            f"| {ragas.get('faithfulness', '—')} | {ragas.get('answer_relevancy', '—')} "
            f"| {ragas.get('context_precision', '—')} |"
        )
    lines.append("")
    lines.append(_provenance_line(report))
    return "\n".join(lines)


def _bench_table(report: dict) -> str:
    lines = [
        "### Qdrant quantization trade-off\n",
        "| Quantization | Recall@k | Memory (bytes) | Latency (ms) |",
        "|---|---:|---:|---:|",
    ]
    for name, q in report["quantization"].items():
        lines.append(f"| {name} | {q['recall_at_k']} | {q['memory_bytes']} | {q['latency_ms']} |")
    lines.append("")
    lines.append(_provenance_line(report))
    return "\n".join(lines)


def _modelfit_table(report: dict) -> str:
    lines = [
        f"### ModelFit rankings (task={report.get('task') or 'any'})\n",
        "| Model | Score | Label | Quant | Estimate? |",
        "|---|---:|---|---|---|",
    ]
    for r in report["rankings"]:
        lines.append(
            f"| {r['model_id']} | {r['overall_score']} | {r['label']} | "
            f"{r['best_quantization']} | {'yes' if r['estimate_used'] else 'no'} |"
        )
    lines.append("")
    lines.append(_provenance_line(report))
    return "\n".join(lines)


def _visual_grounding_table(report: dict) -> str:
    lines = ["### Visual grounding stage rates\n", "| Stage | Count | Rate |", "|---|---:|---:|"]
    for stage, count in report["stage_counts"].items():
        lines.append(f"| {stage} | {count} | {report['stage_rate'].get(stage, 0)} |")
    lines.append("")
    lines.append(_provenance_line(report))
    return "\n".join(lines)


def _rag_bench_table(report: dict) -> str:
    m = report["metrics"]
    lines = [
        "### RAG-quality benchmark\n",
        "| Model | Groundedness | Citation coverage | Abstention accuracy |",
        "|---|---:|---:|---:|",
        f"| {report['model_id']} | {m.get('groundedness', '—')} | "
        f"{m.get('citation_coverage', '—')} | {m.get('abstention_accuracy', '—')} |",
    ]
    if m.get("warnings"):
        lines.append("")
        lines.append(f"Warnings: {'; '.join(m['warnings'])}")
    return "\n".join(lines)


_TABLE_BUILDERS = {
    "eval_report.json": ("Retrieval & Answer Quality (`make eval`)", _eval_table),
    "eval_hotpotqa_report.json": (
        "Multi-Hop QA (`python scripts/bench_hotpotqa.py`)",
        _hotpotqa_table,
    ),
    "bench_report.json": ("Vector Index Quantization (`make bench`)", _bench_table),
    "modelfit_bench_report.json": ("ModelFit Index (`make bench-modelfit`)", _modelfit_table),
    "visual_grounding_report.json": (
        "Visual Grounding (`make bench-visual-grounding`)",
        _visual_grounding_table,
    ),
    "rag_bench_report.json": ("RAG Quality (`make bench-rag`)", _rag_bench_table),
}


def run(write_report: bool = True) -> str:
    s = get_settings()
    s.ensure_dirs()
    sections = [
        "# Auralynq Benchmark Tables\n",
        "Generated from `reports/*.json` — see each section's provenance line "
        "for the exact commit, timestamp, and dataset that produced it. "
        "Nothing below is hand-written.\n",
    ]
    missing: list[str] = []
    for filename, (title, builder) in _TABLE_BUILDERS.items():
        path = s.reports_dir / filename
        if not path.exists():
            missing.append(filename)
            continue
        report = json.loads(path.read_text(encoding="utf-8"))
        sections.append(f"## {title}\n\n{builder(report)}\n")
    if missing:
        sections.append(
            "## Not yet generated\n\n"
            + "\n".join(f"- `{m}` — run the matching `make` target to produce it." for m in missing)
        )
    doc = "\n".join(sections)
    if write_report:
        out = s.reports_dir / "paper_tables.md"
        out.write_text(doc, encoding="utf-8")
    return doc


if __name__ == "__main__":
    print(run())
