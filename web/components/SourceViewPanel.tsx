"use client";
import { useState, useCallback, useRef } from "react";
import type { VisualGrounding, VisualHighlight, ClaimGrounding } from "@/lib/api";
import { API_BASE } from "@/lib/api";

// Citation color palette (matches citation markers 1-8)
const CITATION_COLORS = [
  "rgba(59,130,246,0.35)",   // blue  [1]
  "rgba(16,185,129,0.35)",   // green [2]
  "rgba(245,158,11,0.35)",   // amber [3]
  "rgba(239,68,68,0.35)",    // red   [4]
  "rgba(139,92,246,0.35)",   // purple[5]
  "rgba(236,72,153,0.35)",   // pink  [6]
  "rgba(14,165,233,0.35)",   // sky   [7]
  "rgba(251,191,36,0.35)",   // yellow[8]
];
const CITATION_BORDERS = [
  "rgb(59,130,246)",
  "rgb(16,185,129)",
  "rgb(245,158,11)",
  "rgb(239,68,68)",
  "rgb(139,92,246)",
  "rgb(236,72,153)",
  "rgb(14,165,233)",
  "rgb(251,191,36)",
];

function colorFor(idx: number) {
  return CITATION_COLORS[(idx - 1) % CITATION_COLORS.length];
}
function borderFor(idx: number) {
  return CITATION_BORDERS[(idx - 1) % CITATION_BORDERS.length];
}

const SUPPORT_CLS: Record<string, string> = {
  supported:   "text-ok border-ok/40 bg-ok/5",
  partial:     "text-warn border-warn/40 bg-warn/5",
  weak:        "text-warn border-warn/40 bg-warn/5",
  unsupported: "text-bad border-bad/40 bg-bad/5",
};
const SUPPORT_LABEL: Record<string, string> = {
  supported:   "Supported",
  partial:     "Partial",
  weak:        "Weak",
  unsupported: "Unsupported",
};

interface HighlightBoxProps {
  ev: VisualHighlight;
  containerW: number;
  containerH: number;
  hovered: string | null;
  onHover: (id: string | null) => void;
}

function HighlightBox({ ev, containerW, containerH, hovered, onHover }: HighlightBoxProps) {
  if (!ev.normalized_bbox) return null;
  const [x0, y0, x1, y1] = ev.normalized_bbox;
  const left = `${(x0 * 100).toFixed(2)}%`;
  const top = `${(y0 * 100).toFixed(2)}%`;
  const width = `${((x1 - x0) * 100).toFixed(2)}%`;
  const height = `${((y1 - y0) * 100).toFixed(2)}%`;
  const isHovered = hovered === ev.citation_id;
  const color = colorFor(ev.color_index);
  const border = borderFor(ev.color_index);

  return (
    <div
      style={{
        position: "absolute",
        left, top, width, height,
        background: color,
        border: `2px solid ${border}`,
        borderRadius: "3px",
        cursor: "pointer",
        opacity: isHovered ? 1 : 0.75,
        transition: "opacity 0.15s",
        zIndex: isHovered ? 20 : 10,
        boxShadow: isHovered ? `0 0 0 3px ${border}55` : undefined,
      }}
      onMouseEnter={() => onHover(ev.citation_id)}
      onMouseLeave={() => onHover(null)}
      title={`[${ev.citation_id}] ${ev.snippet || ev.block_type} · ${(ev.relevance * 100).toFixed(0)}% relevance`}
    >
      <span
        style={{
          position: "absolute",
          top: -14,
          left: 2,
          background: border,
          color: "#fff",
          borderRadius: "3px",
          fontSize: 10,
          padding: "1px 5px",
          fontWeight: 700,
          whiteSpace: "nowrap",
        }}
      >
        [{ev.citation_id}]
      </span>
    </div>
  );
}

interface PageViewerProps {
  docId: string;
  page: number;
  highlights: VisualHighlight[];
  hoveredCitation: string | null;
  onHoverCitation: (id: string | null) => void;
  zoom: number;
}

function PageViewer({ docId, page, highlights, hoveredCitation, onHoverCitation, zoom }: PageViewerProps) {
  const [imgLoaded, setImgLoaded] = useState(false);
  const [imgError, setImgError] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);
  const imgUrl = `${API_BASE}/documents/${encodeURIComponent(docId)}/pages/${page}/image`;

  const pageHighlights = highlights.filter(
    h => h.page === page && h.normalized_bbox && h.support_type !== "unavailable"
  );

  return (
    <div
      style={{
        position: "relative",
        display: "inline-block",
        width: `${zoom * 100}%`,
        maxWidth: "100%",
        margin: "0 auto",
      }}
    >
      {imgError ? (
        <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-edge bg-surface p-8 text-center">
          <p className="text-sm font-medium text-fg">Page image not available</p>
          <p className="text-xs text-fg3">
            This document may need reindexing (reindex_required) to generate source page images.<br />
            Use the Ingest panel to reindex and enable source highlights.
          </p>
        </div>
      ) : (
        <>
          <img
            ref={imgRef}
            src={imgUrl}
            alt={`Page ${page}`}
            className="w-full rounded shadow-sm"
            style={{ display: "block" }}
            onLoad={() => setImgLoaded(true)}
            onError={() => setImgError(true)}
          />
          {imgLoaded && pageHighlights.map((ev, i) => (
            <HighlightBox
              key={`${ev.citation_id}-${i}`}
              ev={ev}
              containerW={imgRef.current?.offsetWidth ?? 600}
              containerH={imgRef.current?.offsetHeight ?? 800}
              hovered={hoveredCitation}
              onHover={onHoverCitation}
            />
          ))}
          {!imgLoaded && !imgError && (
            <div className="flex h-40 items-center justify-center">
              <span className="text-xs text-fg3">Loading page…</span>
            </div>
          )}
        </>
      )}
    </div>
  );
}

interface ClaimGroundingViewProps {
  claims: ClaimGrounding[];
  onClickCitation: (cid: string) => void;
}

function ClaimGroundingView({ claims, onClickCitation }: ClaimGroundingViewProps) {
  if (!claims.length) return null;
  return (
    <div className="space-y-1">
      <p className="text-xs font-semibold text-fg2">Claim grounding</p>
      {claims.map(cg => (
        <div key={cg.claim_id} className={`rounded-lg border px-2.5 py-1.5 text-xs ${SUPPORT_CLS[cg.support_status] || "border-edge text-fg3"}`}>
          <span className="mr-1 font-semibold">[{SUPPORT_LABEL[cg.support_status] || cg.support_status}]</span>
          {cg.text.length > 100 ? cg.text.slice(0, 100) + "…" : cg.text}
          {cg.citation_ids.length > 0 && (
            <span className="ml-1 text-fg3">
              {cg.citation_ids.map(cid => (
                <button
                  key={cid}
                  className="ml-0.5 underline hover:text-fg"
                  onClick={() => onClickCitation(cid)}
                >
                  [{cid}]
                </button>
              ))}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

interface SourceViewPanelProps {
  grounding: VisualGrounding | null | undefined;
  activeCitation: string | null;
  onClose?: () => void;
  onOpenWorkspace?: () => void;
}

export function SourceViewPanel({ grounding, activeCitation, onClose, onOpenWorkspace }: SourceViewPanelProps) {
  const [zoom, setZoom] = useState(1.0);
  const [hoveredCitation, setHoveredCitation] = useState<string | null>(activeCitation);
  const [showGrounding, setShowGrounding] = useState(false);

  const highlights = grounding?.highlights ?? [];
  const claims = grounding?.claim_grounding ?? [];
  const warnings = grounding?.warnings ?? [];

  // Group highlights by (doc_id, page)
  const pageGroups = new Map<string, { docId: string; page: number; highlights: VisualHighlight[] }>();
  for (const h of highlights) {
    if (!h.doc_id || h.page == null) continue;
    const key = `${h.doc_id}:${h.page}`;
    if (!pageGroups.has(key)) {
      pageGroups.set(key, { docId: h.doc_id, page: h.page, highlights: [] });
    }
    pageGroups.get(key)!.highlights.push(h);
  }
  const pages = Array.from(pageGroups.values());

  const handleCitationClick = useCallback((cid: string) => {
    setHoveredCitation(cid);
  }, []);

  if (!grounding) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
        <span className="text-3xl" aria-hidden>📄</span>
        <p className="text-sm font-medium text-fg">Ask a question to see source grounding.</p>
        <p className="max-w-xs text-xs text-fg3">
          Source View shows the original PDF page with highlighted evidence regions linked to your answer citations.
        </p>
      </div>
    );
  }

  if (!grounding.visual_grounding_available) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-10 text-center">
        <span className="text-3xl" aria-hidden>🔍</span>
        <p className="text-sm font-medium text-fg">Visual grounding not available</p>
        {warnings.length > 0 ? (
          <div className="max-w-xs space-y-1">
            {warnings.map((w, i) => (
              <p key={i} className="text-xs text-fg3">{w}</p>
            ))}
          </div>
        ) : (
          <p className="max-w-xs text-xs text-fg3">
            This document may have been indexed without visual grounding metadata.
            Reindex to enable source highlights.
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Header controls */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-semibold text-fg">Source View</span>
          <span className="pill pill-neutral">{grounding.grounding_stage}</span>
        </div>
        <div className="flex items-center gap-1.5">
          {onOpenWorkspace && (
            <button
              className="flex items-center gap-1 rounded-lg border border-brand/40 bg-brand/10 px-2.5 py-1 text-xs font-semibold text-brand transition hover:bg-brand/20"
              onClick={onOpenWorkspace}
              title="Open full Source Workspace"
            >
              ⛶ Expand
            </button>
          )}
          <button
            className="tag hover:border-edge2 hover:text-fg"
            onClick={() => setShowGrounding(v => !v)}
            title="Toggle claim grounding view"
          >
            {showGrounding ? "Claims ▴" : "Claims ▾"}
          </button>
          <button
            className="tag hover:border-edge2 hover:text-fg"
            onClick={() => setZoom(z => Math.max(0.5, z - 0.25))}
            title="Zoom out"
          >−</button>
          <span className="text-xs text-fg3">{Math.round(zoom * 100)}%</span>
          <button
            className="tag hover:border-edge2 hover:text-fg"
            onClick={() => setZoom(z => Math.min(2.0, z + 0.25))}
            title="Zoom in"
          >+</button>
          <button
            className="tag hover:border-edge2 hover:text-fg"
            onClick={() => setZoom(1.0)}
            title="Fit width"
          >fit</button>
        </div>
      </div>

      {/* Citation legend */}
      {highlights.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {Array.from(new Set(highlights.map(h => h.color_index))).sort().map(idx => (
            <button
              key={idx}
              className="flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold"
              style={{
                background: colorFor(idx),
                border: `1.5px solid ${borderFor(idx)}`,
                color: borderFor(idx),
              }}
              onClick={() => setHoveredCitation(h => h === String(idx) ? null : String(idx))}
            >
              [{idx}]
            </button>
          ))}
        </div>
      )}

      {/* Warnings */}
      {warnings.map((w, i) => (
        <p key={i} className="rounded-lg border border-warn/30 bg-warn/5 px-3 py-1.5 text-xs text-warn">
          {w}
        </p>
      ))}

      {/* Claim grounding */}
      {showGrounding && (
        <ClaimGroundingView claims={claims} onClickCitation={handleCitationClick} />
      )}

      {/* Page viewers */}
      <div className="space-y-4 overflow-x-auto">
        {pages.length === 0 ? (
          <div className="text-center text-xs text-fg3 py-6">
            No source pages to display for this answer.
          </div>
        ) : (
          pages.map(({ docId, page, highlights: ph }) => (
            <div key={`${docId}:${page}`} className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="text-xs text-fg3">Page {page}</span>
                <span className="text-xs text-fg3">·</span>
                <span className="text-xs text-fg3">
                  {ph.filter(h => h.normalized_bbox).length} highlight(s)
                </span>
              </div>
              <div className="overflow-hidden rounded-xl border border-edge bg-white">
                <PageViewer
                  docId={docId}
                  page={page}
                  highlights={highlights.filter(h => h.page === page)}
                  hoveredCitation={hoveredCitation}
                  onHoverCitation={setHoveredCitation}
                  zoom={zoom}
                />
              </div>
            </div>
          ))
        )}
      </div>

      <p className="text-[11px] text-fg3">
        {grounding.grounding_stage === "span"
          ? "Exact text spans highlighted from PDF layout extraction."
          : grounding.grounding_stage === "page"
          ? "Page-level grounding: exact span unavailable; full page shown."
          : "Visual grounding experimental. Text grounding is the default."}
      </p>
    </div>
  );
}
