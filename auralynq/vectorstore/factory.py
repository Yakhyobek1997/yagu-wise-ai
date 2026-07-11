"""Vector store factory with ``auto`` resolution.

Auto-resolution priority (highest → lowest):
  qdrant (if server reachable) → chroma (if chromadb installed) → memory
"""

from __future__ import annotations

import functools
import importlib.util

from auralynq.config import get_settings
from auralynq.telemetry import get_logger
from auralynq.vectorstore.base import VectorStore
from auralynq.vectorstore.memory_store import MemoryStore

_log = get_logger("auralynq.vectorstore")


def _have(pkg: str) -> bool:
    return importlib.util.find_spec(pkg) is not None


def build_store(backend: str | None = None) -> VectorStore:
    s = get_settings()
    backend = backend or s.vector.backend

    if backend == "auto":
        if _qdrant_reachable():
            backend = "qdrant"
        elif _have("chromadb"):
            backend = "chroma"
        else:
            backend = "memory"

    if backend == "qdrant":
        try:
            from auralynq.vectorstore.qdrant_store import QdrantStore

            return QdrantStore(quantization=s.vector.quantization)
        except Exception as exc:  # pragma: no cover - server/lib absent
            _log.warning("vectorstore.qdrant_failed_fallback_chroma", error=str(exc))
            backend = "chroma" if _have("chromadb") else "memory"

    if backend == "chroma":
        try:
            from auralynq.vectorstore.chroma_store import ChromaStore

            return ChromaStore(
                persist_dir=s.vector.chroma_persist_dir,
                collection=s.vector.chroma_collection,
            )
        except Exception as exc:
            _log.warning("vectorstore.chroma_failed_fallback_memory", error=str(exc))

    _log.info("vectorstore.using", backend="memory")
    return MemoryStore()


def _qdrant_reachable() -> bool:
    if not _have("qdrant_client"):
        return False
    s = get_settings()
    try:  # pragma: no cover - network probe
        import httpx

        httpx.get(s.vector.url + "/readyz", timeout=0.5)
        return True
    except Exception:
        return False


@functools.lru_cache(maxsize=1)
def get_store() -> VectorStore:
    return build_store()


def resolved_backend() -> str:
    s = get_settings()
    if s.vector.backend != "auto":
        return s.vector.backend
    if _qdrant_reachable():
        return "qdrant"
    if _have("chromadb"):
        return "chroma"
    return "memory"
