"""Synthesize Compounding-Wiki entity pages from the knowledge graph.

Reuses the PathRAG KG (entities + relations + full provenance) — no re-extraction.
For each qualifying entity we gather its relations and supporting chunk text and
have the LLM compile a durable, cited markdown page. Runs at ingest time; failures
are non-fatal (the wiki is additive and never blocks indexing).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from auralynq.config import get_settings
from auralynq.llm.base import Context
from auralynq.telemetry import get_logger
from auralynq.wiki.store import WikiStore

if TYPE_CHECKING:
    from auralynq.config.settings import WikiSettings
    from auralynq.ingest.models import Chunk
    from auralynq.llm.base import LLM
    from auralynq.retrieval.pathrag.graph import KnowledgeGraph

_log = get_logger("auralynq.wiki")

WIKI_SYSTEM = (
    "You are Auralynq's wiki compiler. Write a concise, durable encyclopedia-style "
    "page about the given entity using ONLY the numbered evidence provided. "
    "Rules:\n"
    "1. Start with a one-sentence definition of the entity.\n"
    "2. Then a short '## Summary' of what the sources say, citing every claim with "
    "[n] markers.\n"
    "3. Then '## Key relations' as a bullet list of the provided relations, each "
    "with its citation.\n"
    "4. Use [[Other Entity]] wiki-links when you mention another named entity.\n"
    "5. Never invent facts or add anything not supported by the evidence. "
    "If evidence is thin, keep the page short.\n"
    "Output GitHub-flavored markdown only — no frontmatter, no title heading."
)


def _strip_frontmatter(md: str) -> str:
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end != -1:
            return md[end + 4 :].lstrip("\n")
    return md


def _entity_relations(kg: KnowledgeGraph, key: str) -> list[str]:
    """Human-readable relation lines for an entity, both directions, with a
    reliability score and its distinct source count."""
    name_of = lambda k: kg.g.nodes[k].get("name", k) if kg.g.has_node(k) else k  # noqa: E731
    out: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for _, dst, data in kg.g.out_edges(key, data=True):
        d = data.get("_dst", dst)
        sig = (key, data.get("relation", ""), d)
        if sig in seen:
            continue
        seen.add(sig)
        srcs = {getattr(p, "source", "") for p in data.get("provenance", [])}
        out.append(
            f"[[{name_of(key)}]] {data.get('relation', '—')} [[{name_of(d)}]] "
            f"(reliability {data.get('reliability', 0.0):.2f}, {len(srcs)} source(s))"
        )
    for src, _, data in kg.g.in_edges(key, data=True):
        sig = (src, data.get("relation", ""), key)
        if sig in seen:
            continue
        seen.add(sig)
        srcs = {getattr(p, "source", "") for p in data.get("provenance", [])}
        out.append(
            f"[[{name_of(src)}]] {data.get('relation', '—')} [[{name_of(key)}]] "
            f"(reliability {data.get('reliability', 0.0):.2f}, {len(srcs)} source(s))"
        )
    return out


def _evidence(
    chunk_ids: list[str], chunk_by_id: dict[str, Chunk], budget_chars: int
) -> tuple[list[Context], list[str]]:
    """Build numbered evidence Contexts (capped by char budget) + distinct sources."""
    contexts: list[Context] = []
    sources: set[str] = set()
    used = 0
    for cid in chunk_ids:
        c = chunk_by_id.get(cid)
        if c is None:
            continue
        text = (c.text or "").strip()
        if not text:
            continue
        if used + len(text) > budget_chars and contexts:
            break
        used += len(text)
        loc = c.locator() if hasattr(c, "locator") else ""
        contexts.append(
            Context(marker=len(contexts) + 1, text=text, source=c.source, locator=loc)
        )
        if c.source:
            sources.add(c.source)
    return contexts, sorted(sources)


def _build_prompt(name: str, relations: list[str], contexts: list[Context]) -> str:
    lines = [f"ENTITY: {name}", "", "EVIDENCE:"]
    for c in contexts:
        head = f"[{c.marker}]"
        if c.source:
            head += f"  ({c.source}{' · ' + c.locator if c.locator else ''})"
        lines += [head, c.text, ""]
    if relations:
        lines += ["KNOWN RELATIONS (from the knowledge graph):"]
        lines += [f"- {r}" for r in relations]
        lines.append("")
    lines.append(f"Write the wiki page for [[{name}]] now.")
    return "\n".join(lines)


def _synthesize_one(
    kg: KnowledgeGraph,
    key: str,
    data: dict[str, Any],
    chunk_by_id: dict[str, Chunk],
    llm: LLM,
    store: WikiStore,
    w: WikiSettings,
) -> bool:
    name = data.get("name", key)
    chunk_ids = sorted(data.get("chunk_ids", set()))
    contexts, sources = _evidence(chunk_ids, chunk_by_id, w.max_context_chars)
    if not contexts:
        return False
    relations = _entity_relations(kg, key)
    prompt = _build_prompt(name, relations, contexts)
    try:
        body = llm.generate(
            prompt, system=WIKI_SYSTEM, temperature=0.2, max_tokens=w.max_page_tokens
        ).strip()
    except Exception as e:  # pragma: no cover - provider failure is non-fatal
        _log.warning("wiki.page_generate_failed", entity=key, error=str(e))
        return False
    if not body:
        return False
    # Contradiction check: if a page already exists, compare its prior claims
    # against the new synthesis before overwriting (invalidate-not-silently-replace).
    contradictions: list[dict] = []
    if w.detect_contradictions:
        prior = store.read_page(key)
        # Only look for contradictions when NEW evidence was added for this entity
        # — re-synthesizing the same sources just rewords, and contradictions can
        # only come from a new source (also avoids reword false-positives on re-ingest).
        new_sources = set(sources) - set(prior.get("sources", []) or []) if prior else set()
        if prior and new_sources:
            from auralynq.wiki.contradiction import detect_contradictions

            old_body = _strip_frontmatter(prior.get("markdown", ""))
            found = detect_contradictions(name, old_body, body, llm)
            contradictions = [c.to_dict() for c in found]
            if contradictions:
                store.append_log(
                    "contradiction", entity=key, count=len(contradictions),
                    items=contradictions,
                )
                _log.info("wiki.contradiction_flagged", entity=key, n=len(contradictions))
    store.write_page(
        key,
        title=name,
        body=body,
        page_type="entity",
        sources=sources,
        mentions=int(data.get("mentions", 0)),
        contradictions=contradictions,
    )
    return True


def synthesize_wiki(
    kg: KnowledgeGraph,
    chunks: list[Chunk],
    *,
    llm: LLM | None = None,
    settings: Any | None = None,
) -> int:
    """Synthesize/refresh entity pages from the KG. Returns pages written.

    Selects entities with >= ``min_mentions`` mentions, highest-mention first,
    capped at ``max_entities`` per run (cost guard).
    """
    s = settings or get_settings()
    w = s.wiki
    if llm is None:
        from auralynq.llm.factory import get_llm

        llm = get_llm()
    store = WikiStore(s.wiki_dir)
    chunk_by_id: dict[str, Chunk] = {c.id: c for c in chunks}

    ents = [
        (key, data)
        for key, data in kg.g.nodes(data=True)
        if data.get("mentions", 0) >= w.min_mentions
    ]
    ents.sort(key=lambda kd: kd[1].get("mentions", 0), reverse=True)
    ents = ents[: w.max_entities]

    written = 0
    for key, data in ents:
        if _synthesize_one(kg, key, data, chunk_by_id, llm, store, w):
            written += 1

    store.append_log(
        "synthesize", entities_considered=len(ents), pages_written=written
    )
    _log.info("wiki.synthesized", entities=len(ents), pages_written=written)
    return written


def file_answer(
    question: str,
    answer: str,
    citations: list[dict[str, Any]],
    confidence: float | None,
    *,
    settings: Any | None = None,
) -> bool:
    """Compounding loop: file a high-confidence, cited answer back as a durable
    wiki page (type ``answer``) so explorations accumulate instead of vanishing
    into chat history. Skips low-confidence, uncited, or refusal answers."""
    s = settings or get_settings()
    w = s.wiki
    if not (w.enabled and w.file_answers):
        return False
    answer = (answer or "").strip()
    if not answer or not citations or (confidence or 0.0) < w.min_answer_confidence:
        return False

    from auralynq.utils import stable_id

    sources = sorted({str(c.get("source", "")) for c in citations if c.get("source")})
    body = [answer, "", "## Sources"]
    for c in citations:
        src = str(c.get("source", ""))
        loc = str(c.get("locator", ""))
        if src:
            body.append(f"- {src}" + (f" · {loc}" if loc else ""))
    page_id = f"answer_{stable_id(question)[:12]}"
    store = WikiStore(s.wiki_dir)
    store.write_page(
        page_id,
        title=question.strip()[:160],
        body="\n".join(body),
        page_type="answer",
        sources=sources,
    )
    store.append_log("file_answer", page=page_id, question=question[:120], sources=len(sources))
    _log.info("wiki.answer_filed", page=page_id)
    return True
