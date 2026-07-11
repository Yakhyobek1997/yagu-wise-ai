"""High-level agent entry points used by the CLI, API and MCP server."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel, Field

from auralynq.agent.cache import SemanticCache
from auralynq.agent.graph import run_agent
from auralynq.agent.nodes import (
    AgentDeps,
    _contexts_for_llm,
    node_critic,
    node_fuse,
    node_plan,
    node_retrieve,
    node_rewrite,
    node_route,
    node_self_check,
    node_validate_citations,
)
from auralynq.agent.state import AgentState
from auralynq.config import get_settings
from auralynq.llm.factory import get_llm
from auralynq.pipeline import load_graph
from auralynq.retrieval.hybrid.retriever import HybridRetriever
from auralynq.retrieval.models import Filter
from auralynq.retrieval.pathrag.retriever import PathRAGRetriever
from auralynq.telemetry.tracing import Trace
from auralynq.utils import stable_id

_CACHE = SemanticCache()


def _export_langfuse(trace: Trace, question: str, answer: str, metadata: dict) -> None:
    """Best-effort hosted-trace export; never affects the response (ADR-0019)."""
    try:
        from auralynq.telemetry.langfuse_export import export_trace

        export_trace(trace, question=question, answer=answer, metadata=metadata)
    except Exception:  # pragma: no cover - observability must not break answers
        pass


_REFUSAL_MARKERS = (
    "don't have enough evidence",
    "do not have enough evidence",
    "not enough evidence",
    "no relevant evidence",
)


def _is_refusal(answer: str, has_contexts: bool) -> bool:
    """An answer is an abstention if it has no grounding *or* says so outright."""
    low = (answer or "").lower()
    if any(m in low for m in _REFUSAL_MARKERS):
        return True
    return not has_contexts and not low.strip()


def _snippets(state: AgentState, limit: int = 3) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c in state.contexts[:limit]:
        cit = c.chunk.citation()
        out.append(
            {
                "source": str(cit.get("source", "")),
                "locator": str(cit.get("locator", "")),
                "score": round(float(getattr(c, "score", 0.0) or 0.0), 4),
                "text": c.chunk.text[:280],
            }
        )
    return out


def _insufficiency(
    state: AgentState, detected: list[str], suggestions: list[str]
) -> dict[str, Any]:
    """Structured, trustworthy explanation of *why* we abstained."""
    snippets = _snippets(state)
    in_corpus = bool(detected)
    n = len(state.contexts)
    if not state.contexts:
        why = (
            "Retrieval returned no passages above the relevance threshold for this "
            "question — the indexed corpus does not appear to cover it."
        )
    elif state.coverage < 0.6:
        why = (
            f"Retrieved {n} passage(s), but they covered only "
            f"{round(state.coverage * 100)}% of the question's key terms — not enough "
            "to ground a faithful, cited answer."
        )
    else:
        why = (
            f"Retrieved {n} passage(s) on related topics, but none directly answered "
            "the question, so the model declined to ground a confident, cited answer "
            "rather than guess."
        )
    return {
        "summary": (
            "Auralynq could not answer because the indexed corpus does not contain "
            "enough relevant evidence."
        ),
        "detected_entities": detected,
        "route_attempted": state.route.value,
        "retrieved_snippets": snippets,
        "why_insufficient": why,
        "suggested_questions": suggestions,
        "suggest_ingest": not in_corpus,
    }


class AnswerResult(BaseModel):
    answer: str
    status: str = "answered"
    citations: list[dict[str, Any]] = Field(default_factory=list)
    route: str = "fast"
    route_confidence: float = 0.0
    route_rationale: str = ""
    path_evidence: list[dict[str, Any]] = Field(default_factory=list)
    seeds: list[str] = Field(default_factory=list)
    iterations: int = 0
    confidence: float = 0.0
    # Per-signal breakdown (paper §4.3, Eq. 6): s_qual, s_cite, s_sem, s_tok
    confidence_signals: dict[str, float] = Field(default_factory=dict)
    evidence_coverage: float = 0.0
    cached: bool = False
    elapsed_ms: float = 0.0
    contexts: list[str] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)
    trace_steps: list[dict[str, Any]] = Field(default_factory=list)
    detected_entities: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    insufficient_evidence_reason: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    provider_status: list[dict[str, str]] = Field(default_factory=list)
    model_fit: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


def _build_modelfit_snapshot(provider: str, model_name: str) -> dict[str, Any] | None:
    """Return a lightweight ModelFit snapshot for the current LLM selection.

    Never raises — ModelFit is purely informational and must not affect answers.
    Returns None if ModelFit is unavailable or the model is not in the registry.
    """
    try:
        from auralynq.modelfit.hardware import probe_hardware
        from auralynq.modelfit.model_registry import get_registry
        from auralynq.modelfit.scoring import score_model

        registry = get_registry()

        # Map the active provider+model to a ModelFit model_id
        if provider == "ollama":
            model_id = f"ollama:{model_name}"
        elif provider == "slm":
            # For SLM, the display name is the GGUF filename, not the llm.model tag
            slm_name = get_settings().llm.slm_filename.replace(".gguf", "")
            model_id = f"local:{slm_name}"
        else:
            return None  # cloud providers — ModelFit only covers local

        m = registry.get(model_id)
        if m is None:
            return {
                "enabled": True,
                "selected_model": model_id,
                "fit_score": None,
                "fit_level": None,
                "fit_label": None,
                "quantization": None,
                "estimated_vram_gb": None,
                "hardware_warning": f"Model '{model_id}' not in ModelFit registry.",
                "hardware_warnings": [f"Model '{model_id}' not in ModelFit registry."],
                "measured_tok_per_sec": None,
                "estimate_used": True,
                "measured_available": False,
                "recommendation_reason": "Model not found in ModelFit registry.",
            }

        hw = probe_hardware()
        s = score_model(m, hw, requested_tasks=["rag"])
        re = s.resource_estimate
        hw_warning = None
        if re and re.fit_level in ("not_recommended", "impossible"):
            hw_warning = f"Model may not fit hardware ({re.fit_level.replace('_', ' ')})."
        elif hw.warnings:
            hw_warning = hw.warnings[0]

        measured_available = s.benchmark is not None and s.benchmark.avg_tok_per_sec is not None
        reason_parts = [f"score {round(s.overall_score)}/100"]
        if re:
            reason_parts.append(f"{re.fit_level.replace('_', ' ')} VRAM fit")
        if s.best_quantization:
            reason_parts.append(s.best_quantization)
        recommendation_reason = "; ".join(reason_parts)

        return {
            "enabled": True,
            "selected_model": model_id,
            "fit_score": round(s.overall_score, 1),
            "fit_level": s.label,
            "fit_label": s.label,
            "quantization": s.best_quantization,
            "estimated_vram_gb": re.estimated_vram_gb if re else None,
            "hardware_warning": hw_warning,
            "hardware_warnings": [hw_warning] if hw_warning else [],
            "measured_tok_per_sec": (s.benchmark.avg_tok_per_sec if s.benchmark else None),
            "estimate_used": s.estimate_used,
            "measured_available": measured_available,
            "recommendation_reason": recommendation_reason,
        }
    except Exception:
        return None  # ModelFit is optional — never break the answer pipeline


def _build_deps(trace: Trace, filt: Filter | None) -> AgentDeps:
    s = get_settings()
    graph = load_graph()
    hybrid = HybridRetriever()
    wiki = None
    if s.wiki.enabled:
        from auralynq.wiki.retriever import WikiRetriever

        wiki = WikiRetriever(s.wiki_dir)
    return AgentDeps(
        hybrid=hybrid,
        pathrag=PathRAGRetriever(graph, store=hybrid.store, embedder=hybrid.embedder),
        llm=get_llm(),
        graph=graph,
        trace=trace,
        settings=s,
        filt=filt,
        wiki=wiki,
    )


def _maybe_file_answer(question: str, state: AgentState, refused: bool) -> None:
    """Compounding loop (Phase 3b): file a good answer back as a wiki page.
    Gated + non-fatal — never affects the response on failure."""
    s = get_settings()
    if refused or not (s.wiki.enabled and s.wiki.file_answers):
        return
    try:
        from auralynq.wiki.generator import file_answer

        file_answer(question, state.answer, state.citations, state.confidence, settings=s)
    except Exception as e:  # pragma: no cover - non-fatal by design
        _log.warning("wiki.file_answer_failed", error=str(e))


def _new_state(question: str, final_k: int | None, route_hint: str = "") -> AgentState:
    s = get_settings()
    return AgentState(
        question=question,
        original_question=question,
        final_k=final_k or s.retrieval.final_k,
        max_iters=s.agent.max_iters,
        latency_budget_ms=s.agent.latency_budget_ms,
        route_hint=route_hint,
    )


def answer_question(
    question: str,
    final_k: int | None = None,
    filt: Filter | None = None,
    use_cache: bool | None = None,
    route_hint: str = "",
) -> AnswerResult:
    s = get_settings()
    use_cache = s.agent.semantic_cache if use_cache is None else use_cache
    trace = Trace(trace_id=stable_id(question))

    if use_cache:
        hit = _CACHE.lookup(question)
        if hit is not None:
            answer, citations = hit
            return AnswerResult(
                answer=answer, citations=citations, cached=True, trace=trace.to_list()
            )

    deps = _build_deps(trace, filt)
    state = _new_state(question, final_k, route_hint=route_hint)
    state = run_agent(state, deps)

    from auralynq.providers import describe_providers
    from auralynq.serving.corpus import corpus_summary, detect_entities, suggested_questions
    from auralynq.serving.observability import to_trace_steps

    summary = corpus_summary()
    detected = detect_entities(question, summary)
    suggestions = suggested_questions(3, summary)
    refused = _is_refusal(state.answer, bool(state.contexts))
    trace_list = trace.to_list()
    _maybe_file_answer(question, state, refused)

    result = AnswerResult(
        answer=state.answer,
        status="insufficient_evidence" if refused else "answered",
        citations=state.citations,
        route=state.route.value,
        route_confidence=state.route_confidence,
        route_rationale=state.route_rationale,
        path_evidence=[e.model_dump() for e in state.path_evidence],
        seeds=state.seeds,
        iterations=state.iteration,
        confidence=state.confidence,
        confidence_signals=state.confidence_signals,
        evidence_coverage=state.coverage,
        elapsed_ms=round(trace.total_ms, 2),
        contexts=[c.chunk.text for c in state.contexts],
        trace=trace_list,
        trace_steps=to_trace_steps(trace_list),
        detected_entities=detected,
        suggested_questions=suggestions,
        insufficient_evidence_reason=(
            _insufficiency(state, detected, suggestions) if refused else None
        ),
        warnings=list(state.notes),
        provider_status=describe_providers(),
    )
    # Attach ModelFit metadata — purely informational, never raises
    try:
        from auralynq.llm.factory import resolved_provider

        _prov = resolved_provider()
        _model = get_settings().llm.model
        result.model_fit = _build_modelfit_snapshot(_prov, _model)
    except Exception:
        pass

    if use_cache and state.answer:
        _CACHE.store(question, state.answer, state.citations)
    _export_langfuse(
        trace,
        question,
        state.answer,
        {
            "route": state.route.value,
            "confidence": state.confidence,
            "iterations": state.iteration,
            "cached": False,
        },
    )
    return result


def stream_answer_question(
    question: str, final_k: int | None = None, filt: Filter | None = None
) -> Iterator[dict[str, Any]]:
    """Yield SSE-style events: {'type': 'token'|'meta'|'final', ...}."""
    trace = Trace(trace_id=stable_id(question))
    deps = _build_deps(trace, filt)
    state = _new_state(question, final_k)

    # Run retrieval + fusion + critic/rewrite loop (non-streamed).
    state = node_plan(state, deps)
    while True:
        state = node_route(state, deps)
        state = node_retrieve(state, deps)
        state = node_fuse(state, deps)
        state = node_critic(state, deps)
        state.elapsed_ms = trace.total_ms
        if state.need_rewrite and not state.out_of_budget():
            state = node_rewrite(state, deps)
            continue
        break

    from auralynq.serving.corpus import corpus_summary, detect_entities, suggested_questions

    _summary = corpus_summary()
    _detected = detect_entities(question, _summary)
    _suggestions = suggested_questions(3, _summary)

    # Retrieved source candidates — emitted before generation so the UI can show
    # real source cards while the answer streams (progressive evidence). These are
    # candidates; the `final` event carries the actually-cited subset. `marker`
    # aligns with the eventual citation index so cards are number-matched early.
    _source_candidates = [
        {
            **c.chunk.citation(),
            "marker": i,
            "score": round(float(c.score or 0.0), 4),
            "method": c.method or "unknown",
        }
        for i, c in enumerate(state.contexts[:8], start=1)
    ]

    yield {
        "type": "meta",
        "route": state.route.value,
        "confidence": state.route_confidence,
        "rationale": state.route_rationale,
        "seeds": state.seeds,
        "path_evidence": [e.model_dump() for e in state.path_evidence],
        "detected_entities": _detected,
        "evidence_coverage": state.coverage,
        "sources": _source_candidates,
    }

    contexts = _contexts_for_llm(state)
    acc = []
    with trace.span("synthesizer_stream", provider=deps.llm.name):
        if not contexts:
            msg = "I don't have enough evidence in the indexed sources to answer that."
            acc.append(msg)
            yield {"type": "token", "text": msg}
        else:
            for tok in deps.llm.stream_answer(
                state.original_question,
                contexts,
                temperature=deps.settings.llm.temperature,
                max_tokens=deps.settings.llm.max_tokens,
            ):
                acc.append(tok)
                yield {"type": "token", "text": tok}

    state.answer = "".join(acc).strip()
    state = node_self_check(state, deps)
    state = node_validate_citations(state, deps)
    _export_langfuse(
        trace,
        question,
        state.answer,
        {"route": state.route.value, "confidence": state.confidence, "streamed": True},
    )
    from auralynq.serving.observability import to_trace_steps

    refused = _is_refusal(state.answer, bool(state.contexts))
    trace_list = trace.to_list()
    _maybe_file_answer(question, state, refused)

    _model_fit = None
    try:
        from auralynq.llm.factory import resolved_provider

        _model_fit = _build_modelfit_snapshot(resolved_provider(), get_settings().llm.model)
    except Exception:
        pass

    yield {
        "type": "final",
        "answer": state.answer,
        "status": "insufficient_evidence" if refused else "answered",
        "citations": state.citations,
        "confidence": state.confidence,
        "evidence_coverage": state.coverage,
        "semantic_coverage": state.semantic_coverage,
        "elapsed_ms": round(trace.total_ms, 2),
        "trace": trace_list,
        "trace_steps": to_trace_steps(trace_list),
        "detected_entities": _detected,
        "suggested_questions": _suggestions,
        "warnings": list(state.notes),
        "insufficient_evidence_reason": (
            _insufficiency(state, _detected, _suggestions) if refused else None
        ),
        "model_fit": _model_fit,
    }
