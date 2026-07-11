"""Agent node functions (planner → … → citation validator).

Each node takes the shared :class:`AgentState` and :class:`AgentDeps`, wraps its
work in a trace span, and mutates/returns state. The same functions are used by
both the LangGraph executor and the native fallback executor (ADR-0008).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from auralynq.agent.state import AgentState
from auralynq.config import Settings
from auralynq.llm.base import LLM, Context
from auralynq.retrieval.hybrid.fusion import reciprocal_rank_fusion
from auralynq.retrieval.hybrid.reorder import lost_in_the_middle_reorder
from auralynq.retrieval.hybrid.retriever import HybridRetriever
from auralynq.retrieval.models import Filter, ScoredChunk
from auralynq.retrieval.pathrag.graph import KnowledgeGraph
from auralynq.retrieval.pathrag.retriever import PathRAGRetriever
from auralynq.retrieval.router import Route, route_query
from auralynq.telemetry.tracing import Trace
from auralynq.utils import tokenize

if TYPE_CHECKING:
    from auralynq.wiki.retriever import WikiRetriever

_MARKER_RE = re.compile(r"\[(\d+)\]")
_STOP = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "of",
    "to",
    "in",
    "on",
    "and",
    "or",
    "how",
    "what",
    "why",
    "who",
    "where",
    "when",
    "does",
    "do",
    "did",
    "between",
    "with",
}


@dataclass
class AgentDeps:
    hybrid: HybridRetriever
    pathrag: PathRAGRetriever
    llm: LLM
    graph: KnowledgeGraph
    trace: Trace
    settings: Settings
    filt: Filter | None = None
    wiki: WikiRetriever | None = None  # set only when the compounding wiki is on


def node_plan(state: AgentState, deps: AgentDeps) -> AgentState:
    with deps.trace.span("planner", question=state.question) as sp:
        if not state.original_question:
            state.original_question = state.question
        sp.attributes["final_k"] = state.final_k
    return state


def node_route(state: AgentState, deps: AgentDeps) -> AgentState:
    with deps.trace.span("router") as sp:
        # Caller hint (e.g. from API route_hint field) overrides the heuristic router.
        if state.route_hint and state.route_hint != "auto":
            try:
                state.route = Route(state.route_hint)
                state.route_confidence = 1.0
                state.route_rationale = f"caller override → {state.route_hint}"
                sp.attributes.update(
                    route=state.route.value, confidence=1.0, rationale=state.route_rationale
                )
                return state
            except ValueError:
                pass  # unknown hint value — fall through to heuristic
        decision = route_query(state.question, deps.graph)
        state.route = decision.route
        state.route_confidence = decision.confidence
        state.route_rationale = decision.rationale
        sp.attributes.update(
            route=decision.route.value, confidence=decision.confidence, rationale=decision.rationale
        )
    return state


def node_retrieve(state: AgentState, deps: AgentDeps) -> AgentState:
    pool_k = max(state.final_k * 2, deps.settings.retrieval.top_k)
    if state.route in (Route.fast, Route.hybrid):
        with deps.trace.span("hybrid_retriever") as sp:
            res = deps.hybrid.retrieve(state.question, pool_k, deps.filt)
            state.contexts.extend(res.chunks)
            sp.attributes.update(n=len(res.chunks), stages=str(res.metadata))
    if state.route in (Route.graph, Route.hybrid):
        with deps.trace.span("pathrag_retriever") as sp:
            res = deps.pathrag.retrieve(state.question, pool_k, deps.filt)
            state.contexts.extend(res.chunks)
            state.path_evidence = [_ev(e) for e in res.metadata.get("paths", [])]
            state.seeds = res.metadata.get("seeds", [])
            sp.attributes.update(
                n=len(res.chunks), seeds=state.seeds, paths=len(state.path_evidence)
            )
    # Fallback: graph-only route that returned no evidence → retry with hybrid so that
    # documents whose text is indexed but whose entities have no graph paths can still
    # be retrieved (e.g. freshly ingested documents with no relational paths yet).
    if state.route == Route.graph and not state.contexts:
        with deps.trace.span("hybrid_fallback") as sp:
            res = deps.hybrid.retrieve(state.question, pool_k, deps.filt)
            state.contexts.extend(res.chunks)
            state.route = Route.hybrid  # reflect the actual retrieval path used
            state.route_rationale += " [graph empty → hybrid fallback]"
            sp.attributes.update(n=len(res.chunks), reason="graph_returned_no_contexts")
    # Compounding wiki (Phase 2): consult pre-synthesized entity pages as an extra,
    # high-value context source. Purely additive — only runs when the wiki is on.
    if deps.wiki is not None:
        with deps.trace.span("wiki_retriever") as sp:
            res = deps.wiki.retrieve(state.question, k=2)
            state.contexts.extend(res.chunks)
            sp.attributes.update(
                n=len(res.chunks), matched=res.metadata.get("pages_matched", 0)
            )
    return state


def node_fuse(state: AgentState, deps: AgentDeps) -> AgentState:
    with deps.trace.span("context_fusion") as sp:
        by_method: dict[str, list[ScoredChunk]] = {}
        for c in state.contexts:
            by_method.setdefault(c.method, []).append(c)
        for lst in by_method.values():
            lst.sort(key=lambda c: c.score, reverse=True)
        fused = reciprocal_rank_fusion(
            list(by_method.values()), k=deps.settings.retrieval.rrf_k, top_k=state.final_k
        )
        fused = lost_in_the_middle_reorder(fused)
        state.contexts = fused
        sp.attributes.update(methods=list(by_method.keys()), final=len(fused))
    return state


def node_critic(state: AgentState, deps: AgentDeps) -> AgentState:
    """Dual-signal evidence sufficiency critic — paper §4.2, Eqs. 3-5.

    rewrite(q, R) = 1[ lex(q,R) < tau_l  AND  sem(q,R) < tau_s ]
      tau_l = 0.60  (lexical key-term coverage threshold)
      tau_s = 0.50  (semantic cosine coverage threshold)

    The AND gate ensures a rewrite fires only when *both* signals indicate a gap.
    High semantic coverage (sem >= tau_s) means the context is on-topic despite
    surface-vocabulary mismatch; rewriting would fetch the same passages with
    lower diversity (Eq. 10, false-positive bound).
    """
    _LEX_TAU = 0.60
    _SEM_TAU = 0.50

    with deps.trace.span("evidence_gap_critic") as sp:
        # lex(q, R) = |T_q intersect union_i T_{c_i}| / |T_q|  (Eq. 3)
        q_terms = {t for t in tokenize(state.original_question) if t not in _STOP and len(t) > 2}
        covered: set[str] = set()
        for c in state.contexts:
            covered |= set(tokenize(c.chunk.text))
        missing = sorted(q_terms - covered)
        lex_cov = len(q_terms & covered) / max(len(q_terms), 1)
        state.gaps = missing
        state.coverage = round(lex_cov, 3)

        # sem(q, R) = cos(q, mean_i(c_i))  mapped to [0,1]  (Eq. 4)
        sem_cov = _semantic_coverage(state.original_question, state.contexts, deps)
        state.semantic_coverage = round(sem_cov, 3)

        can_retry = state.iteration < state.max_iters - 1 and not state.out_of_budget()

        # Eq. 5: rewrite iff lex < tau_l AND sem < tau_s
        state.need_rewrite = lex_cov < _LEX_TAU and sem_cov < _SEM_TAU and can_retry

        sp.attributes.update(
            lex_coverage=round(lex_cov, 3),
            sem_coverage=round(sem_cov, 3),
            lex_tau=_LEX_TAU,
            sem_tau=_SEM_TAU,
            missing_terms=missing,
            need_rewrite=state.need_rewrite,
        )
    return state


def _semantic_coverage(question: str, contexts: list, deps: AgentDeps) -> float:
    """Semantic coverage: sem(q, R) = cos(q, mean_i c_i) mapped to [0,1] — Eq. 4.

    Returns 1.0 (fully covered) when using the hash-embedding fallback because the
    hash embedder produces random unit vectors that carry no semantic information;
    letting it return 0.0 would cause the AND-gate (Eq. 5) to fire spuriously on
    the semantic dimension whenever lexical coverage is also low.
    """
    if not contexts:
        return 0.0
    try:
        emb = deps.hybrid.embedder
        if getattr(emb, "name", "") in ("hashing", "hash"):
            # Hash embedder provides no meaningful cosine signal — treat as covered
            # so the dual-signal AND gate degrades gracefully to lex-only gating.
            return 1.0
        q_vec = emb.embed_query(question).dense
        texts = [c.chunk.text[:512] for c in contexts]
        ctx_embs = emb.embed(texts).dense

        import numpy as np

        # mean pooling over context embeddings, then cosine sim with query
        ctx_mean = np.mean(ctx_embs, axis=0)
        norm_q = float(np.linalg.norm(q_vec)) or 1.0
        norm_c = float(np.linalg.norm(ctx_mean)) or 1.0
        sim = float(np.dot(q_vec, ctx_mean) / (norm_q * norm_c))
        return float(max(0.0, min(1.0, (sim + 1.0) / 2.0)))  # map [-1,1] → [0,1]
    except Exception:  # pragma: no cover — embedder error must not break the loop
        return 0.0


def node_rewrite(state: AgentState, deps: AgentDeps) -> AgentState:
    with deps.trace.span("query_rewrite") as sp:
        state.iteration += 1
        extra = " ".join(state.gaps[:5] + state.seeds[:3])
        state.question = f"{state.original_question} {extra}".strip()
        state.contexts = []  # re-retrieve fresh on the rewritten query
        state.need_rewrite = False
        sp.attributes.update(iteration=state.iteration, rewritten=state.question)
    return state


def _contexts_for_llm(state: AgentState) -> list[Context]:
    out: list[Context] = []
    for i, c in enumerate(state.contexts, start=1):
        cit = c.chunk.citation()
        out.append(
            Context(
                marker=i, text=c.chunk.text, source=str(cit["source"]), locator=str(cit["locator"])
            )
        )
    return out


def node_synthesize(state: AgentState, deps: AgentDeps) -> AgentState:
    with deps.trace.span("synthesizer", provider=deps.llm.name) as sp:
        contexts = _contexts_for_llm(state)
        if not contexts:
            state.answer = "I don't have enough evidence in the indexed sources to answer that."
        else:
            state.answer = deps.llm.answer(
                state.original_question,
                contexts,
                temperature=deps.settings.llm.temperature,
                max_tokens=deps.settings.llm.max_tokens,
            ).strip()
        sp.attributes["chars"] = len(state.answer)
    return state


def node_self_check(state: AgentState, deps: AgentDeps) -> AgentState:
    """Four-signal calibrated confidence — paper §4.3, Eqs. 6-10.

    p̂ = w^T s  =  0.30·s_qual + 0.30·s_cite + 0.25·s_sem + 0.15·s_tok

    s_qual: clip(r̄ / r_ref, 0, 1)            retrieval score quality  (Eq. 7)
    s_cite: |K| / |R|                          citation coverage        (Eq. 8)
    s_sem:  sem(q, R)                          semantic coverage        (Eq. 9, from critic)
    s_tok:  |T_q ∩ T_a| / |T_q|               answer token coverage    (Eq. 10)

    All four signals are stored in state.confidence_signals for the UI ConfidenceBar.
    """
    with deps.trace.span("self_check") as sp:
        markers = {int(m) for m in _MARKER_RE.findall(state.answer)}
        valid = {m for m in markers if 1 <= m <= len(state.contexts)}
        if not valid and state.contexts:
            state.notes.append("answer lacked citations; flagged low confidence")

        # s_qual = clip(r̄ / r_ref, 0, 1)  (Eq. 7)
        s_qual = _retrieval_score_quality(state.contexts)

        # s_cite = |K| / |R|  (Eq. 8): fraction of retrieved chunks cited by LLM
        s_cite = len(valid) / max(len(state.contexts), 1) if state.contexts else 0.0

        # s_sem from critic node (Eq. 9)
        s_sem = state.semantic_coverage

        # s_tok = |T_q ∩ T_a| / |T_q|  (Eq. 10): query key-terms present in answer
        # NOTE: computed against the generated answer, not against context gaps.
        q_terms = {t for t in tokenize(state.original_question) if t not in _STOP and len(t) > 2}
        a_terms = {t for t in tokenize(state.answer) if t not in _STOP and len(t) > 2}
        s_tok = len(q_terms & a_terms) / max(len(q_terms), 1) if q_terms else 1.0

        confidence = round(0.30 * s_qual + 0.30 * s_cite + 0.25 * s_sem + 0.15 * s_tok, 3)
        state.confidence = confidence
        state.confidence_signals = {
            "s_qual": round(s_qual, 3),
            "s_cite": round(s_cite, 3),
            "s_sem": round(s_sem, 3),
            "s_tok": round(s_tok, 3),
        }

        sp.attributes.update(
            citations_used=sorted(valid),
            confidence=confidence,
            **state.confidence_signals,
        )
    return state


def _retrieval_score_quality(contexts: list) -> float:
    """Mean retrieval score normalised to [0,1].

    Reference point 0.7: bge-m3 cross-encoder scores for clearly on-topic
    passages centre around 0.65-0.80.  Scores below 0.3 indicate marginal
    relevance; above 0.8 indicate high precision. Clamp to [0,1].
    """
    if not contexts:
        return 0.0
    scores = [getattr(c, "score", 0.0) or 0.0 for c in contexts]
    mean_s = sum(scores) / len(scores)
    return float(min(1.0, max(0.0, mean_s / 0.7)))


def node_validate_citations(state: AgentState, deps: AgentDeps) -> AgentState:
    with deps.trace.span("citation_validator") as sp:
        used = sorted(
            {int(m) for m in _MARKER_RE.findall(state.answer) if 1 <= int(m) <= len(state.contexts)}
        )

        # Drop dangling markers that point outside the context set.
        def _scrub(match: re.Match) -> str:
            n = int(match.group(1))
            return match.group(0) if 1 <= n <= len(state.contexts) else ""

        state.answer = _MARKER_RE.sub(_scrub, state.answer).strip()
        citations = []
        for n in used:
            sc = state.contexts[n - 1]
            cit = sc.chunk.citation()
            cit["marker"] = n
            # Thread retrieval score and method so the UI can show evidence quality.
            cit["score"] = round(float(sc.score or 0.0), 4)
            cit["method"] = sc.method or "unknown"
            citations.append(cit)
        state.citations = citations
        sp.attributes.update(n_citations=len(citations))
    return state


def _ev(d: dict):
    from auralynq.retrieval.models import PathEvidence

    return PathEvidence.model_validate(d)
