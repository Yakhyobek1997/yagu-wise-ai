"use client";
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, BookText, ChevronLeft, FileText, RefreshCw, Unlink } from "lucide-react";
import { wikiEntities, wikiEntity, wikiLint, type WikiPageSummary, type WikiPageDetail, type WikiLint } from "@/lib/api";
import { Markdown } from "@/components/Markdown";

function stripFrontmatter(md: string): string {
  if (md.startsWith("---")) {
    const end = md.indexOf("\n---", 3);
    if (end !== -1) return md.slice(end + 4).replace(/^\n+/, "");
  }
  return md;
}

/**
 * Compounding Wiki inspector: browse the durable, LLM-synthesized entity pages
 * built from the knowledge graph at ingest. Master list → page detail. Shows a
 * clear disabled/empty state when the wiki layer is off or unpopulated.
 */
export function WikiPanel({ refreshKey }: { refreshKey?: number }) {
  const [state, setState] = useState<{ enabled: boolean; count: number; pages: WikiPageSummary[] }>({
    enabled: false,
    count: 0,
    pages: [],
  });
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<WikiPageDetail | null>(null);
  const [loadingPage, setLoadingPage] = useState(false);
  const [lint, setLint] = useState<WikiLint | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    wikiEntities()
      .then(setState)
      .catch(() => {})
      .finally(() => setLoading(false));
    wikiLint().then(setLint).catch(() => {});
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  const open = (id: string) => {
    setLoadingPage(true);
    wikiEntity(id)
      .then(setSelected)
      .catch(() => {})
      .finally(() => setLoadingPage(false));
  };

  // ---- detail view ----
  if (selected) {
    return (
      <div className="space-y-2">
        <button
          type="button"
          onClick={() => setSelected(null)}
          className="inline-flex items-center gap-1 text-xs text-fg3 transition hover:text-fg"
        >
          <ChevronLeft className="h-3.5 w-3.5" aria-hidden /> All pages
        </button>
        <div className="card-inset">
          <div className="mb-1 flex items-center gap-2">
            <BookText className="h-4 w-4 shrink-0 text-brand" aria-hidden />
            <h3 className="text-sm font-semibold text-fg">{selected.title || selected.id}</h3>
          </div>
          <div className="mb-2 flex flex-wrap gap-1.5 text-[10px] text-fg3">
            <span className="tag">{selected.mentions} mentions</span>
            <span className="tag">{selected.sources.length} source{selected.sources.length === 1 ? "" : "s"}</span>
            {selected.updated && <span className="tag">updated {selected.updated.slice(0, 10)}</span>}
          </div>
          <div className="border-t border-edge/60 pt-2">
            <Markdown text={stripFrontmatter(selected.markdown)} />
          </div>
        </div>
      </div>
    );
  }

  // ---- list view ----
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="inline-flex items-center gap-1.5 text-sm font-semibold text-fg">
          <BookText className="h-4 w-4 text-brand" aria-hidden /> Compounding Wiki
          {state.enabled && <span className="font-mono text-xs text-fg3">{state.count}</span>}
        </h3>
        <button
          type="button"
          onClick={load}
          aria-label="Refresh wiki"
          className="text-fg3 transition hover:text-fg"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} aria-hidden />
        </button>
      </div>

      {state.enabled && lint && (lint.contradiction_count > 0 || lint.orphan_pages.length > 0) && (
        <div className="flex flex-wrap gap-1.5">
          {lint.contradiction_count > 0 && (
            <span className="pill pill-warn" title="New sources contradicted prior claims — see the flagged pages">
              <AlertTriangle className="h-3 w-3" aria-hidden /> {lint.contradiction_count} contradiction
              {lint.contradiction_count === 1 ? "" : "s"} flagged
            </span>
          )}
          {lint.orphan_pages.length > 0 && (
            <span className="pill pill-neutral" title="Pages nothing links to">
              <Unlink className="h-3 w-3" aria-hidden /> {lint.orphan_pages.length} orphan
              {lint.orphan_pages.length === 1 ? "" : "s"}
            </span>
          )}
        </div>
      )}

      {!state.enabled ? (
        <div className="card-inset text-xs text-fg3">
          The compounding wiki is off. Enable it with{" "}
          <code className="rounded bg-ink/60 px-1 py-0.5 font-mono text-fg2">AURALYNQ_WIKI__ENABLED=true</code>{" "}
          and re-ingest — Auralynq will synthesize durable, cited entity pages from the knowledge graph.
        </div>
      ) : state.pages.length === 0 ? (
        <div className="card-inset text-xs text-fg3">
          No wiki pages yet. Ingest documents and Auralynq will compile entity pages here.
        </div>
      ) : (
        <ul className="space-y-1">
          {state.pages.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                onClick={() => open(p.id)}
                className="flex w-full items-center gap-2 rounded-lg border border-edge bg-panel2 px-2.5 py-1.5 text-left transition hover:border-edge2 hover:bg-panel"
              >
                <FileText className="h-3.5 w-3.5 shrink-0 text-fg3" aria-hidden />
                <span className="min-w-0 flex-1 truncate text-sm text-fg">{p.title || p.id}</span>
                <span className="shrink-0 font-mono text-[10px] text-fg3">{p.mentions}×</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {loadingPage && <div className="text-center text-xs text-fg3">Loading page…</div>}
    </div>
  );
}
