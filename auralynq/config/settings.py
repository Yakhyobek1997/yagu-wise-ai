"""Typed, env-driven configuration for Auralynq.

Precedence (highest → lowest):
  1. Environment variables  (``AURALYNQ_<GROUP>__<FIELD>``, double underscore)
  2. ``.env`` file          (auto-loaded from CWD)
  3. ``config.yaml``        (auto-discovered; override path via ``AURALYNQ_CONFIG``)
  4. Hard-coded defaults    (defined here)

Only ``HUGGINGFACE_TOKEN`` is ever required, and only for gated HF assets.
"""

from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

Provider = Literal["auto"]


class EmbeddingSettings(BaseSettings):
    provider: Literal["auto", "ollama", "bge", "hash", "openai"] = "auto"
    model: str = "BAAI/bge-m3"  # used when provider=bge
    ollama_model: str = "nomic-embed-text"  # used when provider=ollama
    dim: int = 768
    device: Literal["auto", "cpu", "cuda"] = "auto"
    batch_size: int = 16


class VectorSettings(BaseSettings):
    backend: Literal["auto", "qdrant", "chroma", "memory"] = "auto"
    url: str = "http://localhost:6333"
    collection: str = "auralynq"
    quantization: Literal["none", "scalar", "binary"] = "none"
    hnsw_m: int = 16
    # ChromaDB local-persistence settings
    chroma_persist_dir: Path = Path("./data/vectorstore")
    chroma_collection: str = "auralynq"


class RerankSettings(BaseSettings):
    provider: Literal["auto", "bge", "cohere", "none"] = "auto"
    model: str = "BAAI/bge-reranker-v2-m3"


class RetrievalSettings(BaseSettings):
    top_k: int = 20
    final_k: int = 6
    rrf_k: int = 60
    mmr_lambda: float = 0.6
    dense_weight: float = 0.6
    sparse_weight: float = 0.4


class LLMSettings(BaseSettings):
    provider: Literal[
        "auto", "ollama", "slm", "openai", "anthropic", "cohere", "huggingface", "extractive"
    ] = "auto"
    model: str = "llama3.2:3b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.1
    max_tokens: int = 1024
    # ── SLM (local GGUF via llama-cpp-python) ──────────────────────────────
    # HuggingFace repo and filename for the default GGUF model.  The file is
    # downloaded once to the HF Hub cache (~/.cache/huggingface/) and reused.
    # Qwen2.5-0.5B-Q4_K_M is ~350 MB and runs comfortably on CPU.
    slm_repo: str = "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
    slm_filename: str = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    slm_n_ctx: int = 4096
    # -1 = auto (GPU when CUDA present, CPU otherwise); 0 = force CPU; N = N layers on GPU
    slm_n_gpu_layers: int = -1


class AgentSettings(BaseSettings):
    max_iters: int = 3
    latency_budget_ms: int = 15_000
    semantic_cache: bool = True
    cache_threshold: float = 0.93


class VoiceSettings(BaseSettings):
    asr_provider: Literal["auto", "faster_whisper", "whisperx", "null"] = "auto"
    asr_model: str = "base"
    tts_provider: Literal["auto", "kokoro", "null"] = "auto"
    tts_voice: str = "af_heart"
    diarize: bool = True
    vad: bool = True
    sample_rate: int = 16_000


class ServeSettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    rate_limit_per_min: int = 120
    max_upload_mb: int = 50
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    # Optional bearer-token auth. Empty == open (local/demo). When set, all
    # endpoints except /health and /metrics require `Authorization: Bearer <key>`.
    api_key: str = ""


class TelemetrySettings(BaseSettings):
    enabled: bool = True
    phoenix_endpoint: str = "http://localhost:6006"
    otlp_endpoint: str = ""
    service_name: str = "auralynq"
    # Langfuse (optional hosted trace/eval). Activated when both LANGFUSE_* keys
    # are set; host defaults to Langfuse Cloud, override for self-hosted.
    langfuse_host: str = "https://cloud.langfuse.com"
    # Strip common PII patterns from trace inputs/outputs before export.
    # Set to false only if you have a legal basis to store raw user queries.
    pii_filter: bool = True


class ModelFitSettings(BaseSettings):
    enabled: bool = True


class VisualGroundingSettings(BaseSettings):
    enabled: bool = True
    # Render and cache PDF page images for source view overlay
    page_rendering_enabled: bool = True
    render_dpi: int = 144
    max_cached_pages: int = 500
    # Sub-dir under data_dir for page image cache
    page_cache_subdir: str = "page_cache"
    # Enable experimental ColPali-style visual retrieval
    visual_retrieval_enabled: bool = False
    visual_retrieval_provider: Literal["none", "colpali", "local_vlm"] = "none"
    # Grounding metadata schema version — bump when schema changes requiring reindex
    metadata_version: int = 1


class WikiSettings(BaseSettings):
    """Compounding Wiki layer (Phase 1) — persistent LLM-synthesized entity pages
    built from the knowledge graph at ingest. Off by default; purely additive."""

    enabled: bool = False
    # Synthesize/refresh pages automatically at the end of each ingest.
    auto_synthesize: bool = True
    # Only build a page for entities mentioned at least this many times (noise gate).
    min_mentions: int = 2
    # Flag factual contradictions between a page's prior claims and a new
    # synthesis at ingest (LLM-based; advisory — never auto-deletes).
    detect_contradictions: bool = True
    # File high-confidence answers back as wiki pages so explorations compound.
    file_answers: bool = True
    min_answer_confidence: float = 0.55
    # Cap pages generated per ingest (cost/latency guard); highest-mention first.
    max_entities: int = 150
    # Token budget per synthesized page.
    max_page_tokens: int = 1024
    # Character budget of source-chunk evidence fed into one page's synthesis.
    max_context_chars: int = 6000


class WatchSettings(BaseSettings):
    """Watch Folder — auto-reindex local directories on change. Off by default.

    The worker polls each configured directory; new and modified files are
    ingested incrementally (content-hash idempotent), and — when
    ``delete_missing`` is on — a document whose source file has disappeared is
    removed from the index and knowledge graph. Files are watched in place (they
    are never moved, unlike the ``inbox`` queue worker)."""

    enabled: bool = False
    #: Directories to watch. Relative paths resolve against ``data_dir``. When
    #: empty (and enabled), defaults to ``<data_dir>/watch``. Set via env as a
    #: JSON array, e.g. AURALYNQ_WATCH__DIRS='["/mnt/docs","reports"]'.
    dirs: list[str] = []
    #: Minimum seconds between folder scans (the worker never scans faster).
    poll_seconds: float = 10.0
    recursive: bool = True
    #: Remove a document from the index when its source file disappears.
    delete_missing: bool = True


class Settings(BaseSettings):
    """Root settings object. Instantiate via :func:`get_settings`."""

    model_config = SettingsConfigDict(
        env_prefix="AURALYNQ_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: Literal["local", "dev", "prod"] = "local"
    log_level: str = "INFO"
    log_json: bool = False
    data_dir: Path = Path("./data")
    reports_dir: Path = Path("./reports")
    seed: int = 42

    # Default PDF source directory (used by `auralynq ingest` with no argument)
    pdf_source_dir: Path = Path("./data/pdfs")

    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    vector: VectorSettings = Field(default_factory=VectorSettings)
    rerank: RerankSettings = Field(default_factory=RerankSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    serve: ServeSettings = Field(default_factory=ServeSettings)
    telemetry: TelemetrySettings = Field(default_factory=TelemetrySettings)
    visual: VisualGroundingSettings = Field(default_factory=VisualGroundingSettings)
    modelfit: ModelFitSettings = Field(default_factory=ModelFitSettings)
    wiki: WikiSettings = Field(default_factory=WikiSettings)
    watch: WatchSettings = Field(default_factory=WatchSettings)

    # When true, blocks all outbound calls to external LLM/embedding/telemetry
    # providers regardless of which API keys are set. Guarantees zero data
    # egress for strict air-gapped deployments. Env: AURALYNQ_AIR_GAPPED=true
    air_gapped: bool = False

    # Hugging Face Space / public-demo posture (see
    # docs/getting-started/huggingface-space.md). Purely informational except
    # for allow_uploads, which the /ingest endpoint enforces.
    hf_space: bool = False
    demo_mode: bool = False
    public_demo: bool = False
    allow_uploads: bool = True

    # Well-known secrets (not prefixed). Empty string == "not configured".
    huggingface_token: str = Field(default="", alias="HUGGINGFACE_TOKEN")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    cohere_api_key: str = Field(default="", alias="COHERE_API_KEY")
    langfuse_public_key: str = Field(default="", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", alias="LANGFUSE_SECRET_KEY")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        from auralynq.config.yaml_source import YamlConfigSettingsSource

        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )

    @property
    def index_dir(self) -> Path:
        return self.data_dir / "index"

    @property
    def storage_dir(self) -> Path:
        return self.data_dir / "storage"

    @property
    def page_cache_dir(self) -> Path:
        return self.data_dir / self.visual.page_cache_subdir

    @property
    def wiki_dir(self) -> Path:
        return self.storage_dir / "wiki_pages"

    @property
    def watch_dirs(self) -> list[Path]:
        """Resolved Watch Folder directories. Relative entries resolve against
        ``data_dir``; defaults to ``<data_dir>/watch`` when none configured."""
        raw = [Path(d) for d in self.watch.dirs] if self.watch.dirs else [self.data_dir / "watch"]
        return [d if d.is_absolute() else (self.data_dir / d) for d in raw]

    def ensure_dirs(self) -> None:
        for p in (self.data_dir, self.reports_dir, self.index_dir, self.storage_dir):
            p.mkdir(parents=True, exist_ok=True)
        self.pdf_source_dir.mkdir(parents=True, exist_ok=True)
        if self.visual.page_rendering_enabled:
            self.page_cache_dir.mkdir(parents=True, exist_ok=True)


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance (read once per process).

    Set ``AURALYNQ_DOTENV_DISABLED=1`` to skip reading a host ``.env`` entirely —
    used by the test suite so a populated server ``.env`` can't leak secrets/auth
    into deterministic offline tests.
    """
    if os.getenv("AURALYNQ_DOTENV_DISABLED") == "1":
        return Settings(_env_file=None)  # type: ignore[call-arg]
    return Settings()


def reload_settings() -> Settings:
    """Clear the cache and re-read settings (useful in tests)."""
    get_settings.cache_clear()
    return get_settings()
