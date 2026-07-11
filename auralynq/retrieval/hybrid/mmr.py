"""Maximal Marginal Relevance (Carbonell & Goldstein, 1998) de-duplication."""

from __future__ import annotations

from collections import OrderedDict

import numpy as np

from auralynq.embeddings.base import Embedder
from auralynq.retrieval.models import ScoredChunk

# Bounded per-text embedding cache: candidate chunks recur across queries, so we
# embed each distinct text at most once instead of re-embedding the whole pool
# on every MMR call. Keyed by (model, text) to stay correct across embedders.
_EMB_CACHE: OrderedDict[tuple[str, str], np.ndarray] = OrderedDict()
_EMB_CACHE_MAX = 4096


def _embed_cached(embedder: Embedder, texts: list[str]) -> np.ndarray:
    model = str(getattr(embedder, "model", embedder.__class__.__name__))
    out: list[np.ndarray | None] = [None] * len(texts)
    miss_idx: list[int] = []
    miss_txt: list[str] = []
    for i, t in enumerate(texts):
        key = (model, t)
        vec = _EMB_CACHE.get(key)
        if vec is None:
            miss_idx.append(i)
            miss_txt.append(t)
        else:
            _EMB_CACHE.move_to_end(key)
            out[i] = vec
    if miss_txt:
        fresh = np.asarray(embedder.embed(miss_txt).dense, dtype=np.float32)
        for j, i in enumerate(miss_idx):
            vec = np.ascontiguousarray(fresh[j], dtype=np.float32)
            out[i] = vec
            _EMB_CACHE[(model, miss_txt[j])] = vec
            if len(_EMB_CACHE) > _EMB_CACHE_MAX:
                _EMB_CACHE.popitem(last=False)
    return np.vstack([v for v in out if v is not None])


def mmr_rerank(
    query_dense: np.ndarray,
    candidates: list[ScoredChunk],
    embedder: Embedder,
    k: int,
    lambda_mult: float = 0.6,
) -> list[ScoredChunk]:
    """Select k chunks balancing relevance to the query and novelty vs. selected.

    Vectorized: embeddings are L2-normalized once, relevance is a single matvec
    and pairwise redundancy is read from one precomputed cosine matrix, replacing
    the original per-pair norm recomputation.
    """
    if not candidates:
        return []
    k = min(k, len(candidates))

    doc = _embed_cached(embedder, [c.chunk.text for c in candidates])
    doc /= np.linalg.norm(doc, axis=1, keepdims=True) + 1e-12
    q = np.asarray(query_dense, dtype=np.float32)
    q = q / (np.linalg.norm(q) + 1e-12)

    rel = doc @ q  # cosine to query, shape (n,)
    sim = doc @ doc.T  # pairwise cosine, shape (n, n)

    selected: list[int] = []
    remaining = list(range(len(candidates)))
    while remaining and len(selected) < k:
        if not selected:
            best_i = max(remaining, key=lambda i: float(rel[i]))
        else:
            sel = np.asarray(selected)
            best_i, best_score = remaining[0], -1e9
            for i in remaining:
                redundancy = float(sim[i, sel].max())
                score = lambda_mult * float(rel[i]) - (1 - lambda_mult) * redundancy
                if score > best_score:
                    best_score, best_i = score, i
        selected.append(best_i)
        remaining.remove(best_i)

    return [candidates[idx].model_copy(update={"rank": rank}) for rank, idx in enumerate(selected)]
