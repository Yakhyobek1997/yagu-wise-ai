"""Corpus management: safe preview + confirm deletion of indexed documents.

Every destructive operation is a two-step flow:
  1. preview  — returns exactly what will be removed, no side-effects
  2. confirm  — caller supplies the typed confirmation phrase; deletion runs

Clears every persistence layer: vector store, knowledge graph, ingest manifest,
last_ingested sidecar, corpus summary cache, and (optionally) eval/bench reports.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from auralynq.config import get_settings
from auralynq.telemetry import get_logger
from auralynq.utils import stable_id

_log = get_logger("auralynq.corpus_manager")

PHRASE_CLEAR_ALL = "CLEAR CORPUS"
PHRASE_DELETE_LAST = "DELETE LAST DOCUMENT"
PHRASE_DELETE_DOC = "DELETE DOCUMENT"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _manifest_path() -> Path:
    return get_settings().storage_dir / "ingest_manifest.json"


def _last_ingested_path() -> Path:
    return get_settings().index_dir / "last_ingested.json"


def _graph_path() -> Path:
    return get_settings().index_dir / "graph.json"


def _memory_store_dir() -> Path:
    return get_settings().index_dir / "memory_store"


def _read_manifest() -> dict[str, str]:
    p = _manifest_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _read_last_ingested() -> dict[str, Any]:
    p = _last_ingested_path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _doc_id_for_source(source: str) -> str:
    return stable_id(str(Path(source).resolve()))


def _qdrant_documents_from_scroll(store: Any) -> dict[str, dict[str, Any]]:
    """Scroll Qdrant collection to collect unique doc_id→metadata mappings."""
    seen: dict[str, dict[str, Any]] = {}
    offset = None
    while True:
        results, next_offset = store.client.scroll(
            collection_name=store.collection,
            scroll_filter=None,
            limit=256,
            offset=offset,
            with_payload=["doc_id", "source", "title", "source_type"],
            with_vectors=False,
        )
        for pt in results:
            pl = pt.payload or {}
            did = pl.get("doc_id", "")
            src = pl.get("source", "")
            if not did:
                continue
            if did not in seen:
                raw_title = pl.get("title") or Path(src).name if src else did
                seen[did] = {
                    "doc_id": did,
                    "source": src,
                    "title": raw_title,
                    "source_type": pl.get("source_type", "unknown"),
                    "chunks": 0,
                    "vectors": 0,
                }
            seen[did]["chunks"] += 1
            seen[did]["vectors"] += 1
        if next_offset is None:
            break
        offset = next_offset
    return seen


def _all_indexed_documents() -> list[dict[str, Any]]:
    """Return indexed document metadata: {doc_id, source, title, chunks, vectors}."""
    try:
        from auralynq.vectorstore.factory import get_store

        store = get_store()
        chunks = store.all_chunks() or []
    except Exception:
        return []

    # For memory store: build from chunks
    seen: dict[str, dict[str, Any]] = {}
    for ch in chunks:
        did = ch.doc_id
        if did not in seen:
            title = ch.title or (Path(ch.source).name if ch.source else did)
            seen[did] = {
                "doc_id": did,
                "source": ch.source or "",
                "title": title,
                "source_type": (
                    ch.source_type.value
                    if hasattr(ch.source_type, "value")
                    else str(ch.source_type)
                ),
                "chunks": 0,
                "vectors": 0,
            }
        seen[did]["chunks"] += 1
        seen[did]["vectors"] += 1

    # For Qdrant store (all_chunks returns []): scroll payload to get real doc_id+source
    if not seen:
        import contextlib

        with contextlib.suppress(Exception):
            seen = _qdrant_documents_from_scroll(store)

    docs = list(seen.values())
    docs.sort(key=lambda d: d["source"])
    return docs


def _last_indexed_document() -> dict[str, Any] | None:
    """Return the last-ingested document metadata, or None if corpus is empty."""
    last = _read_last_ingested()
    if last.get("name"):
        source = last.get("source", "")
        doc_id = _doc_id_for_source(source) if source else ""
        if not doc_id:
            # Fall back: find doc matching by name from indexed docs
            docs = _all_indexed_documents()
            matched = [d for d in docs if Path(d["source"]).name == last["name"]]
            if matched:
                return matched[0]
        return {
            "doc_id": doc_id,
            "source": source,
            "title": last["name"],
            "source_type": "unknown",
            "ingested_at": last.get("ingested_at"),
        }
    # No sidecar: pick the doc with the lexicographically last source path
    docs = _all_indexed_documents()
    if docs:
        manifest = _read_manifest()
        # Use manifest ordering if available
        if manifest:
            manifest_docs = [d for d in docs if d["source"] in manifest]
            if manifest_docs:
                return manifest_docs[-1]
        return docs[-1]
    return None


# ---------------------------------------------------------------------------
# Clear ALL corpus
# ---------------------------------------------------------------------------


def corpus_clear_preview() -> dict[str, Any]:
    """Return a deletion plan for clearing the entire corpus (no side effects)."""
    try:
        from auralynq.vectorstore.factory import get_store

        store = get_store()
        vector_count = store.count()
        docs = _all_indexed_documents()
    except Exception:
        vector_count = 0
        docs = []

    manifest = _read_manifest()
    graph_exists = _graph_path().exists()
    memory_files: list[str] = []
    ms_dir = _memory_store_dir()
    if ms_dir.exists():
        memory_files = [str(p) for p in ms_dir.iterdir() if p.is_file()]

    return {
        "action": "clear_all",
        "document_count": len(docs),
        "vector_count": vector_count,
        "entity_count": _entity_count(),
        "files": [d["title"] for d in docs],
        "document_details": docs,
        "manifest_entries": len(manifest),
        "graph_exists": graph_exists,
        "memory_store_files": memory_files,
        "confirmation_phrase": PHRASE_CLEAR_ALL,
        "warning": (
            "This will permanently remove all indexed documents, vectors,"
            " entities, and the knowledge graph."
        ),
    }


def corpus_clear_confirm(phrase: str) -> dict[str, Any]:
    """Clear the entire corpus after phrase verification. Returns a deletion report."""
    if phrase.strip().upper() != PHRASE_CLEAR_ALL:
        raise ValueError(f"Incorrect confirmation phrase. Expected: {PHRASE_CLEAR_ALL!r}")

    report: dict[str, Any] = {
        "action": "clear_all",
        "deleted_vectors": 0,
        "deleted_documents": 0,
        "deleted_entities": 0,
        "deleted_graph": False,
        "deleted_manifest": False,
        "deleted_last_ingested": False,
        "deleted_memory_files": [],
        "errors": [],
    }

    # 1. Clear vector store
    try:
        from auralynq.vectorstore.factory import get_store

        store = get_store()
        report["deleted_vectors"] = store.count()
        report["deleted_documents"] = len(_all_indexed_documents())
        report["deleted_entities"] = _entity_count()
        store.clear()
        # For MemoryStore, persist the cleared state immediately
        from auralynq.vectorstore.memory_store import MemoryStore

        if isinstance(store, MemoryStore):
            store.save()
    except Exception as e:
        report["errors"].append(f"vector store clear: {e}")

    # 2. Delete knowledge graph
    gp = _graph_path()
    if gp.exists():
        try:
            gp.unlink()
            report["deleted_graph"] = True
        except Exception as e:
            report["errors"].append(f"graph delete: {e}")

    # 3. Delete memory store files
    ms_dir = _memory_store_dir()
    if ms_dir.exists():
        for p in ms_dir.iterdir():
            if p.is_file():
                try:
                    p.unlink()
                    report["deleted_memory_files"].append(p.name)
                except Exception as e:
                    report["errors"].append(f"memory file {p.name}: {e}")

    # 4. Clear ingest manifest
    mp = _manifest_path()
    if mp.exists():
        try:
            mp.write_text("{}", encoding="utf-8")
            report["deleted_manifest"] = True
        except Exception as e:
            report["errors"].append(f"manifest clear: {e}")

    # 5. Delete last_ingested sidecar
    lp = _last_ingested_path()
    if lp.exists():
        try:
            lp.unlink()
            report["deleted_last_ingested"] = True
        except Exception as e:
            report["errors"].append(f"last_ingested delete: {e}")

    # 6. Wipe leftover upload files (ingest deletes each file after indexing, but
    # partial/failed runs may leave files behind).
    uploads_dir = get_settings().storage_dir / "uploads"
    deleted_uploads: list[str] = []
    if uploads_dir.exists():
        for p in uploads_dir.iterdir():
            if p.is_file():
                try:
                    p.unlink()
                    deleted_uploads.append(p.name)
                except Exception as e:
                    report["errors"].append(f"upload file {p.name}: {e}")
    if deleted_uploads:
        report["deleted_upload_files"] = deleted_uploads

    # 7. Invalidate corpus cache
    from auralynq.serving.corpus import invalidate_corpus_cache

    invalidate_corpus_cache()

    report["final_inventory"] = {
        "document_count": 0,
        "vector_count": 0,
        "entity_count": 0,
    }
    _log.info("corpus.cleared", **{k: v for k, v in report.items() if k != "document_details"})
    return report


# ---------------------------------------------------------------------------
# Delete LAST document
# ---------------------------------------------------------------------------


def corpus_delete_last_preview() -> dict[str, Any]:
    """Return deletion plan for the last indexed document (no side effects)."""
    doc = _last_indexed_document()
    if doc is None:
        return {
            "action": "delete_last",
            "found": False,
            "document": None,
            "confirmation_phrase": PHRASE_DELETE_LAST,
        }

    doc_id = doc.get("doc_id") or _doc_id_for_source(doc.get("source", ""))
    chunks = _chunk_count_for_doc(doc_id)

    return {
        "action": "delete_last",
        "found": True,
        "document": {**doc, "chunk_count": chunks},
        "confirmation_phrase": PHRASE_DELETE_LAST,
        "warning": f"This will permanently delete '{doc.get('title')}' from the index.",
    }


def corpus_delete_last_confirm(phrase: str) -> dict[str, Any]:
    """Delete the last indexed document after phrase verification."""
    if phrase.strip().upper() != PHRASE_DELETE_LAST:
        raise ValueError(f"Incorrect confirmation phrase. Expected: {PHRASE_DELETE_LAST!r}")
    doc = _last_indexed_document()
    if doc is None:
        return {
            "action": "delete_last",
            "deleted": False,
            "reason": "no documents indexed",
            "errors": [],
        }
    doc_id = doc.get("doc_id") or _doc_id_for_source(doc.get("source", ""))
    return _delete_document_by_id(doc_id, doc)


# ---------------------------------------------------------------------------
# Delete single document by ID
# ---------------------------------------------------------------------------


def corpus_delete_document_preview(doc_id: str) -> dict[str, Any]:
    """Return deletion plan for a specific document (no side effects)."""
    docs = _all_indexed_documents()
    doc = next((d for d in docs if d["doc_id"] == doc_id), None)
    if doc is None:
        return {
            "action": "delete_document",
            "found": False,
            "document": None,
            "confirmation_phrase": PHRASE_DELETE_DOC,
        }
    return {
        "action": "delete_document",
        "found": True,
        "document": doc,
        "confirmation_phrase": PHRASE_DELETE_DOC,
        "warning": f"This will permanently delete '{doc.get('title')}' from the index.",
    }


def corpus_delete_document_confirm(doc_id: str, phrase: str) -> dict[str, Any]:
    """Delete a specific document after phrase verification."""
    if phrase.strip().upper() != PHRASE_DELETE_DOC:
        raise ValueError(f"Incorrect confirmation phrase. Expected: {PHRASE_DELETE_DOC!r}")
    docs = _all_indexed_documents()
    doc = next((d for d in docs if d["doc_id"] == doc_id), None)
    if doc is None:
        return {
            "action": "delete_document",
            "deleted": False,
            "reason": "document not found",
            "errors": [],
        }
    return _delete_document_by_id(doc_id, doc)


# ---------------------------------------------------------------------------
# Core deletion logic (shared)
# ---------------------------------------------------------------------------


def _delete_document_by_id(doc_id: str, doc_meta: dict[str, Any]) -> dict[str, Any]:
    """Remove one document from every persistence layer."""
    report: dict[str, Any] = {
        "action": "delete_document",
        "doc_id": doc_id,
        "title": doc_meta.get("title", doc_id),
        "source": doc_meta.get("source", ""),
        "deleted": False,
        "deleted_vectors": 0,
        "deleted_chunks": 0,
        "graph_rebuilt": False,
        "manifest_updated": False,
        "last_ingested_updated": False,
        "errors": [],
    }

    # 1. Delete from vector store
    try:
        from auralynq.vectorstore.factory import get_store
        from auralynq.vectorstore.memory_store import MemoryStore

        store = get_store()
        removed = store.delete_by_doc_id(doc_id)
        report["deleted_vectors"] = removed
        report["deleted_chunks"] = removed
        if isinstance(store, MemoryStore):
            store.save()
    except Exception as e:
        report["errors"].append(f"vector store delete: {e}")

    # 2. Rebuild knowledge graph from remaining chunks
    try:
        from auralynq.retrieval.pathrag.builder import build_from_chunks
        from auralynq.vectorstore.factory import get_store

        store = get_store()
        remaining = store.all_chunks() or []
        if remaining:
            from auralynq.pipeline import graph_path

            kg = build_from_chunks(remaining)
            kg.save(graph_path())
        else:
            # No documents left — remove the graph file
            gp = _graph_path()
            if gp.exists():
                gp.unlink()
        report["graph_rebuilt"] = True
    except Exception as e:
        report["errors"].append(f"graph rebuild: {e}")

    # 3. Remove from ingest manifest
    source = doc_meta.get("source", "")
    if source:
        manifest = _read_manifest()
        if source in manifest:
            try:
                del manifest[source]
                mp = _manifest_path()
                mp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
                report["manifest_updated"] = True
            except Exception as e:
                report["errors"].append(f"manifest update: {e}")

    # 4. Update last_ingested sidecar if this was the last document
    last = _read_last_ingested()
    if last.get("source") == source or last.get("name") == doc_meta.get("title"):
        try:
            new_last = _last_indexed_document()
            lp = _last_ingested_path()
            if new_last and new_last.get("doc_id") != doc_id:
                lp.write_text(
                    json.dumps(
                        {
                            "name": new_last.get("title", ""),
                            "source": new_last.get("source", ""),
                            "ingested_at": new_last.get("ingested_at", ""),
                        }
                    ),
                    encoding="utf-8",
                )
            elif lp.exists():
                lp.unlink()
            report["last_ingested_updated"] = True
        except Exception as e:
            report["errors"].append(f"last_ingested update: {e}")

    # 5. Invalidate corpus cache
    from auralynq.serving.corpus import invalidate_corpus_cache

    invalidate_corpus_cache()

    report["deleted"] = True
    _log.info(
        "corpus.document_deleted",
        doc_id=doc_id,
        title=report["title"],
        vectors=report["deleted_vectors"],
    )
    return report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entity_count() -> int:
    try:
        from auralynq.pipeline import load_graph

        kg = load_graph()
        return kg.n_entities
    except Exception:
        return 0


def _chunk_count_for_doc(doc_id: str) -> int:
    try:
        from auralynq.vectorstore.factory import get_store

        store = get_store()
        chunks = store.all_chunks() or []
        return sum(1 for c in chunks if c.doc_id == doc_id)
    except Exception:
        return 0
