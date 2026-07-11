"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { CorpusSummary, DocumentMeta, GroundingSummary, corpusSummary, fetchGroundingSummary, fetchSuggestions, ingestFile } from "@/lib/api";
import { displaySource, timeAgo } from "@/lib/format";
import { CorpusManageModal } from "@/components/CorpusManageModal";
import { IngestSources } from "@/components/IngestSources";

const ACCEPT = ".pdf,.docx,.html,.htm,.md,.txt,.wav,.mp3,.m4a";
const TYPES = ["PDF", "DOCX", "HTML", "Markdown", "TXT", "WAV", "MP3", "M4A"];

interface Recent {
  name: string;
  docs: number;
  chunks: number;
  skipped: number;
  ok: boolean;
}

export function IngestPanel({ onAsk, onDeleted }: { onAsk?: (q: string) => void; onDeleted?: () => void }) {
  const [status, setStatus] = useState<{ kind: "ok" | "err" | "info"; msg: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [summary, setSummary] = useState<CorpusSummary | null>(null);
  const [groundingSummary, setGroundingSummary] = useState<GroundingSummary | null>(null);
  const [showReindexInfo, setShowReindexInfo] = useState(false);
  const [samples, setSamples] = useState<string[]>([]);
  const [recent, setRecent] = useState<Recent[]>([]);
  const [showManage, setShowManage] = useState(false);
  const [manageAction, setManageAction] = useState<"clear_all" | "delete_last" | undefined>(undefined);

  const refresh = useCallback(async () => {
    try {
      const [s, sug] = await Promise.all([corpusSummary(), fetchSuggestions(3)]);
      setSummary(s);
      setSamples(sug.suggestions);
    } catch {
      /* backend may be warming up */
    }
    try {
      const gs = await fetchGroundingSummary();
      setGroundingSummary(gs);
    } catch {
      /* visual grounding endpoint unavailable */
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const upload = useCallback(
    async (file: File) => {
      setBusy(true);
      setStatus({ kind: "info", msg: `Uploading ${file.name} — parsing → chunking → indexing…` });
      try {
        const r = await ingestFile(file);
        setStatus({
          kind: "ok",
          msg: `✓ Indexed ${r.documents} document(s), ${r.chunks} chunk(s)${
            r.skipped ? `, ${r.skipped} skipped` : ""
          }.`,
        });
        setRecent((prev) =>
          [{ name: file.name, docs: r.documents, chunks: r.chunks, skipped: r.skipped || 0, ok: true }, ...prev].slice(0, 5),
        );
        await refresh();
      } catch (err) {
        setStatus({ kind: "err", msg: `✗ ${(err as Error).message}` });
        setRecent((prev) => [{ name: file.name, docs: 0, chunks: 0, skipped: 0, ok: false }, ...prev].slice(0, 5));
      } finally {
        setBusy(false);
      }
    },
    [refresh],
  );

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDrag(false);
    const file = e.dataTransfer.files?.[0];
    if (file && !busy) void upload(file);
  }

  const failed = summary?.failed_files || [];
  const docs: DocumentMeta[] = (summary?.document_titles || []).map((title, i) => ({
    doc_id: `doc_${i}`,
    source: title,
    title: displaySource(title),
    source_type: "unknown",
  }));

  return (
    <div className="space-y-4">
      <IngestSources onUpload={() => fileInputRef.current?.click()} />
      {/* corpus stats */}
      {summary && (
        <div className="card-inset">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-fg">Corpus</h3>
            <div className="flex items-center gap-2">
              <button onClick={() => void refresh()} className="text-[11px] text-fg3 hover:text-brand">
                ↻ Refresh
              </button>
              {summary.indexed && (
                <button
                  onClick={() => { setManageAction(undefined); setShowManage(true); }}
                  className="rounded-md border border-bad/40 px-2 py-0.5 text-[11px] text-bad transition hover:bg-bad/10"
                >
                  Manage
                </button>
              )}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-1.5 text-center">
            <div className="stat">
              <div className="stat-value">{summary.indexed_document_count}</div>
              <div className="stat-label">docs</div>
            </div>
            <div className="stat">
              <div className="stat-value">{summary.vector_count}</div>
              <div className="stat-label">vectors</div>
            </div>
            <div className="stat">
              <div className="stat-value">{summary.entity_count}</div>
              <div className="stat-label">entities</div>
            </div>
          </div>
          <p className="mt-2 text-[11px] text-fg3">Last indexed: {timeAgo(summary.last_indexed)}</p>

          {/* indexed document list */}
          {summary.document_titles.length > 0 && (
            <div className="mt-3">
              <p className="stat-label mb-1">Indexed documents</p>
              <ul className="space-y-1">
                {summary.document_titles.slice(0, 8).map((title) => (
                  <li key={title} className="flex items-center justify-between text-xs">
                    <span className="truncate text-fg2" title={title}>
                      📄 {displaySource(title)}
                    </span>
                    <span className="ml-2 shrink-0 text-fg3">{(summary.source_types as Record<string,number>)?.pdf ? "pdf" : ""}</span>
                  </li>
                ))}
                {summary.document_titles.length > 8 && (
                  <li className="text-[11px] text-fg3">
                    … {summary.document_titles.length - 8} more
                  </li>
                )}
              </ul>
            </div>
          )}

          {/* quick delete actions */}
          {summary.indexed && (
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                onClick={() => { setManageAction("delete_last"); setShowManage(true); }}
                className="flex-1 rounded-lg border border-bad/30 py-1.5 text-xs text-bad transition hover:bg-bad/10"
              >
                Delete last document
              </button>
              <button
                onClick={() => { setManageAction("clear_all"); setShowManage(true); }}
                className="flex-1 rounded-lg border border-bad/30 py-1.5 text-xs text-bad transition hover:bg-bad/10"
              >
                Clear all corpus
              </button>
            </div>
          )}

          {!summary.indexed && (
            <p className="mt-3 rounded-lg border border-edge bg-panel2 p-2.5 text-xs text-fg3">
              No documents indexed yet. Upload a file to begin.
            </p>
          )}
        </div>
      )}

      {/* visual grounding status */}
      {groundingSummary && (
        <div className="card-inset space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-fg">Visual Grounding</h3>
            <span className={`pill ${groundingSummary.enabled ? "pill-ok" : "pill-neutral"}`}>
              <span
                className={`inline-block h-1.5 w-1.5 rounded-full ${groundingSummary.enabled ? "bg-ok" : "bg-edge2"}`}
              />
              {groundingSummary.enabled ? "enabled" : "disabled"}
            </span>
          </div>
          {groundingSummary.total_docs > 0 && (
            <div className="grid grid-cols-3 gap-1.5 text-center">
              <div className="stat">
                <div className="stat-value">{groundingSummary.total_docs}</div>
                <div className="stat-label">total</div>
              </div>
              <div className="stat">
                <div className="stat-value text-ok">{groundingSummary.grounded_docs}</div>
                <div className="stat-label">grounded</div>
              </div>
              <div className="stat">
                <div className={`stat-value ${groundingSummary.needs_reindex > 0 ? "text-warn" : "text-ok"}`}>
                  {groundingSummary.needs_reindex}
                </div>
                <div className="stat-label">need reindex</div>
              </div>
            </div>
          )}
          {groundingSummary.needs_reindex > 0 && (
            <div>
              <button
                onClick={() => setShowReindexInfo((v) => !v)}
                className="w-full rounded-lg border border-warn/40 py-1.5 text-xs text-warn transition hover:bg-warn/10"
              >
                {showReindexInfo ? "Hide" : "Reindex for visual grounding ↓"}
              </button>
              {showReindexInfo && (
                <div className="mt-2 rounded-lg border border-edge bg-panel2 p-2.5 text-[11px] text-fg3 space-y-1">
                  <p className="font-semibold text-fg2">How to enable visual grounding</p>
                  <p>
                    {groundingSummary.needs_reindex} document
                    {groundingSummary.needs_reindex !== 1 ? "s were" : " was"} indexed before visual
                    grounding metadata was available.
                  </p>
                  <p>
                    Re-upload those documents above — the indexer will automatically attach bounding-box
                    and page metadata so citations show highlighted source regions.
                  </p>
                </div>
              )}
            </div>
          )}
          {groundingSummary.total_docs === 0 && (
            <p className="text-[11px] text-fg3">
              Upload a PDF to enable source highlights with bounding-box grounding.
            </p>
          )}
        </div>
      )}

      {/* drag-and-drop zone */}
      <label
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        className={`flex cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed p-6 text-center transition ${
          drag ? "border-brand bg-brand/10" : "border-edge2 hover:border-brand/50 hover:bg-panel2"
        }`}
      >
        <span className="text-2xl" aria-hidden>
          {busy ? "⏳" : "⬆️"}
        </span>
        <span className="text-sm font-medium text-fg">
          {busy ? "Indexing…" : "Drag a file here, or click to upload"}
        </span>
        <span className="text-[11px] text-fg3">Chunked with source spans → hybrid index + graph</span>
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          disabled={busy}
          accept={ACCEPT}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void upload(f);
          }}
        />
      </label>

      {/* indexing progress */}
      {busy && (
        <div className="h-1 w-full overflow-hidden rounded-full bg-edge">
          <div className="h-1 w-1/3 animate-pulse rounded-full bg-brand" />
        </div>
      )}

      {/* supported types */}
      <div>
        <p className="stat-label mb-1">Supported file types</p>
        <div className="flex flex-wrap gap-1">
          {TYPES.map((t) => (
            <span key={t} className="tag">
              {t}
            </span>
          ))}
        </div>
      </div>

      {status && (
        <p
          className={`text-sm ${
            status.kind === "ok" ? "text-ok" : status.kind === "err" ? "text-bad" : "text-fg3"
          }`}
        >
          {status.msg}
        </p>
      )}

      {/* recent uploads */}
      {recent.length > 0 && (
        <div className="card-inset">
          <p className="stat-label mb-1.5">Recent uploads</p>
          <ul className="space-y-1 text-xs">
            {recent.map((r, i) => (
              <li key={i} className="flex items-center justify-between gap-2">
                <span className="truncate text-fg2" title={r.name}>
                  {r.ok ? "✓" : "✕"} {displaySource(r.name)}
                </span>
                <span className={r.ok ? "text-fg3" : "text-bad"}>
                  {r.ok ? `${r.docs}d · ${r.chunks}c${r.skipped ? ` · ${r.skipped} skip` : ""}` : "failed"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* failed ingestion files (from corpus) */}
      {failed.length > 0 && (
        <div className="evidence-weak rounded-xl border p-2.5">
          <p className="stat-label mb-1 text-warn">Failed to ingest ({failed.length})</p>
          <ul className="space-y-0.5 text-xs text-fg2">
            {failed.slice(0, 5).map((f) => (
              <li key={f} className="truncate" title={f}>
                ⚠ {displaySource(f)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* sample questions the current corpus can actually answer */}
      {samples.length > 0 && (
        <div>
          <p className="stat-label mb-1">Try these on the current corpus</p>
          <div className="flex flex-wrap gap-1.5">
            {samples.map((q) => (
              <button
                key={q}
                onClick={() => onAsk?.(q)}
                className="rounded-full border border-edge bg-panel2 px-3 py-1 text-xs text-fg2 transition hover:border-brand hover:text-brand"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Corpus manage modal */}
      {showManage && (
        <CorpusManageModal
          onClose={() => { setShowManage(false); setManageAction(undefined); }}
          onDeleted={() => {
            void refresh();
            setShowManage(false);
            setManageAction(undefined);
            onDeleted?.();
          }}
          initialAction={manageAction}
        />
      )}
    </div>
  );
}
