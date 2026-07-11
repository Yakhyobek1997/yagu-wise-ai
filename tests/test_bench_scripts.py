"""Schema + offline-safety tests for the make bench-* report generators.

Every test here runs under the autouse `_isolated_env` fixture (conftest.py):
hash embeddings, in-memory vector store, extractive LLM, temp data/reports
dirs — i.e. exactly the offline fallback configuration a fresh clone with no
keys/extras gets. If any of these commands needed a real provider or network
access, they'd fail here.
"""

from __future__ import annotations

from scripts.bench_modelfit import run as run_bench_modelfit
from scripts.bench_visual_grounding import run as run_bench_visual_grounding
from scripts.export_paper_tables import run as run_export_paper_tables

_PROVENANCE_KEYS = {"git_commit", "generated_at", "hardware", "dataset_version"}


def _wire_corpus(corpus_dir, monkeypatch):
    from auralynq.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "data_dir", corpus_dir.parent)
    (corpus_dir.parent / "corpus").exists() or corpus_dir.rename(corpus_dir.parent / "corpus")
    return s


def test_bench_modelfit_schema():
    report = run_bench_modelfit(task="rag", limit=3, write_report=True)
    assert report["version"] == 1
    assert report["task"] == "rag"
    assert isinstance(report["hardware"], dict)
    assert 0 < len(report["rankings"]) <= 3
    for r in report["rankings"]:
        assert {"model_id", "overall_score", "label", "best_quantization"} <= set(r)
    assert set(report["provenance"]) >= _PROVENANCE_KEYS


def test_bench_visual_grounding_schema(corpus_dir, monkeypatch):
    s = _wire_corpus(corpus_dir, monkeypatch)
    report = run_bench_visual_grounding(write_report=True)
    assert report["version"] == 1
    assert report["n_golden"] > 0
    assert isinstance(report["stage_counts"], dict)
    # every stage_rate value should be a valid fraction
    assert all(0 <= v <= 1 for v in report["stage_rate"].values())
    assert set(report["provenance"]) >= _PROVENANCE_KEYS
    assert (s.reports_dir / "visual_grounding_report.json").exists()


def test_export_paper_tables_notes_missing_reports():
    # Nothing written yet in this fresh temp reports dir -> every report is "missing".
    doc = run_export_paper_tables(write_report=True)
    assert "Not yet generated" in doc
    assert "eval_report.json" in doc


def test_export_paper_tables_includes_provenance_when_present(corpus_dir, monkeypatch):
    from auralynq.eval.bench import run_bench

    _wire_corpus(corpus_dir, monkeypatch)
    run_bench(k=5, n_queries=8, write_report=True)
    doc = run_export_paper_tables(write_report=True)
    assert "Vector Index Quantization" in doc
    assert "generated" in doc  # provenance line rendered, not a stale/hand-written table
