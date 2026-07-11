"""Pydantic request/response schemas for the FastAPI backend."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    final_k: int | None = Field(default=None, ge=1, le=50)
    use_cache: bool | None = None
    route_hint: str | None = Field(
        default=None,
        description="Override the adaptive router: 'fast' | 'hybrid' | 'graph' | 'auto'.",
    )
    rag_strategy: str | None = Field(
        default=None,
        description="RAG strategy id from /api/rag/strategies. Defaults to auralynq_rag.",
    )
    doc_ids: list[str] | None = Field(
        default=None,
        description="Restrict retrieval to these document ids (source scoping). "
        "None or empty = search the whole corpus.",
    )


class Citation(BaseModel):
    marker: int
    source: str
    locator: str = ""
    source_type: str = "unknown"
    speaker: str | None = None
    start_s: float | None = None
    end_s: float | None = None
    page: int | None = None
    score: float | None = None  # retrieval score (0-1) — evidence quality signal
    method: str | None = None  # retrieval method: "hybrid" | "pathrag" | …


class QueryResponse(BaseModel):
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
    # Per-signal breakdown for UI ConfidenceBar (paper §4.3, Eq. 6)
    confidence_signals: dict[str, float] = Field(default_factory=dict)
    evidence_coverage: float = 0.0
    cached: bool = False
    elapsed_ms: float = 0.0
    trace: list[dict[str, Any]] = Field(default_factory=list)
    trace_steps: list[dict[str, Any]] = Field(default_factory=list)
    detected_entities: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    insufficient_evidence_reason: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    provider_status: list[dict[str, str]] = Field(default_factory=list)
    request_id: str = ""
    selected_rag_strategy: str | None = None
    fallback_strategy: str | None = None
    fallback_reason: str | None = None
    strategy_warnings: list[str] = Field(default_factory=list)
    # Visual grounding
    visual_grounding: dict[str, Any] | None = None
    # ModelFit — model selection metadata (None when not local-model-aware)
    model_fit: dict[str, Any] | None = None


class CorpusSummaryResponse(BaseModel):
    indexed: bool = False
    indexed_document_count: int = 0
    vector_count: int = 0
    document_titles: list[str] = Field(default_factory=list)
    source_types: dict[str, int] = Field(default_factory=dict)
    top_entities: list[dict[str, Any]] = Field(default_factory=list)
    entity_count: int = 0
    last_indexed: str | None = None
    last_document_title: str | None = None
    languages: list[str] = Field(default_factory=list)
    failed_files: list[str] = Field(default_factory=list)


class CorpusDocument(BaseModel):
    doc_id: str
    title: str
    source: str = ""
    source_type: str = ""
    chunks: int = 0


class CorpusDocumentsResponse(BaseModel):
    documents: list[CorpusDocument] = Field(default_factory=list)


class WatchDirStatus(BaseModel):
    path: str
    exists: bool = False
    files: int = 0


class WatchStatusResponse(BaseModel):
    enabled: bool = False
    poll_seconds: float = 10.0
    recursive: bool = True
    delete_missing: bool = True
    tracked: int = 0
    directories: list[WatchDirStatus] = Field(default_factory=list)


class WatchSyncResponse(BaseModel):
    enabled: bool = False
    added: int = 0
    updated: int = 0
    removed: int = 0
    reindexed: bool = False
    chunks_indexed: int = 0
    errors: list[str] = Field(default_factory=list)


class WikiPageSummary(BaseModel):
    id: str
    title: str = ""
    type: str = "entity"
    mentions: int = 0
    updated: str = ""
    sources: list[str] = Field(default_factory=list)


class WikiPagesResponse(BaseModel):
    enabled: bool = False
    count: int = 0
    pages: list[WikiPageSummary] = Field(default_factory=list)


class WikiPageResponse(BaseModel):
    id: str
    title: str = ""
    type: str = "entity"
    mentions: int = 0
    updated: str = ""
    sources: list[str] = Field(default_factory=list)
    markdown: str = ""


class WikiLintResponse(BaseModel):
    enabled: bool = False
    pages: int = 0
    contradiction_count: int = 0
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    orphan_pages: list[str] = Field(default_factory=list)


class SuggestionsResponse(BaseModel):
    suggestions: list[str] = Field(default_factory=list)
    corpus_indexed: bool = False


class StatusResponse(BaseModel):
    status: str = "ok"
    version: str = ""
    env: str = ""
    providers: list[dict[str, str]] = Field(default_factory=list)
    index: dict[str, Any] = Field(default_factory=dict)
    corpus: dict[str, Any] = Field(default_factory=dict)
    tracing: dict[str, Any] = Field(default_factory=dict)
    hf_space: bool = False
    demo_mode: bool = False
    public_demo: bool = False
    allow_uploads: bool = True


class ObservabilitySummaryResponse(BaseModel):
    requests_total: int = 0
    query_total: int = 0
    avg_request_ms: float = 0.0
    tracing_provider: str = "in-process"
    phoenix_url: str | None = None
    langfuse_host: str | None = None


class IngestResponse(BaseModel):
    documents: int
    chunks: int
    skipped: int
    request_id: str = ""


class VoiceResponse(BaseModel):
    transcript: str
    answer: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    route: str = "fast"
    audio_out_url: str | None = None
    asr_provider: str = "null"
    tts_provider: str | None = None
    request_id: str = ""


class HealthResponse(BaseModel):
    status: str
    version: str
    env: str
    providers: list[dict[str, str]]
    hf_token_present: bool
    index: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: str
    detail: str = ""
    request_id: str = ""


# ---------------------------------------------------------------------- corpus management --
class CorpusClearPreviewResponse(BaseModel):
    action: str = "clear_all"
    document_count: int = 0
    vector_count: int = 0
    entity_count: int = 0
    files: list[str] = Field(default_factory=list)
    document_details: list[dict[str, Any]] = Field(default_factory=list)
    manifest_entries: int = 0
    graph_exists: bool = False
    confirmation_phrase: str = ""
    warning: str = ""


class CorpusClearConfirmRequest(BaseModel):
    phrase: str


class CorpusDeleteDocumentPreviewResponse(BaseModel):
    action: str = "delete_document"
    found: bool = False
    document: dict[str, Any] | None = None
    confirmation_phrase: str = ""
    warning: str = ""


class CorpusDeleteDocumentConfirmRequest(BaseModel):
    phrase: str


class CorpusDeleteReportResponse(BaseModel):
    action: str
    deleted: bool = False
    deleted_vectors: int = 0
    deleted_documents: int = 0
    deleted_entities: int = 0
    deleted_chunks: int = 0
    deleted_graph: bool = False
    deleted_manifest: bool = False
    deleted_last_ingested: bool = False
    manifest_updated: bool = False
    graph_rebuilt: bool = False
    last_ingested_updated: bool = False
    errors: list[str] = Field(default_factory=list)
    final_inventory: dict[str, Any] | None = None
    reason: str | None = None


# ---------------------------------------------------------------------- RAG strategies --
class RAGStrategyInfo(BaseModel):
    id: str
    name: str
    description: str
    status: str
    required_features: list[str] = Field(default_factory=list)
    supports_streaming: bool = True
    supports_graph: bool = False
    supports_rerank: bool = False
    supports_web: bool = False
    supports_abstention: bool = True
    expected_latency: str = "medium"
    best_for: str = ""
    limitations: str = ""
    available: bool = True
    unavailable_reason: str | None = None


class RAGStrategiesResponse(BaseModel):
    strategies: list[RAGStrategyInfo]
    default_strategy: str


# ---------------------------------------------------------------------- eval --
class EvalFeedbackRequest(BaseModel):
    query_id: str | None = None
    answer_rating: int | None = Field(default=None, ge=1, le=5)
    citation_correct: bool | None = None
    answer_supported: bool | None = None
    notes: str | None = None


class EvalRunExportRequest(BaseModel):
    query_id: str | None = None


# Extended query request with strategy selection
class QueryRequestV2(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    final_k: int | None = Field(default=None, ge=1, le=50)
    use_cache: bool | None = None
    route_hint: str | None = Field(
        default=None, description="Override route: 'fast' | 'hybrid' | 'graph' | 'auto'"
    )
    rag_strategy: str | None = Field(
        default=None, description="RAG strategy id from /api/rag/strategies"
    )
    force_strategy: bool = Field(
        default=False, description="Fail if strategy is unavailable (no fallback)"
    )
    fallback_allowed: bool = Field(default=True, description="Allow fallback to default strategy")


# ---------------------------------------------------------------------- visual grounding --
class PageInfo(BaseModel):
    page: int
    width: float = 0.0
    height: float = 0.0
    image_url: str = ""
    has_image: bool = False


class DocumentPagesResponse(BaseModel):
    doc_id: str
    source_title: str = ""
    source_type: str = "unknown"
    n_pages: int = 0
    pages: list[PageInfo] = Field(default_factory=list)
    visual_grounding_version: int = 0
    reindex_required: bool = False


class VisualGroundingResponse(BaseModel):
    answer_id: str
    highlights: list[dict[str, Any]] = Field(default_factory=list)
    claim_grounding: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    visual_grounding_available: bool = False
    grounding_stage: str = "unavailable"  # span | page | unavailable


class DocumentGroundingStatusResponse(BaseModel):
    doc_id: str
    source_title: str = ""
    visual_grounding_version: int = 0
    reindex_required: bool = True
    grounding_available: bool = False
    n_pages: int = 0
    n_chunks_with_bbox: int = 0
    page_images_cached: int = 0


class PageLayoutBlock(BaseModel):
    block_id: str = ""
    page: int = 1
    bbox: list[float] = Field(default_factory=list)
    normalized_bbox: list[float] = Field(default_factory=list)
    text: str = ""
    block_type: str = "paragraph"
    chunk_id: str = ""
    relevance: float = 0.0
    confidence: float = 1.0
    is_cited: bool = False
    citation_ids: list[str] = Field(default_factory=list)


class PageLayoutResponse(BaseModel):
    doc_id: str
    page: int
    blocks: list[PageLayoutBlock] = Field(default_factory=list)
    source_title: str = ""
    page_width: float = 0.0
    page_height: float = 0.0
