"""End-to-end indexing pipeline: corpus → vector index + knowledge graph.

Ties together ingestion, embeddings, the vector store and the PathRAG knowledge
graph. Persists both indexes so retrieval/agent can run in a fresh process.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from auralynq.config import get_settings
from auralynq.embeddings.factory import get_embedder
from auralynq.ingest.models import Chunk, Document
from auralynq.ingest.pipeline import ingest_path
from auralynq.retrieval.pathrag.builder import build_from_chunks
from auralynq.retrieval.pathrag.graph import KnowledgeGraph
from auralynq.telemetry import get_logger
from auralynq.utils import chunked
from auralynq.vectorstore.factory import get_store
from auralynq.vectorstore.memory_store import MemoryStore

_log = get_logger("auralynq.pipeline")


def graph_path() -> Path:
    return get_settings().index_dir / "graph.json"


def build_index(input_dir: Path, rebuild: bool = False) -> dict[str, Any]:
    s = get_settings()
    s.ensure_dirs()
    store = get_store()
    embedder = get_embedder()

    if rebuild:
        store.clear()

    # Force a full ingest when the store is empty (e.g. the index dir was cleared
    # but the ingest manifest persisted) so the index is never left empty due to
    # a stale idempotency manifest.
    force = rebuild or store.count() == 0
    result = ingest_path(Path(input_dir), recursive=True, force=force)
    all_chunks: list[Chunk] = [c for d in result.documents for c in d.chunks]

    n_indexed = 0
    for batch in chunked(all_chunks, s.embedding.batch_size):
        emb = embedder.embed([c.text for c in batch])
        n_indexed += store.upsert(batch, emb)

    if isinstance(store, MemoryStore):
        store.save()

    # Rebuild the knowledge graph from the *full* indexed set (not just newly
    # ingested chunks) so an idempotent re-index never wipes the graph. Falls
    # back to this run's chunks if the store can't enumerate (e.g. remote Qdrant).
    kg_chunks = store.all_chunks() or all_chunks
    wiki_pages = 0
    if kg_chunks:
        kg = build_from_chunks(kg_chunks)
        kg.save(graph_path())
        # Compounding Wiki (Phase 1) — synthesize durable entity pages from the
        # fresh KG. Additive and gated; never blocks indexing on failure.
        if s.wiki.enabled and s.wiki.auto_synthesize:
            try:
                from auralynq.wiki.generator import synthesize_wiki

                wiki_pages = synthesize_wiki(kg, kg_chunks, settings=s)
            except Exception as e:  # pragma: no cover - non-fatal by design
                _log.warning("wiki.synthesis_failed", error=str(e))
    else:
        kg = load_graph()  # nothing to index and nothing stored; keep existing

    if result.documents:
        _write_last_ingested(s.index_dir, result.documents)
        _write_doc_meta(s.storage_dir, result.documents)

    stats = {
        "backend": store.backend,
        "embedder": embedder.name,
        "documents": result.n_documents,
        "skipped": result.n_skipped,
        "chunks_indexed": n_indexed,
        "store_count": store.count(),
        "entities": kg.n_entities,
        "relations": kg.n_relations,
    }
    if s.wiki.enabled:
        stats["wiki_pages"] = wiki_pages
    _log.info("index.built", **stats)
    return stats


def _write_last_ingested(index_dir: Path, docs: list[Document]) -> None:
    """Write last_ingested.json: the document with the newest source mtime."""
    import datetime as _dt

    newest_doc = docs[-1]  # default: last in ingestion order
    newest_mtime = 0.0
    for d in docs:
        try:
            mtime = Path(d.source).stat().st_mtime
            if mtime > newest_mtime:
                newest_mtime = mtime
                newest_doc = d
        except OSError:
            pass
    name = newest_doc.title or Path(newest_doc.source).name
    ts = (
        _dt.datetime.fromtimestamp(newest_mtime, tz=_dt.UTC).isoformat()
        if newest_mtime > 0
        else _dt.datetime.now(tz=_dt.UTC).isoformat()
    )
    try:
        sidecar = index_dir / "last_ingested.json"
        sidecar.write_text(
            json.dumps({"name": name, "source": newest_doc.source, "ingested_at": ts}),
            encoding="utf-8",
        )
    except Exception:
        pass


def _write_doc_meta(storage_dir: Path, docs: list[Document]) -> None:
    """Write/merge doc_meta.json — consumed by visual grounding endpoints."""
    import contextlib

    meta_path = storage_dir / "doc_meta.json"
    existing: dict[str, dict] = {}
    if meta_path.exists():
        with contextlib.suppress(Exception):
            existing = json.loads(meta_path.read_text(encoding="utf-8"))
    for doc in docs:
        existing[doc.id] = {
            "title": doc.title or Path(doc.source).name,
            "source": doc.source,
            "source_type": doc.source_type.value,
            "page_dimensions": doc.page_dimensions,
            "visual_grounding_version": doc.visual_grounding_version,
            "n_pages": len(doc.page_dimensions),
            "n_chunks": doc.n_chunks,
            "n_chunks_with_bbox": sum(
                1 for c in doc.chunks if (c.metadata.get("visual_grounding") or {}).get("has_bbox")
            ),
        }
    with contextlib.suppress(Exception):
        meta_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def load_graph() -> KnowledgeGraph:
    p = graph_path()
    if p.exists():
        return KnowledgeGraph.load(p)
    return KnowledgeGraph()
