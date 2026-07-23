"""Filesystem storage for the Compounding Wiki.

Owns ``data/storage/wiki_pages/``:
  * ``entity_<slug>.md`` — one markdown page per entity (YAML frontmatter + body).
  * ``_index.json``       — content catalog: page id -> {title, type, sources, ...}.
  * ``_log.jsonl``        — append-only, greppable timeline of wiki events.

Obsidian-vault-compatible: frontmatter keys (``sources``, ``type``, ``updated``)
double as Dataview fields and, later, retrieval signals. The LLM owns this layer;
humans read it.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(name: str) -> str:
    """Filesystem-safe, stable slug for a page id. Long ids get a short hash
    suffix so distinct entities never collide on a truncated filename."""
    base = _SLUG_RE.sub("_", name.strip().lower()).strip("_") or "unnamed"
    if len(base) <= 64:
        return base
    h = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    return f"{base[:55]}_{h}"


def _now() -> str:
    return _dt.datetime.now(tz=_dt.UTC).isoformat(timespec="seconds")


@dataclass
class WikiPageMeta:
    id: str
    title: str
    type: str = "entity"
    sources: list[str] | None = None
    mentions: int = 0
    updated: str = ""
    path: str = ""


class WikiStore:
    def __init__(self, wiki_dir: Path) -> None:
        self.dir = Path(wiki_dir)
        self.index_path = self.dir / "_index.json"
        self.log_path = self.dir / "_log.jsonl"

    # ---------------------------------------------------------- paths -----
    def page_filename(self, page_id: str) -> str:
        return f"entity_{slug(page_id)}.md"

    def page_path(self, page_id: str) -> Path:
        return self.dir / self.page_filename(page_id)

    # --------------------------------------------------------- index ------
    def _read_index(self) -> dict[str, dict[str, Any]]:
        if not self.index_path.exists():
            return {}
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_index(self, index: dict[str, dict[str, Any]]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.index_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.index_path)

    # ---------------------------------------------------------- write -----
    def write_page(
        self,
        page_id: str,
        *,
        title: str,
        body: str,
        page_type: str = "entity",
        sources: list[str] | None = None,
        mentions: int = 0,
        contradictions: list[dict[str, Any]] | None = None,
    ) -> WikiPageMeta:
        """Write (or overwrite) a page with YAML frontmatter and register it."""
        self.dir.mkdir(parents=True, exist_ok=True)
        srcs = sorted(set(sources or []))
        contras = contradictions or []
        updated = _now()
        if contras:
            lines = ["", "## ⚠ Contradictions flagged", ""]
            for c in contras:
                when = str(c.get("flagged_at", ""))[:10]
                prior_label = f"**Prior** (superseded {when})" if when else "**Prior**"
                lines.append(
                    f"- {prior_label}**:** {c.get('old_claim', '')}  \n"
                    f"  **New:** {c.get('new_claim', '')}"
                    + (f"  \n  _{c.get('why', '')}_" if c.get("why") else "")
                )
            body = body.rstrip() + "\n" + "\n".join(lines)
        lines = [
            "---",
            f"id: {json.dumps(page_id)}",
            f"title: {json.dumps(title)}",
            f"type: {page_type}",
            f"mentions: {mentions}",
            f"updated: {updated}",
        ]
        if srcs:
            lines.append("sources:")
            lines.extend(f"  - {json.dumps(s)}" for s in srcs)
        else:
            lines.append("sources: []")
        lines.append("---")
        frontmatter = "\n".join(lines) + "\n\n"
        path = self.page_path(page_id)
        path.write_text(frontmatter + body.strip() + "\n", encoding="utf-8")

        index = self._read_index()
        meta = WikiPageMeta(
            id=page_id,
            title=title,
            type=page_type,
            sources=srcs,
            mentions=mentions,
            updated=updated,
            path=path.name,
        )
        index[page_id] = {
            "title": title,
            "type": page_type,
            "sources": srcs,
            "mentions": mentions,
            "updated": updated,
            "path": path.name,
            "contradictions": contras,
        }
        self._write_index(index)
        return meta

    # ----------------------------------------------------------- read -----
    def read_page(self, page_id: str) -> dict[str, Any] | None:
        path = self.page_path(page_id)
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8")
        meta = self._read_index().get(page_id, {})
        return {"id": page_id, "markdown": text, **meta}

    def list_pages(self) -> list[dict[str, Any]]:
        return [{"id": pid, **meta} for pid, meta in self._read_index().items()]

    def count(self) -> int:
        return len(self._read_index())

    # ----------------------------------------------------------- lint -----
    def lint(self) -> dict[str, Any]:
        """Health-check the wiki: flagged contradictions + orphan pages (never
        referenced by a [[wikilink]] from any other page)."""
        index = self._read_index()
        contradictions: list[dict[str, Any]] = []
        for pid, meta in index.items():
            for c in meta.get("contradictions", []) or []:
                contradictions.append({**c, "entity": pid})
        linked: set[str] = set()
        for pid in index:
            page = self.read_page(pid)
            if not page:
                continue
            for target in re.findall(r"\[\[([^\]]+)\]\]", page["markdown"]):
                linked.add(target.strip().lower())
        orphans = [
            pid
            for pid, meta in index.items()
            if pid.lower() not in linked
            and str(meta.get("title", pid)).lower() not in linked
        ]
        return {
            "pages": len(index),
            "contradiction_count": len(contradictions),
            "contradictions": contradictions,
            "orphan_pages": sorted(orphans),
        }

    # ------------------------------------------------------------ log -----
    def append_log(self, event: str, **fields: Any) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        entry = {"ts": _now(), "event": event, **fields}
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
