"""Reciprocal Rank Fusion (Cormack et al., 2009)."""

from __future__ import annotations

from auralynq.retrieval.models import ScoredChunk


def reciprocal_rank_fusion(
    rankings: list[list[ScoredChunk]],
    k: int = 60,
    top_k: int | None = None,
    weights: list[float] | None = None,
) -> list[ScoredChunk]:
    """Fuse multiple ranked lists into one. Score = Σ w_i / (k + rank_i)."""
    weights = weights or [1.0] * len(rankings)
    scores: dict[str, float] = {}
    keep: dict[str, ScoredChunk] = {}
    comps: dict[str, dict[str, float]] = {}
    for li, ranking in enumerate(rankings):
        w = weights[li] if li < len(weights) else 1.0
        for rank, sc in enumerate(ranking):
            cid = sc.chunk.id
            contrib = w / (k + rank + 1)
            scores[cid] = scores.get(cid, 0.0) + contrib
            comps.setdefault(cid, {})[sc.method] = round(sc.score, 4)
            if cid not in keep:
                keep[cid] = sc
    fused = [
        keep[cid].model_copy(
            update={"score": score, "method": "rrf", "components": comps.get(cid, {})}
        )
        for cid, score in scores.items()
    ]
    fused.sort(key=lambda c: c.score, reverse=True)
    for i, c in enumerate(fused):
        c.rank = i
    return fused[:top_k] if top_k else fused
