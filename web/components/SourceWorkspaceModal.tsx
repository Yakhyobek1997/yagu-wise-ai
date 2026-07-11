"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Citation, ClaimGrounding, VisualGrounding, VisualHighlight } from "@/lib/api";
import { API_BASE } from "@/lib/api";

// ── Color palette ──────────────────────────────────────────────────────────
const CITATION_BG = [
  "rgba(59,130,246,0.30)",   // blue  [1]
  "rgba(16,185,129,0.30)",   // green [2]
  "rgba(245,158,11,0.30)",   // amber [3]
  "rgba(139,92,246,0.30)",   // purple[4]
  "rgba(236,72,153,0.30)",   // pink  [5]
  "rgba(14,165,233,0.30)",   // sky   [6]
  "rgba(251,191,36,0.30)",   // yellow[7]
  "rgba(239,68,68,0.30)",    // red   [8]
];
const CITATION_BORDER = [
  "rgb(59,130,246)",
  "rgb(16,185,129)",
  "rgb(245,158,11)",
  "rgb(139,92,246)",
  "rgb(236,72,153)",
  "rgb(14,165,233)",
  "rgb(251,191,36)",
  "rgb(239,68,68)",
];
const SUPPORT_BG: Record<string, string> = {
  supported:   "rgba(16,185,129,0.25)",
  partial:     "rgba(245,158,11,0.25)",
  weak:        "rgba(245,158,11,0.20)",
  unsupported: "rgba(239,68,68,0.20)",
};
const SUPPORT_BORDER: Record<string, string> = {
  supported:   "rgb(16,185,129)",
  partial:     "rgb(245,158,11)",
  weak:        "rgb(245,158,11)",
  unsupported: "rgb(239,68,68)",
};
const SUPPORT_LABEL: Record<string, string> = {
  supported:   "Supported",
  partial:     "Partial",
  weak:        "Weak",
  unsupported: "Unsupported",
};

function citBg(idx: number)     { return CITATION_BG[(idx - 1) % CITATION_BG.length]; }
function citBorder(idx: number) { return CITATION_BORDER[(idx - 1) % CITATION_BORDER.length]; }

// ── Types ──────────────────────────────────────────────────────────────────
interface PageKey { docId: string; page: number }

function pageKey(p: PageKey) { return `${p.docId}:${p.page}`; }

// ── Highlight overlay box ──────────────────────────────────────────────────
function HighlightBox({
  ev,
  active,
  hovered,
  onHover,
  onSelect,
}: {
  ev: VisualHighlight;
  active: boolean;
  hovered: boolean;
  onHover: (id: string | null) => void;
  onSelect: (ev: VisualHighlight) => void;
}) {
  if (!ev.normalized_bbox) return null;
  const [x0, y0, x1, y1] = ev.normalized_bbox;
  const bg = active
    ? SUPPORT_BG[ev.support_type] ?? citBg(ev.color_index)
    : citBg(ev.color_index);
  const border = active
    ? SUPPORT_BORDER[ev.support_type] ?? citBorder(ev.color_index)
    : citBorder(ev.color_index);
  const elevated = active || hovered;

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`Citation [${ev.citation_id}] — ${ev.block_type}`}
      style={{
        position: "absolute",
        left: `${(x0 * 100).toFixed(3)}%`,
        top:  `${(y0 * 100).toFixed(3)}%`,
        width: `${((x1 - x0) * 100).toFixed(3)}%`,
        height: `${((y1 - y0) * 100).toFixed(3)}%`,
        background: elevated ? bg.replace("0.30", "0.50").replace("0.25", "0.50") : bg,
        border: `${elevated ? 2.5 : 2}px solid ${border}`,
        borderRadius: "3px",
        cursor: "pointer",
        zIndex: elevated ? 20 : 10,
        boxShadow: elevated ? `0 0 0 3px ${border}44` : undefined,
        transition: "all 0.12s ease",
      }}
      onMouseEnter={() => onHover(ev.citation_id)}
      onMouseLeave={() => onHover(null)}
      onClick={() => onSelect(ev)}
      onKeyDown={(e) => e.key === "Enter" && onSelect(ev)}
      title={`[${ev.citation_id}] ${ev.block_type} · ${(ev.relevance * 100).toFixed(0)}% relevance`}
    >
      <span
        aria-hidden
        style={{
          position: "absolute",
          top: -16,
          left: 0,
          background: border,
          color: "#fff",
          borderRadius: "3px 3px 3px 0",
          fontSize: 10,
          fontWeight: 700,
          padding: "1px 5px",
          whiteSpace: "nowrap",
          lineHeight: "14px",
        }}
      >
        [{ev.citation_id}]
      </span>
    </div>
  );
}

// ── Large page viewer (center panel) ──────────────────────────────────────
function WorkspacePageViewer({
  docId,
  page,
  highlights,
  zoom,
  activeCitation,
  hoveredCitation,
  selectedHighlight,
  onHoverCitation,
  onSelectHighlight,
}: {
  docId: string;
  page: number;
  highlights: VisualHighlight[];
  zoom: number;
  activeCitation: string | null;
  hoveredCitation: string | null;
  selectedHighlight: VisualHighlight | null;
  onHoverCitation: (id: string | null) => void;
  onSelectHighlight: (ev: VisualHighlight) => void;
}) {
  const [imgLoaded, setImgLoaded] = useState(false);
  const [imgError, setImgError] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);
  const imgUrl = `${API_BASE}/documents/${encodeURIComponent(docId)}/pages/${page}/image`;

  const pageHighlights = highlights.filter(
    h => h.page === page && h.normalized_bbox && h.support_type !== "unavailable"
  );

  return (
    <div
      className="flex justify-center px-4 py-3"
      style={{ minWidth: `${zoom * 100}%` }}
    >
      <div
        style={{
          position: "relative",
          display: "inline-block",
          width: `${zoom * 100}%`,
          maxWidth: zoom >= 1 ? "none" : "100%",
        }}
      >
        {imgError ? (
          <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-edge bg-surface p-12 text-center">
            <span className="text-4xl" aria-hidden>📄</span>
            <p className="text-sm font-medium text-fg">Page image not available</p>
            <p className="max-w-xs text-xs text-fg3">
              This document may need reindexing to generate source page images.
              Use the Ingest panel to reindex and enable source highlights.
            </p>
          </div>
        ) : (
          <>
            <img
              ref={imgRef}
              src={imgUrl}
              alt={`Document page ${page}`}
              className="block w-full rounded-lg shadow-lg"
              style={{ border: "1px solid rgba(255,255,255,0.08)" }}
              onLoad={() => setImgLoaded(true)}
              onError={() => setImgError(true)}
            />
            {imgLoaded && pageHighlights.map((ev, i) => (
              <HighlightBox
                key={`${ev.citation_id}-${i}`}
                ev={ev}
                active={selectedHighlight?.citation_id === ev.citation_id && selectedHighlight?.chunk_id === ev.chunk_id}
                hovered={hoveredCitation === ev.citation_id}
                onHover={onHoverCitation}
                onSelect={onSelectHighlight}
              />
            ))}
            {!imgLoaded && !imgError && (
              <div className="flex h-64 items-center justify-center rounded-lg border border-edge bg-panel2">
                <div className="flex flex-col items-center gap-2">
                  <span className="text-xs text-fg3">Loading page {page}…</span>
                  <div className="h-1 w-24 overflow-hidden rounded-full bg-edge">
                    <div className="h-1 w-1/2 animate-pulse rounded-full bg-brand" />
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ── Left panel: Citations + claim grounding ────────────────────────────────
function CitationPanel({
  citations,
  highlights,
  claimGrounding,
  activeCitation,
  hoveredCitation,
  currentPage,
  onSelectCitation,
  onHoverCitation,
}: {
  citations: Citation[];
  highlights: VisualHighlight[];
  claimGrounding: ClaimGrounding[];
  activeCitation: string | null;
  hoveredCitation: string | null;
  currentPage: number;
  onSelectCitation: (cid: string, page: number) => void;
  onHoverCitation: (id: string | null) => void;
}) {
  return (
    <div className="scroll-thin flex flex-col gap-3 overflow-y-auto border-r border-edge bg-panel/40 p-3">
      <p className="text-xs font-semibold uppercase tracking-wider text-fg3">Citations</p>
      <div className="space-y-1.5">
        {citations.map(c => {
          const cid = String(c.marker);
          const hl = highlights.find(h => h.citation_id === cid);
          const page = hl?.page ?? c.page ?? null;
          const isActive = activeCitation === cid;
          const isHovered = hoveredCitation === cid;
          const bg = citBg(c.marker);
          const border = citBorder(c.marker);
          return (
            <button
              key={c.marker}
              onClick={() => page != null && onSelectCitation(cid, page)}
              onMouseEnter={() => onHoverCitation(cid)}
              onMouseLeave={() => onHoverCitation(null)}
              className="w-full rounded-lg border p-2.5 text-left transition"
              style={{
                background: isActive || isHovered ? bg : "transparent",
                borderColor: isActive ? border : "rgb(var(--c-edge))",
                boxShadow: isActive ? `0 0 0 1px ${border}44` : undefined,
              }}
              aria-pressed={isActive}
            >
              <div className="flex items-start gap-2">
                <span
                  className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold"
                  style={{ background: border, color: "#fff" }}
                >
                  {c.marker}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-fg">{c.source.split("/").pop() || c.source}</p>
                  {page != null && (
                    <p className="mt-0.5 text-[10px] text-fg3">
                      Page {page}
                      {currentPage === page && <span className="ml-1 text-brand">← current</span>}
                    </p>
                  )}
                  {hl && (
                    <p className="mt-0.5 text-[10px]" style={{ color: border }}>
                      {hl.support_type === "span" ? "Span-level" : hl.support_type === "page" ? "Page-level" : "No bbox"}
                    </p>
                  )}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {claimGrounding.length > 0 && (
        <>
          <p className="mt-2 text-xs font-semibold uppercase tracking-wider text-fg3">Claim grounding</p>
          <div className="space-y-1.5">
            {claimGrounding.map(cg => {
              const cls = {
                supported: "border-ok/30 bg-ok/5 text-ok",
                partial: "border-warn/30 bg-warn/5 text-warn",
                weak: "border-warn/20 bg-warn/5 text-warn",
                unsupported: "border-bad/30 bg-bad/5 text-bad",
              }[cg.support_status] ?? "border-edge text-fg3";
              return (
                <div key={cg.claim_id} className={`rounded-lg border p-2 text-[11px] ${cls}`}>
                  <span className="mr-1 font-semibold">[{SUPPORT_LABEL[cg.support_status] ?? cg.support_status}]</span>
                  {cg.text.length > 90 ? cg.text.slice(0, 90) + "…" : cg.text}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

// ── Right panel: Evidence details for current page ─────────────────────────
function EvidencePanel({
  highlights,
  currentPage,
  selectedHighlight,
  hoveredCitation,
  onSelectHighlight,
  onHoverCitation,
}: {
  highlights: VisualHighlight[];
  currentPage: number;
  selectedHighlight: VisualHighlight | null;
  hoveredCitation: string | null;
  onSelectHighlight: (ev: VisualHighlight | null) => void;
  onHoverCitation: (id: string | null) => void;
}) {
  const pageHighlights = highlights.filter(h => h.page === currentPage);

  return (
    <div className="scroll-thin flex flex-col gap-3 overflow-y-auto border-l border-edge bg-panel/40 p-3">
      <p className="text-xs font-semibold uppercase tracking-wider text-fg3">
        Evidence · Page {currentPage}
        {pageHighlights.length > 0 && (
          <span className="ml-1.5 rounded-full bg-edge px-1.5 py-0.5 text-[10px] text-fg2 font-normal normal-case tracking-normal">
            {pageHighlights.length}
          </span>
        )}
      </p>

      {pageHighlights.length === 0 && (
        <p className="text-xs text-fg3">No cited evidence on this page.</p>
      )}

      <div className="space-y-2">
        {pageHighlights.map((ev, i) => {
          const isSelected = selectedHighlight?.chunk_id === ev.chunk_id;
          const isHovered = hoveredCitation === ev.citation_id;
          const border = citBorder(ev.color_index);
          const bg = citBg(ev.color_index);
          return (
            <button
              key={`${ev.citation_id}-${i}`}
              onClick={() => onSelectHighlight(isSelected ? null : ev)}
              onMouseEnter={() => onHoverCitation(ev.citation_id)}
              onMouseLeave={() => onHoverCitation(null)}
              className="w-full rounded-lg border p-2.5 text-left transition"
              style={{
                background: isSelected || isHovered ? bg : "rgba(var(--c-panel-2)/0.5)",
                borderColor: isSelected ? border : "rgb(var(--c-edge))",
                boxShadow: isSelected ? `0 0 0 1px ${border}44` : undefined,
              }}
            >
              <div className="mb-1.5 flex items-center gap-1.5">
                <span
                  className="flex h-4 w-4 shrink-0 items-center justify-center rounded text-[9px] font-bold"
                  style={{ background: border, color: "#fff" }}
                >
                  {ev.citation_id}
                </span>
                <span className="rounded border px-1 py-0 text-[10px]" style={{ borderColor: border, color: border }}>
                  {ev.block_type}
                </span>
                <span className={`ml-auto rounded px-1 py-0 text-[10px] font-medium ${
                  ev.support_type === "span" ? "text-ok" : ev.support_type === "page" ? "text-warn" : "text-fg3"
                }`}>
                  {ev.support_type}
                </span>
              </div>
              {ev.snippet && (
                <p className="line-clamp-3 text-[11px] leading-relaxed text-fg2 italic">
                  "{ev.snippet.length > 160 ? ev.snippet.slice(0, 160) + "…" : ev.snippet}"
                </p>
              )}
              <div className="mt-1.5 flex items-center gap-3 text-[10px] text-fg3">
                <span>
                  relevance&nbsp;<span className="font-medium text-fg2">{(ev.relevance * 100).toFixed(0)}%</span>
                </span>
                <span>
                  confidence&nbsp;<span className="font-medium text-fg2">{(ev.confidence * 100).toFixed(0)}%</span>
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Legend */}
      <div className="mt-auto space-y-1 border-t border-edge pt-3">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-fg3">Legend</p>
        <div className="grid grid-cols-2 gap-1">
          {[
            { label: "Span-level", color: "rgb(16,185,129)", desc: "Exact text match" },
            { label: "Page-level", color: "rgb(245,158,11)", desc: "Whole page evidence" },
          ].map(({ label, color, desc }) => (
            <div key={label} className="flex items-start gap-1.5">
              <span className="mt-0.5 h-2.5 w-2.5 shrink-0 rounded-sm border" style={{ background: `${color}33`, borderColor: color }} />
              <div>
                <p className="text-[10px] font-medium text-fg">{label}</p>
                <p className="text-[9px] text-fg3">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Zoom preset buttons ────────────────────────────────────────────────────
const ZOOM_PRESETS = [0.5, 0.75, 1.0, 1.25, 1.5] as const;
const ZOOM_LABELS: Record<number, string> = { 0.5: "50%", 0.75: "75%", 1.0: "fit", 1.25: "125%", 1.5: "150%" };

// ── Main SourceWorkspaceModal ──────────────────────────────────────────────
export interface SourceWorkspaceModalProps {
  grounding: VisualGrounding | null | undefined;
  citations: Citation[];
  activeCitation: string | null;
  onClose: () => void;
}

export function SourceWorkspaceModal({
  grounding,
  citations,
  activeCitation,
  onClose,
}: SourceWorkspaceModalProps) {
  const highlights = grounding?.highlights ?? [];
  const claimGrounding = grounding?.claim_grounding ?? [];
  const warnings = grounding?.warnings ?? [];

  // Build sorted list of unique (docId, page) pairs from highlights
  const pageKeys = useMemo<PageKey[]>(() => {
    const seen = new Set<string>();
    const result: PageKey[] = [];
    for (const h of highlights) {
      if (h.page == null || !h.doc_id) continue;
      const k = pageKey({ docId: h.doc_id, page: h.page });
      if (!seen.has(k)) { seen.add(k); result.push({ docId: h.doc_id, page: h.page }); }
    }
    return result.sort((a, b) => a.page - b.page);
  }, [highlights]);

  // Find initial page from activeCitation
  const initialPageKey = useMemo<PageKey | null>(() => {
    if (activeCitation) {
      const hl = highlights.find(h => h.citation_id === activeCitation && h.page != null);
      if (hl?.page != null && hl.doc_id) return { docId: hl.doc_id, page: hl.page };
    }
    return pageKeys[0] ?? null;
  }, [activeCitation, highlights, pageKeys]);

  const [currentPageKey, setCurrentPageKey] = useState<PageKey | null>(initialPageKey);
  const [zoom, setZoom] = useState(1.0);
  const [selectedCitation, setSelectedCitation] = useState<string | null>(activeCitation);
  const [hoveredCitation, setHoveredCitation] = useState<string | null>(null);
  const [selectedHighlight, setSelectedHighlight] = useState<VisualHighlight | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const viewerRef = useRef<HTMLDivElement>(null);

  // Keep initial page in sync when activeCitation changes
  useEffect(() => {
    if (activeCitation) {
      const hl = highlights.find(h => h.citation_id === activeCitation && h.page != null);
      if (hl?.page != null && hl.doc_id) setCurrentPageKey({ docId: hl.doc_id, page: hl.page });
      setSelectedCitation(activeCitation);
    }
  }, [activeCitation, highlights]);

  // Escape closes the workspace
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight" || e.key === "ArrowDown") navigatePage(1);
      if (e.key === "ArrowLeft" || e.key === "ArrowUp") navigatePage(-1);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onClose, currentPageKey, pageKeys]);

  function navigatePage(dir: 1 | -1) {
    if (!currentPageKey) return;
    const idx = pageKeys.findIndex(p => pageKey(p) === pageKey(currentPageKey));
    const next = pageKeys[idx + dir];
    if (next) setCurrentPageKey(next);
  }

  function handleSelectCitation(cid: string, page: number) {
    setSelectedCitation(cid);
    const hl = highlights.find(h => h.citation_id === cid && h.page === page);
    if (hl?.doc_id) setCurrentPageKey({ docId: hl.doc_id, page });
    // Scroll viewer to top when navigating
    viewerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }

  function handleSelectHighlight(ev: VisualHighlight | null) {
    setSelectedHighlight(ev);
    if (ev) setSelectedCitation(ev.citation_id);
  }

  const currentDoc = currentPageKey?.docId ?? "";
  const currentPage = currentPageKey?.page ?? 1;
  const pageIdx = pageKeys.findIndex(p => pageKey(p) === pageKey(currentPageKey!));
  const hasPrev = pageIdx > 0;
  const hasNext = pageIdx < pageKeys.length - 1;

  // Stage display
  const stage = grounding?.grounding_stage ?? "unavailable";
  const stageCls = stage === "span" ? "text-ok" : stage === "page" ? "text-warn" : "text-fg3";
  const stageDot = stage === "span" ? "bg-ok" : stage === "page" ? "bg-warn" : "bg-fg3";

  if (!grounding?.visual_grounding_available) {
    return (
      <div className="fixed inset-0 z-[200] flex flex-col bg-ink/98 backdrop-blur-sm">
        <div className="flex items-center justify-between border-b border-edge px-5 py-3">
          <span className="text-sm font-semibold text-fg">Grounded Source Workspace</span>
          <button onClick={onClose} className="btn-ghost px-2 py-1 text-sm" aria-label="Close workspace">✕</button>
        </div>
        <div className="flex flex-1 items-center justify-center">
          <div className="flex flex-col items-center gap-3 text-center">
            <span className="text-4xl" aria-hidden>🔍</span>
            <p className="text-sm font-medium text-fg">Visual grounding not available</p>
            {warnings.map((w, i) => (
              <p key={i} className="max-w-sm text-xs text-fg3">{w}</p>
            ))}
            <p className="max-w-sm text-xs text-fg3">
              Reindex your documents to enable exact source highlights.
            </p>
            <button onClick={onClose} className="btn-ghost mt-2 text-sm">Close</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      role="dialog"
      aria-label="Grounded Source Workspace"
      aria-modal="true"
      className="fixed inset-0 z-[200] flex flex-col bg-ink"
    >
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex shrink-0 items-center gap-3 border-b border-edge bg-panel/80 px-4 py-2.5 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-fg">Grounded Source Workspace</span>
          <span className={`flex items-center gap-1.5 text-xs font-medium ${stageCls}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${stageDot}`} />
            {stage} grounding
          </span>
        </div>

        {/* Zoom controls */}
        <div className="ml-auto flex items-center gap-1">
          {ZOOM_PRESETS.map(z => (
            <button
              key={z}
              onClick={() => setZoom(z)}
              className={`rounded px-2 py-0.5 text-xs transition ${
                zoom === z ? "bg-brand/20 text-brand font-medium" : "text-fg3 hover:text-fg"
              }`}
            >
              {ZOOM_LABELS[z]}
            </button>
          ))}
          <button
            className="ml-1 rounded border border-edge px-2 py-0.5 text-xs text-fg3 hover:text-fg transition"
            onClick={() => setZoom(v => Math.max(0.5, parseFloat((v - 0.1).toFixed(1))))}
            title="Zoom out"
          >−</button>
          <span className="w-10 text-center text-xs text-fg3">{Math.round(zoom * 100)}%</span>
          <button
            className="rounded border border-edge px-2 py-0.5 text-xs text-fg3 hover:text-fg transition"
            onClick={() => setZoom(v => Math.min(2.0, parseFloat((v + 0.1).toFixed(1))))}
            title="Zoom in"
          >+</button>
        </div>

        {/* Page navigation */}
        {pageKeys.length > 0 && (
          <div className="flex items-center gap-1 border-l border-edge pl-3">
            <button
              className="rounded px-2 py-0.5 text-xs text-fg3 hover:text-fg transition disabled:opacity-40"
              disabled={!hasPrev}
              onClick={() => navigatePage(-1)}
              title="Previous page"
            >
              ‹
            </button>
            <span className="text-xs text-fg3">
              p.{currentPage}
              {pageKeys.length > 1 && <span className="text-fg4"> ({pageIdx + 1}/{pageKeys.length})</span>}
            </span>
            <button
              className="rounded px-2 py-0.5 text-xs text-fg3 hover:text-fg transition disabled:opacity-40"
              disabled={!hasNext}
              onClick={() => navigatePage(1)}
              title="Next page"
            >
              ›
            </button>
          </div>
        )}

        {/* Full-screen toggle */}
        <button
          className="rounded border border-edge px-2 py-0.5 text-xs text-fg3 hover:text-fg transition"
          onClick={() => setFullscreen(v => !v)}
          title={fullscreen ? "Show side panels" : "Full-screen PDF view"}
        >
          {fullscreen ? "⊞" : "⛶"}
        </button>

        {/* Warnings badge */}
        {warnings.length > 0 && (
          <span
            className="rounded border border-warn/30 bg-warn/10 px-2 py-0.5 text-xs text-warn"
            title={warnings.join("\n")}
          >
            ⚠ {warnings.length}
          </span>
        )}

        <button
          onClick={onClose}
          className="btn-ghost rounded px-2 py-1 text-sm"
          aria-label="Close workspace"
          title="Close (Esc)"
        >
          ✕
        </button>
      </div>

      {/* ── Three-panel body ─────────────────────────────────────────────── */}
      <div className={`flex min-h-0 flex-1 overflow-hidden ${fullscreen ? "grid grid-cols-[0_1fr_0]" : "grid grid-cols-[260px_1fr_280px]"}`}>

        {/* LEFT: Citations + claim grounding */}
        {!fullscreen && (
          <CitationPanel
            citations={citations}
            highlights={highlights}
            claimGrounding={claimGrounding}
            activeCitation={selectedCitation}
            hoveredCitation={hoveredCitation}
            currentPage={currentPage}
            onSelectCitation={handleSelectCitation}
            onHoverCitation={setHoveredCitation}
          />
        )}

        {/* CENTER: Large PDF viewer */}
        <div className="flex min-w-0 flex-col bg-ink/60">
          {/* Page thumbnails / quick-nav when multiple pages */}
          {pageKeys.length > 1 && (
            <div className="flex shrink-0 items-center gap-1.5 overflow-x-auto border-b border-edge px-4 py-1.5">
              {pageKeys.map((pk, i) => {
                const isCurrent = pageKey(pk) === pageKey(currentPageKey!);
                const hasHL = highlights.some(h => h.page === pk.page && h.doc_id === pk.docId);
                return (
                  <button
                    key={pageKey(pk)}
                    onClick={() => setCurrentPageKey(pk)}
                    className={`flex shrink-0 items-center gap-1 rounded px-2 py-0.5 text-xs transition ${
                      isCurrent ? "bg-brand/20 text-brand font-medium" : "text-fg3 hover:text-fg"
                    }`}
                  >
                    {hasHL && <span className="h-1.5 w-1.5 rounded-full bg-brand" />}
                    p.{pk.page}
                  </button>
                );
              })}
            </div>
          )}

          {/* Scrollable viewer area */}
          <div ref={viewerRef} className="scroll-thin min-h-0 flex-1 overflow-auto">
            {currentPageKey ? (
              <WorkspacePageViewer
                docId={currentDoc}
                page={currentPage}
                highlights={highlights}
                zoom={zoom}
                activeCitation={selectedCitation}
                hoveredCitation={hoveredCitation}
                selectedHighlight={selectedHighlight}
                onHoverCitation={setHoveredCitation}
                onSelectHighlight={handleSelectHighlight}
              />
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-fg3">
                No pages available
              </div>
            )}
          </div>
        </div>

        {/* RIGHT: Evidence details */}
        {!fullscreen && (
          <EvidencePanel
            highlights={highlights}
            currentPage={currentPage}
            selectedHighlight={selectedHighlight}
            hoveredCitation={hoveredCitation}
            onSelectHighlight={handleSelectHighlight}
            onHoverCitation={setHoveredCitation}
          />
        )}
      </div>
    </div>
  );
}
