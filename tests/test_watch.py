"""Watch Folder — incremental auto-reindex of a local directory.

Runs end-to-end on the offline test stack (hash embedder + memory vector store
from conftest), so ``sync_once`` actually ingests, indexes and deletes.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from auralynq.config import get_settings, reload_settings
from auralynq.serving import watcher
from auralynq.vectorstore.factory import get_store


def _enable(monkeypatch, watch_dir: Path, delete_missing: bool = True) -> None:
    monkeypatch.setenv("AURALYNQ_WATCH__ENABLED", "true")
    monkeypatch.setenv("AURALYNQ_WATCH__DIRS", f'["{watch_dir}"]')
    monkeypatch.setenv("AURALYNQ_WATCH__POLL_SECONDS", "0")
    monkeypatch.setenv("AURALYNQ_WATCH__DELETE_MISSING", "true" if delete_missing else "false")
    reload_settings()
    get_store.cache_clear()


def _bump_mtime(p: Path) -> None:
    future = time.time() + 5
    os.utime(p, (future, future))


def test_disabled_is_noop():
    reload_settings()  # default: watch disabled
    rep = watcher.sync_once()
    assert rep["enabled"] is False
    assert rep["reindexed"] is False


def test_watch_dirs_default_and_relative(monkeypatch):
    reload_settings()
    s = get_settings()
    # Default: <data_dir>/watch when none configured.
    assert s.watch_dirs == [s.data_dir / "watch"]
    monkeypatch.setenv("AURALYNQ_WATCH__DIRS", '["reports","/mnt/docs"]')
    reload_settings()
    s = get_settings()
    assert s.watch_dirs[0] == s.data_dir / "reports"  # relative → under data_dir
    assert s.watch_dirs[1] == Path("/mnt/docs")  # absolute preserved


def test_scan_ignores_unsupported(tmp_path):
    (tmp_path / "keep.md").write_text("hello", encoding="utf-8")
    (tmp_path / "skip.transcript.json").write_text("{}", encoding="utf-8")
    (tmp_path / "skip.bin").write_bytes(b"\x00\x01")
    seen = watcher.scan([tmp_path])
    names = {Path(k).name for k in seen}
    assert names == {"keep.md"}


def test_add_update_remove(monkeypatch, tmp_path):
    watch_dir = tmp_path / "watched"
    watch_dir.mkdir()
    _enable(monkeypatch, watch_dir)

    # 1. ADD — a new file is ingested and indexed.
    doc = watch_dir / "ericsson.md"
    doc.write_text(
        "# Ericsson\nEricsson filed action for fair and reasonable FRAND patent licensing.",
        encoding="utf-8",
    )
    rep = watcher.sync_once()
    assert rep["added"] == 1
    assert rep["reindexed"] is True
    assert get_store().count() > 0

    # 2. IDEMPOTENT — unchanged tree does no work (no re-embed / no KG rebuild).
    rep2 = watcher.sync_once()
    assert rep2["added"] == 0 and rep2["updated"] == 0 and rep2["removed"] == 0
    assert rep2["reindexed"] is False

    # 3. UPDATE — modified content is detected via (mtime, size) and re-indexed.
    doc.write_text(
        "# Ericsson\nEricsson and Ford disagree about the patent licensing terms today.",
        encoding="utf-8",
    )
    _bump_mtime(doc)
    rep3 = watcher.sync_once()
    assert rep3["updated"] == 1
    assert rep3["reindexed"] is True

    # 4. REMOVE — a vanished file is deleted from the index + graph.
    count_before = get_store().count()
    assert count_before > 0
    doc.unlink()
    rep4 = watcher.sync_once()
    assert rep4["removed"] == 1
    assert get_store().count() < count_before


def test_remove_kept_when_delete_missing_off(monkeypatch, tmp_path):
    watch_dir = tmp_path / "w2"
    watch_dir.mkdir()
    _enable(monkeypatch, watch_dir, delete_missing=False)

    doc = watch_dir / "ford.md"
    doc.write_text("Ford joined the AutoHarvest foundation for open innovation.", encoding="utf-8")
    watcher.sync_once()
    count_after_add = get_store().count()
    assert count_after_add > 0

    doc.unlink()
    rep = watcher.sync_once()
    # File is forgotten from state, but its vectors are retained.
    assert rep["removed"] == 0
    assert get_store().count() == count_after_add


def test_watch_status(monkeypatch, tmp_path):
    watch_dir = tmp_path / "ws"
    watch_dir.mkdir()
    (watch_dir / "a.md").write_text("alpha", encoding="utf-8")
    (watch_dir / "b.txt").write_text("bravo", encoding="utf-8")
    _enable(monkeypatch, watch_dir)

    st = watcher.watch_status()
    assert st["enabled"] is True
    assert st["delete_missing"] is True
    assert len(st["directories"]) == 1
    d0 = st["directories"][0]
    assert d0["exists"] is True
    assert d0["files"] == 2
