"""Watch Folder — incremental auto-reindex of local directories.

Unlike the ``inbox`` queue worker (which *moves* files after ingesting), the
Watch Folder keeps files in place and keeps the index in sync with whatever is
on disk. The worker calls :func:`sync_once` each cycle:

* **added / modified** files → ingested via the idempotent pipeline
  (:func:`auralynq.pipeline.build_index`, content-hash deduped).
* **removed** files → the corresponding document is deleted from the vector
  store and the knowledge graph is rebuilt (when ``delete_missing`` is on).

A cheap ``watch_state.json`` snapshot of ``(mtime, size)`` per file lets us skip
re-parsing unchanged trees — a full ``build_index`` only runs when something
actually changed, so idle polling costs a few ``stat`` calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from auralynq.config import get_settings
from auralynq.ingest.pipeline import SUPPORTED_EXTENSIONS
from auralynq.telemetry import get_logger

_log = get_logger("auralynq.watch")


def _state_path() -> Path:
    return get_settings().storage_dir / "watch_state.json"


def _load_state() -> dict[str, dict[str, float]]:
    p = _state_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # corrupt snapshot → treat as empty, resync
            return {}
    return {}


def _save_state(state: dict[str, dict[str, float]]) -> None:
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _is_supported(p: Path) -> bool:
    return (
        p.suffix.lower() in SUPPORTED_EXTENSIONS
        and not p.name.endswith(".transcript.json")
    )


def scan(dirs: list[Path], recursive: bool = True) -> dict[str, dict[str, float]]:
    """Snapshot supported files under ``dirs`` → ``{path: {mtime, size}}``."""
    seen: dict[str, dict[str, float]] = {}
    for d in dirs:
        if not d.exists() or not d.is_dir():
            continue
        it = d.rglob("*") if recursive else d.glob("*")
        for p in it:
            try:
                if not p.is_file() or not _is_supported(p):
                    continue
                st = p.stat()
            except OSError:
                continue
            seen[str(p)] = {"mtime": st.st_mtime, "size": float(st.st_size)}
    return seen


def _changed(a: dict[str, float], b: dict[str, float]) -> bool:
    return a.get("mtime") != b.get("mtime") or a.get("size") != b.get("size")


def sync_once() -> dict[str, Any]:
    """Reconcile the index with the current contents of the watch folders.

    Returns a report dict. Safe to call when watching is disabled (no-op).
    """
    s = get_settings()
    if not s.watch.enabled:
        return {"enabled": False, "added": 0, "updated": 0, "removed": 0, "reindexed": False}

    dirs = s.watch_dirs
    report: dict[str, Any] = {
        "enabled": True,
        "dirs": len(dirs),
        "added": 0,
        "updated": 0,
        "removed": 0,
        "reindexed": False,
        "chunks_indexed": 0,
        "errors": [],
    }

    prev = _load_state()
    cur = scan(dirs, recursive=s.watch.recursive)

    added = [k for k in cur if k not in prev]
    updated = [k for k in cur if k in prev and _changed(cur[k], prev[k])]
    removed = [k for k in prev if k not in cur]

    # 1. Ingest new / modified files. build_index is idempotent, so we only pay
    #    the parse+embed cost for dirs that actually contain a change this cycle.
    if added or updated:
        from auralynq.pipeline import build_index

        touched = set(added) | set(updated)
        for d in dirs:
            if not any(Path(k) == d or d in Path(k).parents for k in touched):
                continue
            try:
                stats = build_index(d, rebuild=False)
                report["reindexed"] = True
                report["chunks_indexed"] += int(stats.get("chunks_indexed", 0) or 0)
            except Exception as exc:  # never let one dir abort the sync
                report["errors"].append(f"index {d}: {exc}")
        report["added"] = len(added)
        report["updated"] = len(updated)

    # 2. Drop documents whose source file has disappeared.
    if removed and s.watch.delete_missing:
        try:
            from auralynq.serving.corpus_manager import (
                _all_indexed_documents,
                _delete_document_by_id,
            )

            by_source = {d.get("source", ""): d for d in _all_indexed_documents()}
            for src in removed:
                doc = by_source.get(src)
                if not doc or not doc.get("doc_id"):
                    continue
                try:
                    _delete_document_by_id(str(doc["doc_id"]), doc)
                    report["removed"] += 1
                except Exception as exc:
                    report["errors"].append(f"delete {src}: {exc}")
        except Exception as exc:
            report["errors"].append(f"reconcile deletes: {exc}")

    # 3. Persist the fresh snapshot (also forgets removed files so they are not
    #    re-detected next cycle even when delete_missing is off).
    if added or updated or removed:
        _save_state(cur)
        _log.info(
            "watch.sync",
            added=report["added"],
            updated=report["updated"],
            removed=report["removed"],
            reindexed=report["reindexed"],
        )
    return report


def watch_status() -> dict[str, Any]:
    """Current watch configuration + per-directory presence and file counts."""
    s = get_settings()
    dirs = s.watch_dirs
    tracked = _load_state()
    dir_status = []
    for d in dirs:
        exists = d.exists() and d.is_dir()
        n_files = 0
        if exists:
            n_files = sum(
                1
                for p in (d.rglob("*") if s.watch.recursive else d.glob("*"))
                if p.is_file() and _is_supported(p)
            )
        dir_status.append({"path": str(d), "exists": exists, "files": n_files})
    return {
        "enabled": s.watch.enabled,
        "poll_seconds": s.watch.poll_seconds,
        "recursive": s.watch.recursive,
        "delete_missing": s.watch.delete_missing,
        "tracked": len(tracked),
        "directories": dir_status,
    }
