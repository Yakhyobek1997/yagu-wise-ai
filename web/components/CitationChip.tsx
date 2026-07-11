"use client";
import * as HoverCard from "@radix-ui/react-hover-card";
import { FileText, ArrowUpRight } from "lucide-react";
import type { Citation } from "@/lib/api";
import { citationColor, scoreStrength, STRENGTH_META } from "@/lib/citations";
import { displaySource } from "@/lib/format";

function locatorText(c: Citation): string {
  if (c.speaker || c.start_s != null) {
    const t = (s?: number | null) =>
      s == null ? "" : `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
    const range = c.start_s != null ? `${t(c.start_s)}–${t(c.end_s)}` : "";
    return [c.speaker, range].filter(Boolean).join(" · ");
  }
  if (c.page != null) return `p.${c.page}`;
  return "";
}

function rgba(rgb: string, a: number): string {
  return rgb.replace("rgb(", "rgba(").replace(")", `,${a})`);
}

/** Inline, number-matched, hover-previewable citation marker `[n]`.
 *  Click opens the Source Workspace at this citation. */
export function CitationChip({
  citation,
  onOpen,
}: {
  citation: Citation;
  onOpen?: (marker: number) => void;
}) {
  const color = citationColor(citation.marker);
  const strength = scoreStrength(citation.score);
  const sm = strength ? STRENGTH_META[strength] : null;
  const loc = locatorText(citation);

  return (
    <HoverCard.Root openDelay={120} closeDelay={80}>
      <HoverCard.Trigger asChild>
        <button
          type="button"
          onClick={() => onOpen?.(citation.marker)}
          aria-label={`Citation ${citation.marker}: ${displaySource(citation.source)}${loc ? `, ${loc}` : ""}`}
          className="mx-0.5 inline-flex h-[1.15em] min-w-[1.15em] translate-y-[-0.15em] items-center justify-center rounded-[0.35em] border px-[0.3em] align-baseline text-[0.7em] font-semibold leading-none transition hover:brightness-110"
          style={{ color, borderColor: rgba(color, 0.5), backgroundColor: rgba(color, 0.12) }}
        >
          {citation.marker}
        </button>
      </HoverCard.Trigger>
      <HoverCard.Portal>
        <HoverCard.Content
          side="top"
          align="start"
          sideOffset={6}
          collisionPadding={12}
          className="z-[220] w-72 rounded-xl border border-edge bg-panel p-3 text-left shadow-lg data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
        >
          <div className="flex items-start gap-2">
            <span
              className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold"
              style={{ color, backgroundColor: rgba(color, 0.15) }}
            >
              {citation.marker}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5 text-sm font-medium text-fg">
                <FileText className="h-3.5 w-3.5 shrink-0 text-fg3" aria-hidden />
                <span className="truncate" title={displaySource(citation.source)}>
                  {displaySource(citation.source)}
                </span>
              </div>
              {loc && <div className="mt-0.5 font-mono text-xs text-fg3">{loc}</div>}
            </div>
          </div>

          {(sm || citation.method) && (
            <div className="mt-2 flex items-center gap-2 border-t border-edge/60 pt-2">
              {sm && citation.score != null && (
                <span className="inline-flex items-center gap-1.5 text-xs">
                  <span className={`h-2 w-2 rounded-full ${sm.dot}`} aria-hidden />
                  <span className={sm.text}>{sm.label}</span>
                  <span className="font-mono text-fg3">{citation.score.toFixed(2)}</span>
                </span>
              )}
              {citation.method && (
                <span className="tag ml-auto font-mono text-[10px] uppercase">{citation.method}</span>
              )}
            </div>
          )}

          {onOpen && (
            <button
              type="button"
              onClick={() => onOpen(citation.marker)}
              className="mt-2.5 inline-flex w-full items-center justify-center gap-1.5 rounded-lg border border-edge bg-panel2 px-2.5 py-1.5 text-xs font-medium text-fg2 transition hover:border-edge2 hover:text-fg"
            >
              Open in Source Workspace
              <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
            </button>
          )}
          <HoverCard.Arrow className="fill-panel" />
        </HoverCard.Content>
      </HoverCard.Portal>
    </HoverCard.Root>
  );
}
