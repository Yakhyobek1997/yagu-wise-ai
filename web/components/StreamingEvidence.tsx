"use client";
import { Loader2, Search } from "lucide-react";
import type { Citation } from "@/lib/api";
import { citationColor, scoreStrength, STRENGTH_META } from "@/lib/citations";
import { displaySource } from "@/lib/format";

const ROUTE_LABEL: Record<string, string> = {
  fast: "fast retrieval",
  hybrid: "hybrid retrieval",
  graph: "graph traversal",
  relational: "graph traversal",
};

function rgba(rgb: string, a: number): string {
  return rgb.replace("rgb(", "rgba(").replace(")", `,${a})`);
}

/**
 * Progressive-evidence strip shown while an answer streams (Perplexity's finding:
 * visible evidence assembling beats a bare spinner). Once the SSE `meta` event
 * arrives, retrieval is already done — so we render the real retrieved source
 * candidates as number-matched cards *above* the forming answer, then the final
 * event narrows them to the actually-cited subset. Falls back to detected-entity
 * chips before sources are known.
 */
export function StreamingEvidence({
  route,
  entities,
  sources,
}: {
  route?: string;
  entities: string[];
  sources: Citation[];
}) {
  const label = route ? ROUTE_LABEL[route] ?? route.replace(/_/g, " ") : null;
  const hasSources = sources.length > 0;

  return (
    <div className="mb-2 space-y-2 rounded-xl border border-edge bg-panel2/60 px-3 py-2 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 font-medium text-fg2">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-brand" aria-hidden />
          {hasSources ? "Reading sources" : "Gathering evidence"}
        </span>
        {label && (
          <span className="inline-flex items-center gap-1 text-fg3">
            <Search className="h-3 w-3" aria-hidden />
            {label}
          </span>
        )}
        {!hasSources &&
          entities.slice(0, 6).map((e) => (
            <span
              key={e}
              className="rounded-full border border-edge bg-panel px-2 py-0.5 text-[11px] text-fg2 animate-pulse-soft"
            >
              {e}
            </span>
          ))}
      </div>

      {hasSources && (
        <div className="flex flex-wrap gap-1.5">
          {sources.map((c) => {
            const color = citationColor(c.marker);
            const sm = scoreStrength(c.score);
            return (
              <span
                key={c.marker}
                className="inline-flex max-w-[220px] items-center gap-1.5 rounded-lg border border-edge bg-panel px-2 py-1 animate-in fade-in-0"
                title={displaySource(c.source)}
              >
                <span
                  className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold"
                  style={{ color, backgroundColor: rgba(color, 0.15) }}
                >
                  {c.marker}
                </span>
                <span className="truncate text-[11px] text-fg2">{displaySource(c.source)}</span>
                {sm && c.score != null && (
                  <span className={`shrink-0 font-mono text-[10px] ${STRENGTH_META[sm].text}`}>
                    {c.score.toFixed(2)}
                  </span>
                )}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}
