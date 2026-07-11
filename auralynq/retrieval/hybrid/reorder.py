"""Lost-in-the-middle context reordering (Liu et al., 2023).

LLMs attend best to the start and end of the context window. Given chunks sorted
by relevance (most relevant first), interleave them so the most relevant land at
the edges and the least relevant in the middle.
"""

from __future__ import annotations

from auralynq.retrieval.models import ScoredChunk


def lost_in_the_middle_reorder(chunks: list[ScoredChunk]) -> list[ScoredChunk]:
    if len(chunks) <= 2:
        return chunks
    head: list[ScoredChunk] = []
    tail: list[ScoredChunk] = []
    for i, c in enumerate(chunks):  # chunks assumed already relevance-sorted
        (head if i % 2 == 0 else tail).append(c)
    ordered = head + tail[::-1]
    for i, c in enumerate(ordered):
        c.rank = i
    return ordered
