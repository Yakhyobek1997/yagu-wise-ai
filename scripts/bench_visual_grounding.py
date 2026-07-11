"""Benchmark visual-grounding resolution rates over the golden set.

For each golden question, runs the real agent pipeline and resolves its
citations through GroundingResolver, then tabulates how many resolve to
`span` (exact bounding box) vs. `page` (page known, no box) vs. `unavailable`
(needs reindex). Writes reports/visual_grounding_report.json with the same
provenance block (git commit, timestamp, hardware) as eval/bench reports —
see auralynq/eval/provenance.py.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from auralynq.agent.runner import answer_question
from auralynq.config import get_settings
from auralynq.eval.datasets import load_golden
from auralynq.eval.provenance import report_provenance
from auralynq.eval.report import _ensure_index
from auralynq.grounding.resolver import GroundingResolver


def run(write_report: bool = True) -> dict[str, Any]:
    s = get_settings()
    s.ensure_dirs()
    _ensure_index()
    golden = load_golden()
    resolver = GroundingResolver()

    stage_counts: Counter[str] = Counter()
    n_citations = 0
    for item in golden:
        result = answer_question(item.question)
        if not result.citations:
            continue
        n_citations += len(result.citations)
        for g in resolver.resolve(
            answer_id=item.question, answer=result.answer, citations=result.citations
        ):
            stage_counts[g.grounding_stage] += 1

    total = sum(stage_counts.values())
    report: dict[str, Any] = {
        "version": 1,
        "n_golden": len(golden),
        "n_citations": n_citations,
        "n_grounding_groups": total,
        "stage_counts": dict(stage_counts),
        "stage_rate": ({k: round(v / total, 3) for k, v in stage_counts.items()} if total else {}),
        "note": (
            "stage_rate is the fraction of resolved (doc_id, page) citation "
            "groups in each grounding stage, not a quality score — span is "
            "only possible for documents with layout/bbox metadata (PDFs)."
        ),
        "provenance": report_provenance(dataset_version=f"golden_qa.json n={len(golden)}"),
    }
    if write_report:
        out = s.reports_dir / "visual_grounding_report.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
