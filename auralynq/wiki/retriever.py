"""Retrieve pre-synthesized wiki pages to consult before/alongside chunk search.

The compounding-wiki payoff at query time: for entity questions the answer is
already compiled on a durable page, so we surface that page as a high-priority,
cleanly-citable context instead of re-stitching raw chunks. Lexical entity match
(no extra index needed); returns the page body with its internal [n] markers
stripped so it becomes one citation of its own rather than clashing with the
answer's citation numbering.
"""

from __future__ import annotations

import re
import time

from auralynq.ingest.models import Chunk, SourceType
from auralynq.retrieval.models import RetrievalResult, ScoredChunk
from auralynq.wiki.store import WikiStore

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_MARKER_RE = re.compile(r"\[\d+\]")
_STOP = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are",
    "was", "were", "what", "who", "where", "when", "why", "how", "does", "do",
    "did", "with", "about", "tell", "me", "explain", "describe",
}


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP and len(t) > 1}


def _strip_frontmatter(md: str) -> str:
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end != -1:
            return md[end + 4 :].lstrip("\n")
    return md


class WikiRetriever:
    name = "wiki"

    def __init__(self, wiki_dir) -> None:  # noqa: ANN001 - Path
        self.store = WikiStore(wiki_dir)

    def retrieve(self, query: str, k: int = 2) -> RetrievalResult:
        t0 = time.perf_counter()
        q_tokens = _tokens(query)
        scored: list[tuple[float, dict]] = []
        for meta in self.store.list_pages():
            title = str(meta.get("title") or meta.get("id", ""))
            name_tokens = _tokens(title) | _tokens(str(meta.get("id", "")))
            if not name_tokens:
                continue
            overlap = len(q_tokens & name_tokens)
            if overlap == 0:
                continue
            # Score: fraction of the entity name covered by the query, + a boost
            # when the full entity title appears verbatim in the query.
            frac = overlap / len(name_tokens)
            boost = 0.25 if title.lower() in query.lower() else 0.0
            scored.append((min(1.0, 0.6 * frac + boost + 0.15 * overlap), meta))

        scored.sort(key=lambda s: s[0], reverse=True)
        chunks: list[ScoredChunk] = []
        for rank, (score, meta) in enumerate(scored[: max(1, k)]):
            page = self.store.read_page(meta["id"])
            if not page:
                continue
            body = _MARKER_RE.sub("", _strip_frontmatter(page["markdown"])).strip()
            if not body:
                continue
            title = str(meta.get("title") or meta["id"])
            chunk = Chunk(
                id=f"wiki:{meta['id']}",
                doc_id="wiki",
                text=body,
                source=f"{title} (wiki)",
                source_type=SourceType.text,
                title=title,
            )
            chunks.append(
                ScoredChunk(chunk=chunk, score=round(score, 4), method="wiki", rank=rank)
            )
        return RetrievalResult(
            query=query,
            method="wiki",
            chunks=chunks,
            took_ms=(time.perf_counter() - t0) * 1000,
            metadata={"pages_matched": len(scored)},
        )
