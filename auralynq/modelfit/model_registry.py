"""Model registry for Auralynq ModelFit Index.

Merges static catalog entries (Ollama, HF) with live Ollama API data and
local GGUF file discovery. Provides search, filter, and lookup APIs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from auralynq.modelfit.hf_catalog import get_static_hf_catalog
from auralynq.modelfit.model_metadata import ModelMetadata
from auralynq.modelfit.ollama_catalog import get_static_catalog, list_installed_models

_GGUF_FAMILY_HINTS: dict[str, str] = {
    "qwen": "qwen",
    "llama": "llama",
    "mistral": "mistral",
    "gemma": "gemma",
    "phi": "phi",
    "deepseek": "deepseek",
}

_GGUF_PARAM_HINTS: dict[str, float] = {
    "0.5b": 0.5,
    "1b": 1.0,
    "1.5b": 1.5,
    "3b": 3.0,
    "7b": 7.0,
    "8b": 8.0,
    "14b": 14.0,
    "32b": 32.0,
    "70b": 70.0,
}


def _make_slm_entry() -> ModelMetadata | None:
    """Build a ModelMetadata for the configured SLM GGUF. Returns None on import error."""
    try:
        from auralynq.config.settings import get_settings

        s = get_settings()
        slug = s.llm.slm_filename.replace(".gguf", "").lower()
        model_id = f"local:{slug}"

        # Infer family from filename
        family: str = "unknown"
        for hint, fam in _GGUF_FAMILY_HINTS.items():
            if hint in slug:
                family = fam
                break

        # Infer parameter count from filename  (e.g. "0.5b", "7b")
        params_b: float | None = None
        for hint, size in _GGUF_PARAM_HINTS.items():
            if hint in slug:
                params_b = size
                break

        return ModelMetadata(
            model_id=model_id,
            source="local",
            display_name=slug,
            family=family,  # type: ignore[arg-type]
            parameter_count_b=params_b,
            context_length=s.llm.slm_n_ctx,
            license="unknown",
            tasks=["chat", "rag"],
            hf_repo=s.llm.slm_repo,
            notes=[f"SLM GGUF via llama-cpp-python — {s.llm.slm_filename}"],
        )
    except Exception:
        return None


def _discover_local_gguf(search_dirs: list[str] | None = None) -> list[ModelMetadata]:
    """Scan common directories for local GGUF files (read-only, no downloads)."""
    dirs = search_dirs or [
        str(Path.home() / ".ollama" / "models"),
        str(Path.home() / ".cache" / "lm-studio" / "models"),
        str(Path.home() / "models"),
        "/models",
    ]
    found: list[ModelMetadata] = []
    for d in dirs:
        p = Path(d)
        if not p.exists():
            continue
        for gguf in p.rglob("*.gguf"):
            rel = gguf.stem
            size_gb = round(gguf.stat().st_size / (1024**3), 1)
            found.append(
                ModelMetadata(
                    model_id=f"local:{gguf}",
                    source="local",
                    display_name=rel,
                    family="unknown",
                    local_path=str(gguf),
                    notes=[f"Local GGUF file — {size_gb} GB on disk."],
                )
            )
    return found


class ModelRegistry:
    """Central registry of all known models, supporting search and filtering."""

    def __init__(self) -> None:
        self._models: dict[str, ModelMetadata] = {}
        self._loaded_live: bool = False

        # Seed with static catalogs immediately (offline-safe)
        for m in get_static_catalog():
            self._models[m.model_id] = m
        for m in get_static_hf_catalog():
            self._models[m.model_id] = m
        for m in _discover_local_gguf():
            self._models[m.model_id] = m

        # Register the configured SLM model so ModelFit can score it
        slm = _make_slm_entry()
        if slm is not None:
            self._models.setdefault(slm.model_id, slm)

    async def refresh_from_ollama(self) -> list[str]:
        """Sync live-installed Ollama models into the registry. Returns warnings."""
        models, warnings = await list_installed_models()
        for m in models:
            # Live data overrides static catalog entries for the same tag
            self._models[m.model_id] = m
            # Mark as locally available
            if m.notes and "installed" not in m.notes[0]:
                m.notes.insert(0, "Locally installed in Ollama.")
        self._loaded_live = True
        return warnings

    def get(self, model_id: str) -> ModelMetadata | None:
        return self._models.get(model_id)

    def list_all(self) -> list[ModelMetadata]:
        return list(self._models.values())

    def search(
        self,
        query: str = "",
        source: str | None = None,
        family: str | None = None,
        min_params_b: float | None = None,
        max_params_b: float | None = None,
        task: str | None = None,
        embedding_only: bool = False,
        reranker_only: bool = False,
        vision: bool | None = None,
        tool_calling: bool | None = None,
        open_license: bool = False,
        supports_adapters: bool | None = None,
        limit: int = 50,
    ) -> list[ModelMetadata]:
        results = list(self._models.values())

        if query:
            q = query.lower()
            results = [
                m
                for m in results
                if q in m.model_id.lower() or q in m.display_name.lower() or q in m.family.lower()
            ]
        if source:
            results = [m for m in results if m.source == source]
        if family:
            results = [m for m in results if m.family == family]
        if min_params_b is not None:
            results = [
                m
                for m in results
                if m.parameter_count_b is not None and m.parameter_count_b >= min_params_b
            ]
        if max_params_b is not None:
            results = [
                m
                for m in results
                if m.parameter_count_b is not None and m.parameter_count_b <= max_params_b
            ]
        if task:
            results = [m for m in results if task in m.tasks]
        if embedding_only:
            results = [m for m in results if m.embedding]
        if reranker_only:
            results = [m for m in results if m.reranker]
        if vision is not None:
            results = [m for m in results if m.vision == vision]
        if tool_calling is not None:
            results = [m for m in results if m.tool_calling == tool_calling]
        if open_license:
            open_licenses = {"apache-2.0", "mit", "apache 2.0"}
            results = [
                m
                for m in results
                if m.license.lower().replace(" ", "-") in open_licenses
                or m.license.lower() in open_licenses
            ]
        if supports_adapters is not None:
            results = [m for m in results if m.supports_adapters == supports_adapters]

        return results[:limit]

    def to_dict_list(self, models: list[ModelMetadata] | None = None) -> list[dict[str, Any]]:
        items = models if models is not None else self.list_all()
        return [m.to_dict() for m in items]


# Module-level singleton — shared across request lifecycle
_registry: ModelRegistry | None = None


def get_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
