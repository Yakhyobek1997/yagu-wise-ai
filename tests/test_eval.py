from __future__ import annotations

import pytest
from auralynq.eval.asr_eval import evaluate_asr, word_error_rate
from auralynq.eval.bench import run_bench
from auralynq.eval.provenance import report_provenance
from auralynq.eval.ragas_eval import proxy_scores
from auralynq.eval.report import run_eval
from auralynq.eval.retrieval_metrics import aggregate, mrr, ndcg_at_k, recall_at_k

_PROVENANCE_KEYS = {"git_commit", "generated_at", "hardware", "dataset_version"}


def test_recall_and_mrr():
    rel = {"geography"}
    ranked = ["other.md", "geography.md", "x.md"]
    assert recall_at_k(rel, ranked, 3) == 1.0
    assert recall_at_k(rel, ranked, 1) == 0.0
    assert mrr(rel, ranked) == pytest.approx(0.5)


def test_ndcg_monotonic_in_position():
    rel = {"a"}
    top = ndcg_at_k(rel, ["a.md", "b.md"], 2)
    bottom = ndcg_at_k(rel, ["b.md", "a.md"], 2)
    assert top > bottom


def test_aggregate_shapes():
    cases = [({"geography"}, ["geography.md", "x.md"]), ({"pathrag"}, ["pathrag.md"])]
    s = aggregate(cases, k=2)
    assert s.n == 2 and 0 <= s.recall_at_k <= 1


def test_wer_exact_and_fallback():
    assert word_error_rate("the cat sat", "the cat sat") == 0.0
    assert word_error_rate("the cat sat", "the dog sat") == pytest.approx(1 / 3, abs=1e-3)
    s = evaluate_asr([("paris is the capital", "paris is the capital")])
    assert s.wer == 0.0


def test_ragas_proxy_bounds():
    samples = [
        {
            "question": "what is the capital of france",
            "answer": "paris is the capital of france",
            "contexts": ["paris is the capital of france"],
        }
    ]
    sc = proxy_scores(samples)
    assert 0 <= sc.faithfulness <= 1
    assert sc.faithfulness > 0.5
    assert sc.provider == "proxy"


def test_run_eval_smoke_writes_report(corpus_dir, monkeypatch):
    # point data_dir corpus at our fixture corpus
    from auralynq.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "data_dir", corpus_dir.parent)
    (corpus_dir.parent / "corpus").exists() or corpus_dir.rename(corpus_dir.parent / "corpus")
    report = run_eval(smoke=True, write_report=True)
    assert "retrieval" in report
    assert {"naive", "hybrid", "pathrag"} <= set(report["retrieval"])
    assert "agentic" in report and "ragas" in report["agentic"]
    assert report["drift"]["status"] in ("baseline_created", "ok", "regressed")
    assert (s.reports_dir / "eval_report.json").exists()
    # every report must be traceable: git commit, timestamp, hardware, dataset
    assert set(report["provenance"]) >= _PROVENANCE_KEYS
    assert "smoke=True" in report["provenance"]["dataset_version"]


def test_run_bench(corpus_dir, monkeypatch):
    from auralynq.config import get_settings

    s = get_settings()
    report = run_bench(k=5, n_queries=8, write_report=True)
    assert set(report["quantization"]) == {"none", "scalar", "binary"}
    assert report["quantization"]["none"]["recall_at_k"] == 1.0
    assert 0 <= report["quantization"]["binary"]["recall_at_k"] <= 1
    # scalar (int8) should retain more recall than binary (1-bit)
    assert (
        report["quantization"]["scalar"]["recall_at_k"]
        >= report["quantization"]["binary"]["recall_at_k"]
    )
    assert (s.reports_dir / "bench_report.json").exists()
    assert set(report["provenance"]) >= _PROVENANCE_KEYS


def test_report_provenance_schema():
    p = report_provenance(dataset_version="unit-test-dataset")
    assert set(p) >= _PROVENANCE_KEYS
    assert p["dataset_version"] == "unit-test-dataset"
    assert isinstance(p["hardware"], dict)
    # git_commit degrades to "unknown" outside a repo, but must never raise
    assert isinstance(p["git_commit"], str) and p["git_commit"]
