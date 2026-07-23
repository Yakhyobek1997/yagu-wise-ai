"""Retrieval metrics: recall@k, precision@k, nDCG@k, MRR.

Binary relevance based on whether a retrieved document's source matches a golden
``supporting`` document (substring match against the source path/name).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class RetrievalScores:
    recall_at_k: float
    precision_at_k: float
    ndcg_at_k: float
    mrr: float
    n: int
    k: int


def _rels(relevant: set[str], ranked_sources: list[str]) -> list[int]:
    out = []
    for src in ranked_sources:
        hit = any(r and r in src for r in relevant)
        out.append(1 if hit else 0)
    return out


def recall_at_k(relevant: set[str], ranked: list[str], k: int) -> float:
    if not relevant:
        return 0.0
    rels = _rels(relevant, ranked[:k])
    return min(sum(rels), len(relevant)) / len(relevant)


def precision_at_k(relevant: set[str], ranked: list[str], k: int) -> float:
    if k == 0:
        return 0.0
    return sum(_rels(relevant, ranked[:k])) / k


def ndcg_at_k(relevant: set[str], ranked: list[str], k: int) -> float:
    rels = _rels(relevant, ranked[:k])
    dcg = sum(r / math.log2(i + 2) for i, r in enumerate(rels))
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    return dcg / ideal if ideal else 0.0


def mrr(relevant: set[str], ranked: list[str]) -> float:
    for i, src in enumerate(ranked):
        if any(r and r in src for r in relevant):
            return 1.0 / (i + 1)
    return 0.0


def aggregate(cases: list[tuple[set[str], list[str]]], k: int = 10) -> RetrievalScores:
    if not cases:
        return RetrievalScores(0, 0, 0, 0, 0, k)
    n = len(cases)
    return RetrievalScores(
        recall_at_k=round(sum(recall_at_k(r, ranked, k) for r, ranked in cases) / n, 4),
        precision_at_k=round(sum(precision_at_k(r, ranked, k) for r, ranked in cases) / n, 4),
        ndcg_at_k=round(sum(ndcg_at_k(r, ranked, k) for r, ranked in cases) / n, 4),
        mrr=round(sum(mrr(r, ranked) for r, ranked in cases) / n, 4),
        n=n,
        k=k,
    )
