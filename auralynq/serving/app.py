"""Auralynq FastAPI backend.

Async API with SSE token streaming for chat, a WebSocket voice channel, ingest /
query / voice / health / metrics / eval endpoints, request IDs, rate limiting and
safe file handling. All heavy work degrades to offline fallbacks (ADR-0003).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
import time
import uuid
from collections import Counter
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from auralynq import __version__
from auralynq.config import get_settings
from auralynq.providers import health_snapshot
from auralynq.serving.auth import AuthMiddleware
from auralynq.serving.errors import (
    AuralynqError,
    auralynq_error_handler,
    http_exception_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from auralynq.retrieval.models import Filter
from auralynq.serving.ratelimit import RateLimitMiddleware
from auralynq.serving.schemas import (
    CorpusClearConfirmRequest,
    CorpusDocument,
    CorpusDocumentsResponse,
    WatchStatusResponse,
    WatchSyncResponse,
    WikiLintResponse,
    WikiPageResponse,
    WikiPageSummary,
    WikiPagesResponse,
    CorpusClearPreviewResponse,
    CorpusDeleteDocumentConfirmRequest,
    CorpusDeleteDocumentPreviewResponse,
    CorpusDeleteReportResponse,
    CorpusSummaryResponse,
    DocumentGroundingStatusResponse,
    DocumentPagesResponse,
    EvalFeedbackRequest,
    HealthResponse,
    IngestResponse,
    ObservabilitySummaryResponse,
    PageInfo,
    PageLayoutBlock,
    PageLayoutResponse,
    QueryRequest,
    QueryRequestV2,
    QueryResponse,
    RAGStrategiesResponse,
    StatusResponse,
    SuggestionsResponse,
    VoiceResponse,
)
from auralynq.telemetry import configure_logging, get_logger, init_telemetry

_log = get_logger("auralynq.api")
_METRICS: Counter = Counter()
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")

# --- Backend intent classifier -------------------------------------------
# Classifies questions that must skip RAG and be answered from system state.
# Intercepts at the query endpoint level before answer_question() is called.

_CORPUS_MGMT_PATTERNS = [
    re.compile(
        r"\b(delete|remove|wipe|clear|purge|erase|drop|reset)\b"
        r".*\b(document|file|corpus|collection|index|vector|upload|pdf|docx"
        r"|data|db|library|everything|all|last|uploaded)\b",
        re.I,
    ),
    re.compile(
        r"\b(delete|remove|wipe|clear|purge|erase|drop|reset)\b.*\b(my|the)\b",
        re.I,
    ),
    re.compile(
        r"\b(how|can i|how do i|can you|please)\b"
        r".*\b(delete|remove|clear|wipe|reset|purge)\b",
        re.I,
    ),
    re.compile(
        r"\b(delete|remove)\b.*\b(last|latest|most recent|previously)\b"
        r".*\b(document|file|upload|doc|pdf)\b",
        re.I,
    ),
    re.compile(
        r"\b(clear|wipe|reset)\b.*\b(corpus|collection|vectors?|index|everything)\b",
        re.I,
    ),
    re.compile(r"\b(remove|delete)\b.*permanently", re.I),
]

_CORPUS_INVENTORY_PATTERNS = [
    re.compile(
        r"\b(how many|how much|count|number of)\b"
        r".*\b(document|file|doc|vector|entit|page|chunk|upload|index)\b",
        re.I,
    ),
    re.compile(r"\bhow many\b", re.I),  # "how many documents do I have?"
    re.compile(
        r"\b(what|which|list|show)\b.*\b(document|file|doc|upload|index)\b",
        re.I,
    ),
    re.compile(
        r"\b(do i have|are there|is there)\b"
        r".*\b(document|file|doc|upload|index|arabic|english|french)\b",
        re.I,
    ),
    re.compile(r"\bare there any (documents?|files?|docs?)\b", re.I),
    re.compile(r"\b(list|show)\b.*\b(document|file|doc|indexed)\b", re.I),
    re.compile(r"\bin my (corpus|collection|library|index)\b", re.I),
    re.compile(r"\bwhat (documents?|files?) (do i|have i|are)\b", re.I),
    re.compile(
        r"\b(last|latest|most recent|recently)\b.*\b(document|file|upload|index|add)\b",
        re.I,
    ),
    re.compile(r"\b(what was|what is) the last\b", re.I),
    re.compile(r"\bhow many.*so far\b", re.I),
    re.compile(r"\b(my|the) (corpus|collection) (is|has|contains|include)\b", re.I),
]

_APP_HELP_PATTERNS = [
    re.compile(
        r"\bhow (do|can|to) (i|you|we)\b.*(upload|ingest|index|add|use|start|begin|reindex)\b",
        re.I,
    ),
    re.compile(
        r"\bhow (does|to) (upload|ingest|index|reindex|delete|remove)\b",
        re.I,
    ),
    re.compile(
        r"\b(what|which) (file types?|formats?|documents?)\b.*(support|accept|upload|ingest)\b",
        re.I,
    ),
]


def _classify_corpus_intent(question: str) -> str | None:
    """Return a corpus-management intent label, or None for normal RAG questions."""
    q = question.strip()
    for pat in _CORPUS_MGMT_PATTERNS:
        if pat.search(q):
            return "corpus_management"
    for pat in _CORPUS_INVENTORY_PATTERNS:
        if pat.search(q):
            return "corpus_inventory"
    for pat in _APP_HELP_PATTERNS:
        if pat.search(q):
            return "app_help"
    return None


def _system_answer_for_intent(intent: str, question: str) -> dict[str, Any]:
    """Build a system-sourced answer dict for non-RAG intents."""
    from auralynq.serving.corpus import corpus_summary, suggested_questions

    summary = corpus_summary(use_cache=False)
    doc_count = summary.get("indexed_document_count", 0)
    vector_count = summary.get("vector_count", 0)
    entity_count = summary.get("entity_count", 0)
    titles = summary.get("document_titles", [])
    last_doc = summary.get("last_document_title")

    if intent == "corpus_inventory":
        lines = [
            f"Your corpus currently contains **{doc_count} document(s)**,"
            f" **{vector_count} vector(s)**, and **{entity_count} entities**."
        ]
        if titles:
            doc_list = "\n".join(f"  - {t}" for t in titles[:20])
            lines.append(f"\n**Indexed documents:**\n{doc_list}")
        if last_doc:
            lines.append(f"\n**Last document added:** {last_doc}")
        langs = summary.get("languages", [])
        if langs:
            lines.append(f"\n**Languages detected:** {', '.join(langs)}")
        if not titles:
            lines = ["Your corpus is **empty**. Upload a document to begin."]
        answer = "\n".join(lines)

    elif intent == "corpus_management":
        answer = (
            "To manage your corpus, use the **Ingest** panel → **Manage Corpus** section.\n\n"
            "Available actions:\n"
            "- **Delete last document**: removes the most recently indexed file\n"
            "- **Clear all corpus**: removes all documents, vectors, and entities\n"
            "- **Delete a specific document**: select from the document list\n\n"
            f"Current corpus: **{doc_count}** document(s), **{vector_count}** vectors."
        )

    else:  # app_help
        answer = (
            "**Getting started with Auralynq:**\n\n"
            "1. **Upload documents**: drag a file onto the Ingest panel\n"
            "2. **Ask questions**: type or speak a question in the composer\n"
            "3. **Manage corpus**: use Ingest → Manage Corpus to delete or clear\n"
            "4. **Supported formats**: PDF, DOCX, HTML, Markdown, TXT, WAV, MP3, M4A"
        )

    rationale = f"retrieval skipped: system/{intent} intent detected"
    trace_step = {
        "id": 1,
        "name": "intent_classifier",
        "label": f"System: {intent}",
        "status": "success",
        "duration_ms": 0,
        "warnings": [],
        "attributes": {"intent": intent},
    }
    return {
        "answer": answer,
        "status": "answered",
        "citations": [],
        "route": intent,
        "route_confidence": 1.0,
        "route_rationale": rationale,
        "path_evidence": [],
        "seeds": [],
        "iterations": 0,
        "confidence": 1.0,
        "evidence_coverage": 0.0,
        "cached": False,
        "elapsed_ms": 0.0,
        "trace": [
            {
                "name": "intent_classifier",
                "duration_ms": 0,
                "attributes": {"intent": intent},
                "events": [],
            }
        ],
        "trace_steps": [trace_step],
        "detected_entities": [],
        "suggested_questions": suggested_questions(3, summary),
        "warnings": [],
    }


async def _aiter_sync(gen: Iterator[Any]) -> AsyncIterator[Any]:
    """Adapt a blocking sync generator to an async iterator by advancing it one
    item per ``asyncio.to_thread`` call, so the event loop stays free to service
    other requests between yielded tokens."""
    sentinel = object()

    def _next() -> Any:
        try:
            return next(gen)
        except StopIteration:
            return sentinel

    while True:
        item = await asyncio.to_thread(_next)
        if item is sentinel:
            return
        yield item


def create_app() -> FastAPI:
    s = get_settings()
    configure_logging(level=s.log_level, json=s.log_json)
    s.ensure_dirs()
    if s.telemetry.enabled:
        init_telemetry(s.telemetry.service_name, s.telemetry.otlp_endpoint)

    app = FastAPI(
        title="Auralynq API",
        version=__version__,
        description="Talk to Your Data — agentic voice RAG with PathRAG.",
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=s.serve.cors_origins, allow_methods=["*"], allow_headers=["*"]
    )
    app.add_middleware(RateLimitMiddleware, limit_per_min=s.serve.rate_limit_per_min)
    app.add_middleware(AuthMiddleware, api_key=s.serve.api_key)
    app.add_exception_handler(AuralynqError, auralynq_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    @app.middleware("http")
    async def request_id_mw(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request.state.request_id = rid
        _METRICS["requests_total"] += 1
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        _METRICS["request_ms_total"] += int((time.perf_counter() - t0) * 1000)
        return response

    # ------------------------------------------------------------- health --
    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        snap = health_snapshot()
        try:
            from auralynq.vectorstore.factory import get_store

            snap["index"] = {"vectors": get_store().count()}
        except Exception:  # pragma: no cover
            snap["index"] = {"vectors": 0}
        return HealthResponse(**snap)

    @app.get("/version")
    async def version() -> JSONResponse:
        # Stable service identity for orchestration / compatibility checks.
        import platform

        return JSONResponse(
            {
                "name": "auralynq",
                "version": __version__,
                "api": "v1",
                "python": platform.python_version(),
                "env": get_settings().env,
            }
        )

    @app.get("/ready")
    async def ready() -> JSONResponse:
        # Readiness (vs /health liveness): is the index queryable yet? Returns 503
        # until at least one vector is indexed, so orchestrators don't route
        # traffic to an empty instance.
        try:
            from auralynq.vectorstore.factory import get_store

            n = get_store().count()
        except Exception:  # pragma: no cover
            n = 0
        ready = n > 0
        return JSONResponse(
            {"ready": ready, "vectors": n},
            status_code=200 if ready else 503,
        )

    @app.get("/metrics")
    async def metrics() -> JSONResponse:
        return JSONResponse(dict(_METRICS))

    # -------------------------------------------------- status / corpus ----
    @app.get("/status", response_model=StatusResponse)
    async def status() -> StatusResponse:
        from auralynq.serving.corpus import corpus_summary

        snap = health_snapshot()
        s = get_settings()
        try:
            from auralynq.vectorstore.factory import get_store

            vectors = get_store().count()
        except Exception:  # pragma: no cover
            vectors = 0
        from auralynq.telemetry.langfuse_export import langfuse_enabled

        return StatusResponse(
            status=snap["status"],
            version=snap["version"],
            env=snap["env"],
            providers=snap["providers"],
            index={"vectors": vectors},
            corpus=corpus_summary(),
            tracing={
                "provider": "langfuse+phoenix" if langfuse_enabled() else "in-process",
                "phoenix_endpoint": s.telemetry.phoenix_endpoint,
                "langfuse_host": s.telemetry.langfuse_host,
                "enabled": s.telemetry.enabled,
            },
            hf_space=s.hf_space,
            demo_mode=s.demo_mode,
            public_demo=s.public_demo,
            allow_uploads=s.allow_uploads,
        )

    @app.get("/corpus/summary", response_model=CorpusSummaryResponse)
    async def corpus_summary_ep() -> CorpusSummaryResponse:
        from auralynq.serving.corpus import corpus_summary

        return CorpusSummaryResponse(**corpus_summary())

    @app.get("/corpus/documents", response_model=CorpusDocumentsResponse)
    async def corpus_documents_ep() -> CorpusDocumentsResponse:
        # Indexed documents with ids/titles, for source-scoping the retrieval (#16).
        from auralynq.serving.corpus_manager import _all_indexed_documents

        docs = [
            CorpusDocument(
                doc_id=str(d.get("doc_id", "")),
                title=str(d.get("title", "")),
                source=str(d.get("source", "")),
                source_type=str(d.get("source_type", "")),
                chunks=int(d.get("chunks", 0) or 0),
            )
            for d in _all_indexed_documents()
            if d.get("doc_id")
        ]
        return CorpusDocumentsResponse(documents=docs)

    # ------------------------------------------------------- watch folder --
    @app.get("/watch/status", response_model=WatchStatusResponse)
    async def watch_status_ep() -> WatchStatusResponse:
        from auralynq.serving.watcher import watch_status

        return WatchStatusResponse(**watch_status())

    @app.post("/watch/sync", response_model=WatchSyncResponse)
    async def watch_sync_ep() -> WatchSyncResponse:
        # Manual trigger — reconcile the index with the watch folders now.
        from auralynq.serving.watcher import sync_once

        report = await asyncio.to_thread(sync_once)
        fields = WatchSyncResponse.model_fields
        return WatchSyncResponse(**{k: v for k, v in report.items() if k in fields})

    # ---------------------------------------------------- compounding wiki --
    @app.get("/wiki/entities", response_model=WikiPagesResponse)
    async def wiki_entities_ep(
        limit: int = 100, sort: str = "mentions"
    ) -> WikiPagesResponse:
        s = get_settings()
        if not s.wiki.enabled:
            return WikiPagesResponse(enabled=False, count=0, pages=[])
        from auralynq.wiki.store import WikiStore

        store = WikiStore(s.wiki_dir)
        pages = store.list_pages()
        key = "updated" if sort == "updated" else "mentions"
        pages.sort(key=lambda p: p.get(key, 0), reverse=True)
        summaries = [
            WikiPageSummary(
                id=p["id"],
                title=p.get("title", ""),
                type=p.get("type", "entity"),
                mentions=int(p.get("mentions", 0) or 0),
                updated=p.get("updated", ""),
                sources=p.get("sources", []) or [],
            )
            for p in pages[: max(1, limit)]
        ]
        return WikiPagesResponse(enabled=True, count=store.count(), pages=summaries)

    @app.get("/wiki/entity/{entity_id}", response_model=WikiPageResponse)
    async def wiki_entity_ep(entity_id: str) -> WikiPageResponse:
        s = get_settings()
        if not s.wiki.enabled:
            raise HTTPException(status_code=404, detail="wiki disabled")
        from auralynq.wiki.store import WikiStore

        page = WikiStore(s.wiki_dir).read_page(entity_id)
        if page is None:
            raise HTTPException(status_code=404, detail="wiki page not found")
        return WikiPageResponse(
            id=page["id"],
            title=page.get("title", ""),
            type=page.get("type", "entity"),
            mentions=int(page.get("mentions", 0) or 0),
            updated=page.get("updated", ""),
            sources=page.get("sources", []) or [],
            markdown=page.get("markdown", ""),
        )

    @app.get("/wiki/lint", response_model=WikiLintResponse)
    async def wiki_lint_ep() -> WikiLintResponse:
        # Health-check: flagged contradictions + orphan pages (#Phase 3).
        s = get_settings()
        if not s.wiki.enabled:
            return WikiLintResponse(enabled=False)
        from auralynq.wiki.store import WikiStore

        report = WikiStore(s.wiki_dir).lint()
        return WikiLintResponse(enabled=True, **report)

    # -------------------------------------------------- corpus management ---
    @app.get("/corpus/inventory", response_model=CorpusSummaryResponse)
    async def corpus_inventory_ep() -> CorpusSummaryResponse:
        from auralynq.serving.corpus import corpus_summary

        return CorpusSummaryResponse(**corpus_summary(use_cache=False))

    @app.post("/corpus/clear/preview", response_model=CorpusClearPreviewResponse)
    async def corpus_clear_preview_ep() -> CorpusClearPreviewResponse:
        from auralynq.serving.corpus_manager import corpus_clear_preview

        return CorpusClearPreviewResponse(**corpus_clear_preview())

    @app.post("/corpus/clear/confirm", response_model=CorpusDeleteReportResponse)
    async def corpus_clear_confirm_ep(req: CorpusClearConfirmRequest) -> CorpusDeleteReportResponse:
        from auralynq.serving.corpus_manager import corpus_clear_confirm

        try:
            report = await asyncio.to_thread(corpus_clear_confirm, req.phrase)
        except ValueError as e:
            raise AuralynqError("wrong_phrase", detail=str(e), status_code=400) from e
        return CorpusDeleteReportResponse(**report)

    @app.get("/corpus/documents/last/preview", response_model=CorpusDeleteDocumentPreviewResponse)
    async def corpus_delete_last_preview_ep() -> CorpusDeleteDocumentPreviewResponse:
        from auralynq.serving.corpus_manager import corpus_delete_last_preview

        return CorpusDeleteDocumentPreviewResponse(**corpus_delete_last_preview())

    @app.post("/corpus/documents/last/confirm", response_model=CorpusDeleteReportResponse)
    async def corpus_delete_last_confirm_ep(
        req: CorpusDeleteDocumentConfirmRequest,
    ) -> CorpusDeleteReportResponse:
        from auralynq.serving.corpus_manager import corpus_delete_last_confirm

        try:
            report = await asyncio.to_thread(corpus_delete_last_confirm, req.phrase)
        except ValueError as e:
            raise AuralynqError("wrong_phrase", detail=str(e), status_code=400) from e
        return CorpusDeleteReportResponse(**report)

    @app.get(
        "/corpus/documents/{doc_id}/preview",
        response_model=CorpusDeleteDocumentPreviewResponse,
    )
    async def corpus_delete_doc_preview_ep(doc_id: str) -> CorpusDeleteDocumentPreviewResponse:
        if not re.match(r"^[0-9a-f]{8,64}$", doc_id):
            raise AuralynqError("invalid_doc_id", status_code=400)
        from auralynq.serving.corpus_manager import corpus_delete_document_preview

        return CorpusDeleteDocumentPreviewResponse(**corpus_delete_document_preview(doc_id))

    @app.post("/corpus/documents/{doc_id}/confirm", response_model=CorpusDeleteReportResponse)
    async def corpus_delete_doc_confirm_ep(
        doc_id: str, req: CorpusDeleteDocumentConfirmRequest
    ) -> CorpusDeleteReportResponse:
        if not re.match(r"^[0-9a-f]{8,64}$", doc_id):
            raise AuralynqError("invalid_doc_id", status_code=400)
        from auralynq.serving.corpus_manager import corpus_delete_document_confirm

        try:
            report = await asyncio.to_thread(corpus_delete_document_confirm, doc_id, req.phrase)
        except ValueError as e:
            raise AuralynqError("wrong_phrase", detail=str(e), status_code=400) from e
        return CorpusDeleteReportResponse(**report)

    @app.get("/suggestions", response_model=SuggestionsResponse)
    async def suggestions_ep(limit: int = 4) -> SuggestionsResponse:
        from auralynq.serving.corpus import corpus_summary, suggested_questions

        summary = corpus_summary()
        return SuggestionsResponse(
            suggestions=suggested_questions(max(1, min(limit, 8)), summary),
            corpus_indexed=bool(summary.get("indexed")),
        )

    @app.get("/observability/summary", response_model=ObservabilitySummaryResponse)
    async def observability_summary() -> ObservabilitySummaryResponse:
        from auralynq.telemetry.langfuse_export import langfuse_enabled

        s = get_settings()
        reqs = _METRICS.get("requests_total", 0)
        total_ms = _METRICS.get("request_ms_total", 0)
        return ObservabilitySummaryResponse(
            requests_total=reqs,
            query_total=_METRICS.get("query_total", 0) + _METRICS.get("query_stream_total", 0),
            avg_request_ms=round(total_ms / reqs, 2) if reqs else 0.0,
            tracing_provider="langfuse+phoenix" if langfuse_enabled() else "in-process",
            phoenix_url=s.telemetry.phoenix_endpoint or None,
            langfuse_host=s.telemetry.langfuse_host or None,
        )

    # ------------------------------------------------------------- query ---
    @app.post("/query", response_model=QueryResponse)
    async def query(req: QueryRequest, request: Request) -> QueryResponse:
        _METRICS["query_total"] += 1
        intent = _classify_corpus_intent(req.question)
        if intent:
            data = await asyncio.to_thread(_system_answer_for_intent, intent, req.question)
            data["selected_rag_strategy"] = "system"
            return QueryResponse(request_id=request.state.request_id, **data)

        from auralynq.rag import get_registry

        strategy_id = req.rag_strategy or "auralynq_rag"
        registry = get_registry()
        result = await asyncio.to_thread(
            registry.run,
            strategy_id,
            req.question,
            final_k=req.final_k,
            use_cache=req.use_cache if req.use_cache is not None else True,
            route_hint=req.route_hint or "",
        )
        d = {
            "answer": result.answer,
            "status": result.status,
            "citations": result.citations,
            "route": result.route,
            "route_confidence": result.route_confidence,
            "route_rationale": result.route_rationale,
            "path_evidence": result.path_evidence,
            "seeds": result.seeds,
            "iterations": result.iterations,
            "confidence": result.confidence,
            "confidence_signals": getattr(result, "confidence_signals", {}),
            "evidence_coverage": result.evidence_coverage,
            "cached": result.cached,
            "elapsed_ms": result.elapsed_ms,
            "trace": result.trace,
            "trace_steps": result.trace_steps,
            "detected_entities": result.detected_entities,
            "suggested_questions": result.suggested_questions,
            "warnings": result.warnings + (result.strategy_warnings or []),
            "selected_rag_strategy": result.fallback_strategy or strategy_id,
            "fallback_strategy": result.fallback_strategy,
            "fallback_reason": result.fallback_reason,
            "strategy_warnings": result.strategy_warnings or [],
            "model_fit": getattr(result, "model_fit", None),
        }
        try:
            _last_eval.clear()
            _last_eval.update(
                {
                    "strategy": result.fallback_strategy or strategy_id,
                    "requested_strategy": strategy_id,
                    "fallback_strategy": result.fallback_strategy,
                    "route": result.route,
                    "confidence": result.confidence,
                    "evidence_coverage": result.evidence_coverage,
                    "citations": len(result.citations or []),
                    "elapsed_ms": result.elapsed_ms,
                    "status": result.status,
                    "warnings": result.warnings + (result.strategy_warnings or []),
                }
            )
        except Exception:
            pass
        return QueryResponse(request_id=request.state.request_id, **d)

    @app.post("/query/stream")
    async def query_stream(req: QueryRequest, request: Request) -> EventSourceResponse:
        _METRICS["query_stream_total"] += 1
        intent = _classify_corpus_intent(req.question)
        requested_strategy_id = req.rag_strategy or "auralynq_rag"

        async def event_gen():
            if intent:
                data = await asyncio.to_thread(_system_answer_for_intent, intent, req.question)
                yield {
                    "event": "meta",
                    "data": json.dumps(
                        {
                            "type": "meta",
                            "route": intent,
                            "confidence": 1.0,
                            "rationale": f"retrieval skipped: {intent}",
                            "seeds": [],
                            "path_evidence": [],
                            "selected_rag_strategy": "system",
                        }
                    ),
                }
                yield {
                    "event": "final",
                    "data": json.dumps(
                        {
                            "type": "final",
                            **data,
                            "selected_rag_strategy": "system",
                        }
                    ),
                }
                return

            from auralynq.agent.runner import stream_answer_question
            from auralynq.rag import get_registry

            registry = get_registry()

            # Resolve effective strategy and fallback metadata without running yet.
            effective_id = requested_strategy_id
            fallback_strategy: str | None = None
            fallback_reason: str | None = None
            strategy_warnings: list[str] = []

            strategy = registry.get(requested_strategy_id)
            if strategy is None:
                effective_id = "auralynq_rag"
                fallback_strategy = "auralynq_rag"
                fallback_reason = f"unknown_strategy: {requested_strategy_id}"
                strategy_warnings.append(
                    f"Unknown strategy '{requested_strategy_id}', fell back to auralynq_rag."
                )
            else:
                available, reason = strategy.is_available()
                if not available:
                    effective_id = "auralynq_rag"
                    fallback_strategy = "auralynq_rag"
                    fallback_reason = reason
                    strategy_warnings.append(
                        f"Strategy '{requested_strategy_id}' unavailable: {reason}. "
                        "Fell back to auralynq_rag."
                    )

            if effective_id == "auralynq_rag":
                # Full token-streaming path via the agentic runner. Optional
                # source scoping: restrict retrieval to selected documents (#16).
                _filt = Filter(doc_ids=req.doc_ids) if req.doc_ids else None
                gen = stream_answer_question(req.question, final_k=req.final_k, filt=_filt)
                async for event in _aiter_sync(gen):
                    if await request.is_disconnected():
                        close = getattr(gen, "close", None)
                        if close is not None:
                            close()
                        break
                    if event.get("type") == "meta":
                        event["selected_rag_strategy"] = effective_id
                        event["fallback_strategy"] = fallback_strategy
                        event["fallback_reason"] = fallback_reason
                    elif event.get("type") == "final":
                        event["selected_rag_strategy"] = effective_id
                        event["fallback_strategy"] = fallback_strategy
                        event["fallback_reason"] = fallback_reason
                        event["strategy_warnings"] = strategy_warnings
                        # Resolve visual grounding for the auralynq_rag streaming path.
                        try:
                            from auralynq.grounding.resolver import GroundingResolver

                            _gr = GroundingResolver()
                            _gr_results = _gr.resolve(
                                answer_id=str(id(event)),
                                answer=event.get("answer", ""),
                                citations=event.get("citations", []),
                            )
                            event["visual_grounding"] = (
                                _gr.to_api_response(_gr_results) if _gr_results else None
                            )
                        except Exception:
                            event["visual_grounding"] = None
                        try:
                            _last_eval.clear()
                            _last_eval.update(
                                {
                                    "strategy": effective_id,
                                    "requested_strategy": requested_strategy_id,
                                    "fallback_strategy": fallback_strategy,
                                    "route": event.get("route"),
                                    "confidence": event.get("confidence"),
                                    "evidence_coverage": event.get("evidence_coverage"),
                                    "citations": len(event.get("citations", [])),
                                    "elapsed_ms": event.get("elapsed_ms"),
                                    "status": event.get("status"),
                                    "warnings": strategy_warnings,
                                }
                            )
                        except Exception:
                            pass
                    yield {"event": event["type"], "data": json.dumps(event)}
            else:
                # Non-auralynq_rag strategy: run blocking, emit meta + final.
                result = await asyncio.to_thread(
                    registry.run,
                    effective_id,
                    req.question,
                    fallback_allowed=False,
                    force_strategy=True,
                    final_k=req.final_k,
                    use_cache=req.use_cache if req.use_cache is not None else True,
                    route_hint=req.route_hint or "",
                )
                combined_warnings = strategy_warnings + (result.strategy_warnings or [])
                yield {
                    "event": "meta",
                    "data": json.dumps(
                        {
                            "type": "meta",
                            "route": result.route or "auto",
                            "confidence": result.route_confidence or 0.0,
                            "rationale": result.route_rationale or "",
                            "seeds": result.seeds or [],
                            "path_evidence": result.path_evidence or [],
                            "selected_rag_strategy": effective_id,
                            "fallback_strategy": None,
                            "fallback_reason": None,
                        }
                    ),
                }
                try:
                    _last_eval.clear()
                    _last_eval.update(
                        {
                            "strategy": effective_id,
                            "requested_strategy": requested_strategy_id,
                            "fallback_strategy": None,
                            "route": result.route,
                            "confidence": result.confidence,
                            "evidence_coverage": result.evidence_coverage,
                            "citations": len(result.citations or []),
                            "elapsed_ms": result.elapsed_ms,
                            "status": result.status,
                            "warnings": combined_warnings,
                        }
                    )
                except Exception:
                    pass
                # Compute visual grounding for non-streaming strategies
                _vg_data = None
                try:
                    from auralynq.grounding.resolver import GroundingResolver

                    _gr = GroundingResolver()
                    _gr_results = _gr.resolve(
                        answer_id=str(request.state.request_id),
                        answer=result.answer,
                        citations=result.citations or [],
                    )
                    _vg_data = _gr.to_api_response(_gr_results)
                except Exception:
                    pass

                yield {
                    "event": "final",
                    "data": json.dumps(
                        {
                            "type": "final",
                            "answer": result.answer,
                            "status": result.status,
                            "citations": result.citations or [],
                            "confidence": result.confidence,
                            "evidence_coverage": result.evidence_coverage,
                            "elapsed_ms": result.elapsed_ms,
                            "trace": result.trace or [],
                            "trace_steps": result.trace_steps or [],
                            "detected_entities": [],
                            "suggested_questions": [],
                            "warnings": combined_warnings,
                            "strategy_warnings": combined_warnings,
                            "selected_rag_strategy": effective_id,
                            "fallback_strategy": None,
                            "fallback_reason": None,
                            "visual_grounding": _vg_data,
                        }
                    ),
                }

        return EventSourceResponse(event_gen())

    # ------------------------------------------------------------ ingest ---
    @app.post("/ingest", response_model=IngestResponse)
    async def ingest(request: Request, file: UploadFile = File(...)) -> IngestResponse:
        s = get_settings()
        if not s.allow_uploads:
            raise AuralynqError(
                "uploads_disabled",
                detail="Document uploads are disabled on this deployment "
                "(AURALYNQ_ALLOW_UPLOADS=false).",
                status_code=403,
            )
        from auralynq.ingest.pipeline import SUPPORTED_EXTENSIONS

        safe = _SAFE_NAME.sub("_", Path(file.filename or "upload.bin").name)
        if Path(safe).suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise AuralynqError(
                "unsupported_file_type",
                detail=(
                    f"'{Path(safe).suffix or '(no extension)'}' isn't a supported document "
                    f"type. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}."
                ),
                status_code=415,
            )
        inbox = s.storage_dir / "uploads"
        inbox.mkdir(parents=True, exist_ok=True)
        dest = inbox / safe
        size = 0
        limit = s.serve.max_upload_mb * 1024 * 1024
        with dest.open("wb") as fh:
            while chunk := await file.read(1 << 20):
                size += len(chunk)
                if size > limit:
                    dest.unlink(missing_ok=True)
                    raise AuralynqError(
                        "file_too_large", detail=f"max {s.serve.max_upload_mb} MB", status_code=413
                    )
                fh.write(chunk)
        from auralynq.pipeline import build_index
        from auralynq.serving.corpus import invalidate_corpus_cache

        try:
            stats = build_index(inbox, rebuild=False)
        finally:
            # Remove the raw upload after indexing; only embeddings are retained.
            dest.unlink(missing_ok=True)
        invalidate_corpus_cache()  # refresh corpus stats/suggestions immediately
        _METRICS["ingest_total"] += 1
        return IngestResponse(
            documents=stats["documents"],
            chunks=stats["chunks_indexed"],
            skipped=stats["skipped"],
            request_id=request.state.request_id,
        )

    # ------------------------------------------------------------- voice ---
    @app.post("/voice", response_model=VoiceResponse)
    async def voice(request: Request, file: UploadFile = File(...)) -> VoiceResponse:
        s = get_settings()
        safe = _SAFE_NAME.sub("_", Path(file.filename or "audio.wav").name)
        tmp = s.storage_dir / "voice_in"
        tmp.mkdir(parents=True, exist_ok=True)
        dest = tmp / safe
        # Stream with the same per-upload size cap as /ingest so a large audio
        # file cannot exhaust memory or disk before we even start ASR.
        size = 0
        limit = s.serve.max_upload_mb * 1024 * 1024
        try:
            with dest.open("wb") as fh:
                while chunk := await file.read(1 << 20):
                    size += len(chunk)
                    if size > limit:
                        dest.unlink(missing_ok=True)
                        raise AuralynqError(
                            "file_too_large",
                            detail=f"max {s.serve.max_upload_mb} MB",
                            status_code=413,
                        )
                    fh.write(chunk)
            from auralynq.voice.loop import run_voice_turn

            res = run_voice_turn(audio_path=dest, speak=True)
        finally:
            # Securely unlink the transient audio buffer regardless of outcome.
            dest.unlink(missing_ok=True)
        _METRICS["voice_total"] += 1
        audio_url = "/voice/audio" if res.audio_out_path else None
        return VoiceResponse(
            transcript=res.transcript,
            answer=res.answer,
            citations=res.citations,
            route=res.route,
            audio_out_url=audio_url,
            asr_provider=res.asr_provider,
            tts_provider=res.tts_provider,
            request_id=request.state.request_id,
        )

    @app.get("/voice/audio")
    async def voice_audio() -> FileResponse:
        out = get_settings().storage_dir / "tts_out.wav"
        if not out.exists():
            raise AuralynqError("no_audio", status_code=404)
        return FileResponse(str(out), media_type="audio/wav")

    @app.websocket("/ws/voice")
    async def ws_voice(ws: WebSocket) -> None:
        await ws.accept()
        s = get_settings()
        tmp = s.storage_dir / "ws_voice"
        tmp.mkdir(parents=True, exist_ok=True)
        buffer = bytearray()
        ws_limit = s.serve.max_upload_mb * 1024 * 1024
        try:
            while True:
                msg = await ws.receive()
                if msg.get("bytes") is not None:
                    if len(buffer) + len(msg["bytes"]) > ws_limit:
                        await ws.send_json(
                            {
                                "type": "error",
                                "detail": f"buffer exceeds {s.serve.max_upload_mb} MB",
                            }
                        )
                        buffer.clear()
                        continue
                    buffer += msg["bytes"]
                    await ws.send_json({"type": "ack", "bytes": len(buffer)})
                elif msg.get("text") is not None:
                    ctrl = json.loads(msg["text"])
                    if ctrl.get("action") == "end":
                        dest = tmp / f"{uuid.uuid4().hex[:8]}.wav"
                        try:
                            dest.write_bytes(bytes(buffer) or _silence())
                            from auralynq.voice.loop import run_voice_turn

                            res = run_voice_turn(audio_path=dest, speak=False)
                        finally:
                            dest.unlink(missing_ok=True)
                        await ws.send_json({"type": "transcript", "text": res.transcript})
                        await ws.send_json(
                            {
                                "type": "final",
                                "answer": res.answer,
                                "citations": res.citations,
                                "route": res.route,
                            }
                        )
                        buffer.clear()
                    elif ctrl.get("action") == "reset":
                        buffer.clear()
        except (WebSocketDisconnect, RuntimeError):  # client closed
            return

    # --------------------------------------------------------- RAG strategies ---
    @app.get("/rag/strategies", response_model=RAGStrategiesResponse)
    async def rag_strategies_ep() -> RAGStrategiesResponse:
        from auralynq.rag import get_registry

        registry = get_registry()
        strategies_raw = registry.list_all()
        from auralynq.serving.schemas import RAGStrategyInfo

        return RAGStrategiesResponse(
            strategies=[RAGStrategyInfo(**s) for s in strategies_raw],
            default_strategy=registry.default_strategy_id,
        )

    # v2 query endpoint with strategy selection
    @app.post("/query/v2", response_model=QueryResponse)
    async def query_v2(req: QueryRequestV2, request: Request) -> QueryResponse:
        _METRICS["query_total"] += 1
        intent = _classify_corpus_intent(req.question)
        if intent:
            data = await asyncio.to_thread(_system_answer_for_intent, intent, req.question)
            data["selected_rag_strategy"] = "system"
            data["requested_rag_strategy"] = req.rag_strategy
            return QueryResponse(request_id=request.state.request_id, **data)

        strategy_id = req.rag_strategy or "auralynq_rag"
        from auralynq.rag import get_registry

        registry = get_registry()
        result = await asyncio.to_thread(
            registry.run,
            strategy_id,
            req.question,
            fallback_allowed=req.fallback_allowed,
            force_strategy=req.force_strategy,
            final_k=req.final_k,
            use_cache=req.use_cache if req.use_cache is not None else True,
            route_hint=req.route_hint or "",
        )
        # Build visual grounding for the response
        vg_data = None
        try:
            from auralynq.grounding.resolver import GroundingResolver

            _gresolver = GroundingResolver()
            _gresults = _gresolver.resolve(
                answer_id=request.state.request_id,
                answer=result.answer,
                citations=result.citations,
            )
            vg_data = _gresolver.to_api_response(_gresults)
        except Exception:
            pass

        data = {
            "answer": result.answer,
            "status": result.status,
            "citations": result.citations,
            "route": result.route,
            "route_confidence": result.route_confidence,
            "route_rationale": result.route_rationale,
            "path_evidence": result.path_evidence,
            "seeds": result.seeds,
            "iterations": result.iterations,
            "confidence": result.confidence,
            "evidence_coverage": result.evidence_coverage,
            "cached": result.cached,
            "elapsed_ms": result.elapsed_ms,
            "trace": result.trace,
            "trace_steps": result.trace_steps,
            "detected_entities": result.detected_entities,
            "suggested_questions": result.suggested_questions,
            "warnings": result.warnings + (result.strategy_warnings or []),
            "selected_rag_strategy": result.strategy_id,
            "fallback_strategy": result.fallback_strategy,
            "fallback_reason": result.fallback_reason,
            "strategy_warnings": result.strategy_warnings or [],
            "visual_grounding": vg_data,
            "model_fit": getattr(result, "model_fit", None),
        }
        return QueryResponse(request_id=request.state.request_id, **data)

    # -------------------------------------------------------------- eval ---
    # In-memory last-run eval store (resets on restart — ephemeral by design)
    _last_eval: dict = {}
    _eval_feedback: list[dict] = []

    @app.get("/eval/last")
    async def eval_last() -> JSONResponse:
        if not _last_eval:
            return JSONResponse({"status": "pending", "detail": "No query has been run yet."})
        return JSONResponse(_last_eval)

    @app.get("/eval/summary")
    async def eval_summary() -> JSONResponse:
        if not _eval_feedback:
            return JSONResponse(
                {"total_feedback": 0, "avg_rating": None, "citation_correct_rate": None}
            )
        ratings = [f["answer_rating"] for f in _eval_feedback if f.get("answer_rating")]
        citations = [
            f["citation_correct"] for f in _eval_feedback if f.get("citation_correct") is not None
        ]
        return JSONResponse(
            {
                "total_feedback": len(_eval_feedback),
                "avg_rating": sum(ratings) / len(ratings) if ratings else None,
                "citation_correct_rate": sum(citations) / len(citations) if citations else None,
            }
        )

    @app.post("/eval/feedback")
    async def eval_feedback(req: EvalFeedbackRequest) -> JSONResponse:
        entry = req.model_dump()
        _eval_feedback.append(entry)
        return JSONResponse({"status": "recorded", "total": len(_eval_feedback)})

    @app.post("/eval/export-run")
    async def eval_export_run() -> JSONResponse:
        return JSONResponse({"last_eval": _last_eval, "feedback": _eval_feedback[-10:]})

    _eval_running = False  # simple mutex — one eval at a time

    @app.post("/eval/run")
    async def eval_run_ep(background_tasks: BackgroundTasks) -> JSONResponse:
        """Start an async eval run. Returns immediately; poll GET /eval/report for results."""
        nonlocal _eval_running
        if _eval_running:
            return JSONResponse({"status": "running", "detail": "Eval already in progress."})

        s = get_settings()
        from auralynq.agent.runner import answer_question

        # Collect candidate questions
        suggest_path = s.storage_dir / "suggestions_cache.json"
        questions: list[str] = []
        if suggest_path.exists():
            with contextlib.suppress(Exception):
                questions = json.loads(suggest_path.read_text(encoding="utf-8"))[:3]
        if not questions:
            doc_meta = _doc_store()
            for meta in list(doc_meta.values())[:3]:
                title = meta.get("title", "")
                if title:
                    questions.append(f"Summarise the key points from {title}.")
        if not questions:
            return JSONResponse(
                {"status": "error", "detail": "No corpus content to evaluate."}, status_code=400
            )

        # Write "running" sentinel so the frontend can show a spinner
        try:
            s.reports_dir.mkdir(parents=True, exist_ok=True)
            (s.reports_dir / "eval_report.json").write_text(
                json.dumps({"status": "running", "n_questions": len(questions[:3])}),
                encoding="utf-8",
            )
        except Exception:
            pass

        async def _run():
            nonlocal _eval_running
            _eval_running = True
            results: list[dict[str, Any]] = []
            for q in questions[:3]:
                try:
                    r = await asyncio.to_thread(answer_question, q)
                    results.append(
                        {
                            "question": q,
                            "status": r.status,
                            "citations": len(r.citations or []),
                            "confidence": r.confidence,
                            "evidence_coverage": r.evidence_coverage,
                            "elapsed_ms": r.elapsed_ms,
                        }
                    )
                except Exception as exc:
                    results.append({"question": q, "status": "error", "error": str(exc)})
            answered = [r for r in results if r.get("status") == "answered"]
            n = len(answered) or 1
            report = {
                "status": "ok",
                "n_questions": len(questions[:3]),
                "n_answered": len(answered),
                "citation_rate": round(sum(1 for r in answered if r["citations"] > 0) / n, 3),
                "avg_confidence": round(sum(r["confidence"] for r in answered) / n, 3),
                "avg_evidence_coverage": round(
                    sum(r["evidence_coverage"] for r in answered) / n, 3
                ),
                "avg_latency_ms": round(sum(r["elapsed_ms"] for r in answered) / n, 1),
                "abstention_rate": round(
                    sum(1 for r in results if r.get("status") == "insufficient_evidence")
                    / len(results),
                    3,
                ),
                "per_question": results,
                "feedback_summary": {
                    "total": len(_eval_feedback),
                    "avg_rating": (
                        round(
                            sum(
                                f["answer_rating"] for f in _eval_feedback if f.get("answer_rating")
                            )
                            / max(1, sum(1 for f in _eval_feedback if f.get("answer_rating"))),
                            2,
                        )
                        if _eval_feedback
                        else None
                    ),
                },
            }
            with contextlib.suppress(Exception):
                (s.reports_dir / "eval_report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )
            _eval_running = False

        background_tasks.add_task(_run)
        return JSONResponse({"status": "running", "n_questions": len(questions[:3])})

    @app.get("/eval/report")
    async def eval_report() -> JSONResponse:
        path = get_settings().reports_dir / "eval_report.json"
        if not path.exists():
            return JSONResponse(
                {"status": "pending", "detail": "run `make eval` to generate a report"}
            )
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))

    @app.get("/bench/report")
    async def bench_report() -> JSONResponse:
        path = get_settings().reports_dir / "bench_report.json"
        if not path.exists():
            return JSONResponse({"status": "pending", "detail": "run `make bench`"})
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))

    # ------------------------------------------ visual grounding endpoints ---

    def _doc_store() -> dict[str, dict]:
        """Load document metadata from ingest manifest + storage.

        Returns doc_id → {title, source_type, page_dimensions, visual_grounding_version, n_pages}.
        """
        s = get_settings()
        doc_meta_path = s.storage_dir / "doc_meta.json"
        if doc_meta_path.exists():
            try:
                return json.loads(doc_meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    @app.get("/documents/{doc_id}/pages", response_model=DocumentPagesResponse)
    async def document_pages(doc_id: str) -> DocumentPagesResponse:
        """List pages and their metadata for a document."""
        s = get_settings()
        doc_store = _doc_store()
        meta = doc_store.get(doc_id, {})
        page_dims: list[dict] = meta.get("page_dimensions", [])
        n_pages = meta.get("n_pages", len(page_dims))
        vg_version = meta.get("visual_grounding_version", 0)
        from auralynq.ingest.models import VISUAL_GROUNDING_VERSION as _VGV

        reindex_required = vg_version < _VGV

        pages_info: list[PageInfo] = []
        for pd in page_dims:
            pg = pd.get("page", 0)
            img_path = s.page_cache_dir / doc_id / f"page_{pg:04d}.png"
            has_img = img_path.exists()
            pages_info.append(
                PageInfo(
                    page=pg,
                    width=pd.get("width", 0.0),
                    height=pd.get("height", 0.0),
                    image_url=f"/documents/{doc_id}/pages/{pg}/image" if has_img else "",
                    has_image=has_img,
                )
            )

        return DocumentPagesResponse(
            doc_id=doc_id,
            source_title=meta.get("title", ""),
            source_type=meta.get("source_type", "unknown"),
            n_pages=n_pages,
            pages=pages_info,
            visual_grounding_version=vg_version,
            reindex_required=reindex_required,
        )

    @app.get("/documents/{doc_id}/pages/{page_number}/image")
    async def document_page_image(doc_id: str, page_number: int) -> FileResponse:
        """Serve a rendered page image (PNG). Only serves files in the page cache."""
        s = get_settings()
        # Validate doc_id: only alphanumeric + _ - (safe subset of stable_id output)
        if not re.match(r"^[a-f0-9]{8,64}$", doc_id):
            return JSONResponse({"error": "Invalid document ID"}, status_code=400)  # type: ignore[return-value]
        if page_number < 1 or page_number > 9999:
            return JSONResponse({"error": "Invalid page number"}, status_code=400)  # type: ignore[return-value]
        img_path = s.page_cache_dir / doc_id / f"page_{page_number:04d}.png"
        if not img_path.exists():
            return JSONResponse(
                {
                    "error": "Page image not available",
                    "detail": "Reindex the document to generate page images",
                },
                status_code=404,
            )  # type: ignore[return-value]
        # Security: ensure the resolved path is inside page_cache_dir
        try:
            img_path.resolve().relative_to(s.page_cache_dir.resolve())
        except ValueError:
            return JSONResponse({"error": "Access denied"}, status_code=403)  # type: ignore[return-value]
        return FileResponse(str(img_path), media_type="image/png")

    @app.post("/documents/{doc_id}/render-pages")
    async def document_render_pages(doc_id: str, file: UploadFile = File(...)) -> JSONResponse:
        """Render page images for an existing document from a re-uploaded PDF.

        Does NOT re-index; only populates the page cache so Source View can
        show page images for a document whose pages were never rendered.
        """
        s = get_settings()
        if not re.match(r"^[a-f0-9]{8,64}$", doc_id):
            return JSONResponse({"error": "Invalid document ID"}, status_code=400)
        if not s.visual.page_rendering_enabled:
            return JSONResponse({"error": "Page rendering is disabled"}, status_code=400)
        # Save to a temp location in the uploads dir
        inbox = s.storage_dir / "uploads"
        inbox.mkdir(parents=True, exist_ok=True)
        safe = _SAFE_NAME.sub("_", Path(file.filename or "upload.pdf").name)
        dest = inbox / f"_rerender_{doc_id}_{safe}"
        try:
            with dest.open("wb") as fh:
                while chunk := await file.read(1 << 20):
                    fh.write(chunk)
            from auralynq.ingest.models import SourceType
            from auralynq.ingest.pipeline import _render_page_images

            _render_page_images(dest, doc_id, SourceType.pdf)
            cache_dir = s.page_cache_dir / doc_id
            n_cached = len(list(cache_dir.glob("page_*.png"))) if cache_dir.exists() else 0
            return JSONResponse({"doc_id": doc_id, "pages_rendered": n_cached, "status": "ok"})
        finally:
            dest.unlink(missing_ok=True)

    @app.get("/documents/{doc_id}/grounding-status", response_model=DocumentGroundingStatusResponse)
    async def document_grounding_status(doc_id: str) -> DocumentGroundingStatusResponse:
        """Return visual grounding status for a document."""
        s = get_settings()
        doc_store = _doc_store()
        meta = doc_store.get(doc_id, {})
        vg_version = meta.get("visual_grounding_version", 0)
        from auralynq.ingest.models import VISUAL_GROUNDING_VERSION as _VGV

        reindex_required = vg_version < _VGV
        cache_dir = s.page_cache_dir / doc_id
        n_cached = len(list(cache_dir.glob("page_*.png"))) if cache_dir.exists() else 0
        return DocumentGroundingStatusResponse(
            doc_id=doc_id,
            source_title=meta.get("title", ""),
            visual_grounding_version=vg_version,
            reindex_required=reindex_required,
            grounding_available=not reindex_required and n_cached > 0,
            n_pages=meta.get("n_pages", 0),
            n_chunks_with_bbox=meta.get("n_chunks_with_bbox", 0),
            page_images_cached=n_cached,
        )

    @app.get("/corpus/grounding-summary")
    async def corpus_grounding_summary_ep() -> JSONResponse:
        """Return visual grounding statistics for the whole corpus."""
        s = get_settings()
        doc_store = _doc_store()
        from auralynq.ingest.models import VISUAL_GROUNDING_VERSION as _VGV

        total = len(doc_store)
        grounded = sum(
            1 for m in doc_store.values() if m.get("visual_grounding_version", 0) >= _VGV
        )
        return JSONResponse(
            {
                "enabled": s.visual.enabled,
                "page_rendering_enabled": s.visual.page_rendering_enabled,
                "total_docs": total,
                "grounded_docs": grounded,
                "needs_reindex": total - grounded,
                "visual_grounding_version": _VGV,
            }
        )

    @app.get("/documents/{doc_id}/pages/{page_number}/layout", response_model=PageLayoutResponse)
    async def document_page_layout(doc_id: str, page_number: int) -> PageLayoutResponse:
        """Return layout blocks (chunks with bbox) for a specific page.

        Scrolls the vector store for chunks belonging to doc_id, filters by page,
        and returns them as positioned layout blocks for the Source Workspace.
        """
        if not re.match(r"^[a-f0-9]{8,64}$", doc_id):
            return JSONResponse({"error": "Invalid document ID"}, status_code=400)  # type: ignore[return-value]
        if page_number < 1 or page_number > 9999:
            return JSONResponse({"error": "Invalid page number"}, status_code=400)  # type: ignore[return-value]

        doc_store = _doc_store()
        meta = doc_store.get(doc_id, {})
        source_title = meta.get("title", "")
        page_dims = meta.get("page_dimensions", [])
        page_dim: dict[str, Any] = next((d for d in page_dims if d.get("page") == page_number), {})
        page_w = float(page_dim.get("width", 0.0))
        page_h = float(page_dim.get("height", 0.0))

        # Scroll vector store for chunks of this document, filter by page
        blocks: list[PageLayoutBlock] = []
        try:
            from qdrant_client import models as qm

            from auralynq.vectorstore.qdrant_store import QdrantStore

            vs = QdrantStore()
            if vs._exists():
                offset: Any = None
                seen_chunk_ids: set[str] = set()
                while True:
                    pts, offset = vs.client.scroll(
                        vs.collection,
                        scroll_filter=qm.Filter(
                            must=[
                                qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=doc_id))
                            ]
                        ),
                        limit=256,
                        with_payload=True,
                        with_vectors=False,
                        offset=offset,
                    )
                    if not pts:
                        break
                    for pt in pts:
                        pl = pt.payload or {}
                        chunk_id = str(pl.get("id", ""))
                        if chunk_id in seen_chunk_ids:
                            continue
                        seen_chunk_ids.add(chunk_id)
                        meta_field = pl.get("metadata") or {}
                        vg = meta_field.get("visual_grounding") or {}
                        if vg.get("page") != page_number:
                            continue
                        raw_bbox = vg.get("bbox") or []
                        raw_nbbox = vg.get("normalized_bbox") or []
                        blocks.append(
                            PageLayoutBlock(
                                block_id=chunk_id,
                                page=page_number,
                                bbox=raw_bbox if isinstance(raw_bbox, list) else [],
                                normalized_bbox=raw_nbbox if isinstance(raw_nbbox, list) else [],
                                text=str(pl.get("text", ""))[:400],
                                block_type=str(vg.get("block_type", "paragraph")),
                                chunk_id=chunk_id,
                                relevance=0.0,
                                confidence=float(vg.get("confidence", 1.0)),
                                is_cited=False,
                                citation_ids=[],
                            )
                        )
                    if offset is None:
                        break
        except Exception:
            pass  # best-effort; return empty blocks on error

        # Sort top-to-bottom by normalized y position
        blocks.sort(key=lambda b: b.normalized_bbox[1] if len(b.normalized_bbox) > 1 else 0.0)

        return PageLayoutResponse(
            doc_id=doc_id,
            page=page_number,
            blocks=blocks,
            source_title=source_title,
            page_width=page_w,
            page_height=page_h,
        )

    @app.get("/visual-grounding/settings")
    async def visual_grounding_settings_ep() -> JSONResponse:
        """Return visual grounding configuration."""
        s = get_settings()
        return JSONResponse(
            {
                "enabled": s.visual.enabled,
                "page_rendering_enabled": s.visual.page_rendering_enabled,
                "render_dpi": s.visual.render_dpi,
                "max_cached_pages": s.visual.max_cached_pages,
                "visual_retrieval_enabled": s.visual.visual_retrieval_enabled,
                "visual_retrieval_provider": s.visual.visual_retrieval_provider,
                "metadata_version": s.visual.metadata_version,
            }
        )

    # ─────────────────────────────────────────── ModelFit Index ──────────────
    if s.modelfit.enabled:
        try:
            from auralynq.modelfit.router import router as modelfit_router

            app.include_router(modelfit_router)
        except Exception:
            pass  # ModelFit is optional — degrade gracefully if deps missing

    return app


def _silence(seconds: float = 0.5, sr: int = 16_000) -> bytes:
    import wave
    from io import BytesIO

    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(b"\x00\x00" * int(sr * seconds))
    return buf.getvalue()


app = create_app()
