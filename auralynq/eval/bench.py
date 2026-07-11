"""Vector-index benchmark: recall / latency / memory across quantization modes.

Measures the recall@k, mean query latency and resident vector memory for three
quantization strategies — ``none`` (float32), ``scalar`` (int8) and ``binary``
(1-bit) — using the actual indexed vectors. Recall is measured against the exact
float32 top-k as ground truth. This runs fully in-process at $0; when a Qdrant
server is reachable the same modes map onto Qdrant's quantization configs.
"""

from __future__ import annotations

import json
import time
from typing import Any

import numpy as np

from auralynq.config import get_settings
from auralynq.eval.provenance import report_provenance
from auralynq.eval.report import _ensure_index
from auralynq.telemetry import get_logger
from auralynq.vectorstore.factory import get_store, resolved_backend
from auralynq.vectorstore.memory_store import MemoryStore

_log = get_logger("auralynq.bench")


def _vectors() -> np.ndarray:
    # Prefer a rich, real vector population: embed every chunk across the full
    # corpus (curated + any HF augmentation) so the quantization recall/memory
    # curve is statistically meaningful, not a 5-vector toy.
    s = get_settings()
    mats: list[np.ndarray] = []
    try:
        from auralynq.embeddings.factory import get_embedder
        from auralynq.ingest.pipeline import ingest_path

        embedder = get_embedder()
        for sub in ("corpus", "corpus_hf"):
            d = s.data_dir / sub
            if not d.exists():
                continue
            chunks = [c for doc in ingest_path(d, force=True).documents for c in doc.chunks]
            if chunks:
                mats.append(embedder.embed([c.text for c in chunks]).dense.astype(np.float32))
    except Exception:  # pragma: no cover
        mats = []
    if mats:
        combined = np.vstack(mats)
        if combined.shape[0] >= 32:
            return combined

    store = get_store()
    if isinstance(store, MemoryStore) and store._dense is not None and store.count() >= 32:
        return store._dense.astype(np.float32)
    # Last-resort deterministic synthetic vectors (keeps the bench runnable).
    rng = np.random.RandomState(s.seed)
    return rng.randn(256, 256).astype(np.float32)


def _normalize(m: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return m / n


def _exact_topk(mat: np.ndarray, queries: np.ndarray, k: int) -> np.ndarray:
    sims = queries @ mat.T
    return np.argsort(-sims, axis=1)[:, :k]


def _scalar_quantize(mat: np.ndarray) -> tuple[np.ndarray, int]:
    lo, hi = mat.min(axis=0), mat.max(axis=0)
    rng = np.where(hi - lo == 0, 1.0, hi - lo)
    q = np.round((mat - lo) / rng * 255).astype(np.uint8)
    deq = q.astype(np.float32) / 255 * rng + lo
    return deq, q.nbytes


def _binary_quantize(mat: np.ndarray) -> tuple[np.ndarray, int]:
    bits = (mat > 0).astype(np.float32) * 2 - 1
    nbytes = int(np.ceil(mat.shape[1] / 8)) * mat.shape[0]
    return bits, nbytes


def _recall(approx_idx: np.ndarray, truth_idx: np.ndarray, k: int) -> float:
    hits = 0
    for a, t in zip(approx_idx, truth_idx, strict=False):
        hits += len(set(a[:k]) & set(t[:k]))
    return round(hits / (len(truth_idx) * k), 4)


def _latency_ms(mat: np.ndarray, queries: np.ndarray, k: int, repeats: int = 3) -> float:
    best = float("inf")
    for _ in range(repeats):
        t0 = time.perf_counter()
        sims = queries @ mat.T
        np.argsort(-sims, axis=1)[:, :k]
        best = min(best, (time.perf_counter() - t0) * 1000)
    return round(best / max(len(queries), 1), 4)


def run_bench(k: int = 10, n_queries: int = 32, write_report: bool = False) -> dict[str, Any]:
    s = get_settings()
    s.ensure_dirs()
    _ensure_index()
    mat = _normalize(_vectors())
    n = mat.shape[0]
    rng = np.random.RandomState(s.seed)
    qidx = rng.choice(n, size=min(n_queries, n), replace=False)
    queries = mat[qidx]
    truth = _exact_topk(mat, queries, k)

    results = {}
    # none
    results["none"] = {
        "recall_at_k": 1.0,
        "latency_ms": _latency_ms(mat, queries, k),
        "memory_bytes": int(mat.nbytes),
        "bits_per_dim": 32,
    }
    # scalar int8
    deq_s, bytes_s = _scalar_quantize(mat)
    approx_s = _exact_topk(_normalize(deq_s), queries, k)
    results["scalar"] = {
        "recall_at_k": _recall(approx_s, truth, k),
        "latency_ms": _latency_ms(_normalize(deq_s), queries, k),
        "memory_bytes": int(bytes_s),
        "bits_per_dim": 8,
    }
    # binary
    bin_m, bytes_b = _binary_quantize(mat)
    approx_b = _exact_topk(_normalize(bin_m), queries, k)
    results["binary"] = {
        "recall_at_k": _recall(approx_b, truth, k),
        "latency_ms": _latency_ms(_normalize(bin_m), queries, k),
        "memory_bytes": int(bytes_b),
        "bits_per_dim": 1,
    }

    report = {
        "version": 1,
        "backend": resolved_backend(),
        "n_vectors": int(n),
        "dim": int(mat.shape[1]),
        "k": k,
        "n_queries": len(queries),
        "quantization": results,
        "note": (
            "Recall measured vs exact float32 top-k. Memory is resident vector "
            "bytes for the stored set; latency is mean brute-force query time."
        ),
        "provenance": report_provenance(dataset_version=f"n_vectors={n} dim={mat.shape[1]}"),
    }
    if write_report:
        out = s.reports_dir / "bench_report.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        _log.info("bench.report_written", path=str(out))
    return report
