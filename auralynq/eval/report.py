"""Evaluation harness + report generation (ADR-0010).

Compares retrieval quality across naive / hybrid / PathRAG / full-agentic, scores
answer quality (Ragas or proxy), measures ASR WER, runs a frozen-golden drift
check, and writes ``reports/eval_report.json``. Every README benchmark number
originates here — nothing is hand-written.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from auralynq.agent.runner import answer_question
from auralynq.config import get_settings
from auralynq.eval.asr_eval import evaluate_asr
from auralynq.eval.datasets import load_asr_refs, load_golden
from auralynq.eval.provenance import report_provenance
from auralynq.eval.ragas_eval import evaluate as ragas_evaluate
from auralynq.eval.retrieval_metrics import aggregate
from auralynq.llm.factory import resolved_provider as llm_provider
from auralynq.pipeline import build_index, load_graph
from auralynq.retrieval.hybrid.retriever import HybridRetriever
from auralynq.retrieval.naive import NaiveRetriever
from auralynq.retrieval.pathrag.retriever import PathRAGRetriever
from auralynq.telemetry import get_logger
from auralynq.vectorstore.factory import get_store

_log = get_logger("auralynq.eval")
DRIFT_TOLERANCE = 0.05


def _ensure_index() -> None:
    store = get_store()
    if store.count() > 0:
        return
    s = get_settings()
    corpus = s.data_dir / "corpus"
    if not corpus.exists() or not any(corpus.iterdir()):
        from scripts.download_data import download

        download(sample=True)
    build_index(corpus)


def _dedup_preserve_order(sources: list[str]) -> list[str]:
    """Collapse a chunk-level ranking to document granularity.

    Relevance judgements are per document, so a gold document split across
    several chunks must be credited once at its best (earliest) rank — otherwise
    nDCG/precision are inflated (nDCG can exceed 1). Keeps first occurrence.
    """
    seen: set[str] = set()
    out: list[str] = []
    for s in sources:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _ranked_sources(chunks) -> list[str]:
    return _dedup_preserve_order([Path(c.chunk.source).name or c.chunk.source for c in chunks])


def _retrieval_variants(golden, k: int) -> dict[str, Any]:
    store = get_store()
    naive = NaiveRetriever(store=store)
    hybrid = HybridRetriever(store=store)
    pathrag = PathRAGRetriever(load_graph(), store=store)
    variants = {"naive": naive, "hybrid": hybrid, "pathrag": pathrag}

    out: dict[str, Any] = {}
    for name, retriever in variants.items():
        cases, latencies = [], []
        for item in golden:
            res = retriever.retrieve(item.question, k)
            latencies.append(res.took_ms)
            cases.append((set(item.supporting), _ranked_sources(res.chunks)))
        scores = aggregate(cases, k=k)
        out[name] = {
            "recall_at_k": scores.recall_at_k,
            "precision_at_k": scores.precision_at_k,
            "ndcg_at_10": scores.ndcg_at_k,
            "mrr": scores.mrr,
            "latency_p50_ms": round(statistics.median(latencies), 2) if latencies else 0.0,
        }
    return out


def _agentic(golden, k: int) -> dict[str, Any]:
    cases, latencies, samples = [], [], []
    from auralynq.agent import runner

    runner._CACHE.clear()
    for item in golden:
        res = answer_question(item.question, final_k=k, use_cache=False)
        latencies.append(res.elapsed_ms)
        ranked = _dedup_preserve_order([Path(c.get("source", "")).name for c in res.citations])
        cases.append((set(item.supporting), ranked))
        samples.append(
            {
                "question": item.question,
                "answer": res.answer,
                "contexts": res.contexts or [item.answer],
                "ground_truth": item.answer,
            }
        )
    scores = aggregate(cases, k=k)
    ragas = ragas_evaluate(samples)
    return {
        "retrieval": {
            "recall_at_k": scores.recall_at_k,
            "ndcg_at_10": scores.ndcg_at_k,
            "mrr": scores.mrr,
            "precision_at_k": scores.precision_at_k,
            "latency_p50_ms": round(statistics.median(latencies), 2) if latencies else 0.0,
        },
        "ragas": {
            "faithfulness": ragas.faithfulness,
            "answer_relevancy": ragas.answer_relevancy,
            "context_precision": ragas.context_precision,
            "provider": ragas.provider,
        },
    }


def _asr() -> dict[str, Any]:
    refs = load_asr_refs()
    if not refs:
        return {"wer": None, "n": 0, "provider": "n/a", "note": "no asr refs"}
    from auralynq.voice.loop import transcribe

    s = get_settings()
    pairs, provider = [], "null"
    for ref in refs:
        audio = s.data_dir / "corpus" / ref.audio
        if not audio.exists():
            continue
        t = transcribe(audio)
        provider = t.provider
        pairs.append((ref.reference, t.text))
    scores = evaluate_asr(pairs, provider=provider)
    return {"wer": scores.wer, "n": scores.n, "provider": scores.provider}


def _drift_check(report: dict[str, Any]) -> dict[str, Any]:
    s = get_settings()
    baseline_path = s.reports_dir / "golden_baseline.json"
    current = {
        "agentic_recall": report["agentic"]["retrieval"]["recall_at_k"],
        "agentic_faithfulness": report["agentic"]["ragas"]["faithfulness"],
        "hybrid_ndcg": report["retrieval"]["hybrid"]["ndcg_at_10"],
    }
    if not baseline_path.exists():
        baseline_path.write_text(json.dumps(current, indent=2), encoding="utf-8")
        return {"status": "baseline_created", "baseline": current}
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    regressions = {
        k: {"baseline": baseline[k], "current": current[k]}
        for k in current
        if k in baseline and current[k] < baseline[k] - DRIFT_TOLERANCE
    }
    return {
        "status": "regressed" if regressions else "ok",
        "regressions": regressions,
        "current": current,
        "baseline": baseline,
    }


def run_eval(smoke: bool = False, write_report: bool = False) -> dict[str, Any]:
    s = get_settings()
    s.ensure_dirs()
    _ensure_index()
    golden = load_golden()
    if smoke:
        golden = golden[:3]
    k = s.retrieval.final_k

    report: dict[str, Any] = {
        "version": 1,
        "config": {
            "embedder": get_store().backend,
            "llm": llm_provider(),
            "k": k,
            "n_golden": len(golden),
            "smoke": smoke,
        },
        "retrieval": _retrieval_variants(golden, k),
        "agentic": _agentic(golden, k),
        "asr": _asr(),
    }
    report["drift"] = _drift_check(report)
    report["provenance"] = report_provenance(
        dataset_version=f"golden_qa.json n={len(golden)} (smoke={smoke})"
    )

    if write_report:
        out = s.reports_dir / "eval_report.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        _log.info("eval.report_written", path=str(out))
    return report
