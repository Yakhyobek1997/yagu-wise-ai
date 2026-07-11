import { Citation } from "@/lib/api";
import { displaySource } from "@/lib/format";
import { citationColor, scoreStrength, STRENGTH_META } from "@/lib/citations";

// Clean, user-facing locator (page / speaker+timestamp) — never raw char spans.
function cleanLocator(c: Citation): string {
  if (c.speaker || c.start_s != null) {
    const t = (s?: number | null) => {
      if (s == null) return "";
      const m = Math.floor(s / 60);
      const sec = Math.round(s % 60);
      return `${m}:${String(sec).padStart(2, "0")}`;
    };
    const range = c.start_s != null ? `${t(c.start_s)}–${t(c.end_s)}` : "";
    return [c.speaker, range].filter(Boolean).join(" · ");
  }
  if (c.page != null) return `p.${c.page}`;
  return "";
}

function rgba(rgb: string, a: number): string {
  return rgb.replace("rgb(", "rgba(").replace(")", `,${a})`);
}

export function Citations({
  citations,
  onOpenSource,
}: {
  citations: Citation[];
  onOpenSource?: (marker: number) => void;
}) {
  if (!citations?.length) return null;
  return (
    <div className="mt-3 space-y-1.5">
      <div className="overline text-fg3">
        Sources · {citations.length}
      </div>
      <ol className="space-y-1.5">
        {citations.map((c) => {
          const loc = cleanLocator(c);
          const color = citationColor(c.marker);
          const strength = scoreStrength(c.score);
          const sm = strength ? STRENGTH_META[strength] : null;
          const clickable = !!onOpenSource;
          const Tag = clickable ? "button" : "div";
          return (
            <li key={c.marker}>
              <Tag
                {...(clickable
                  ? {
                      type: "button" as const,
                      onClick: () => onOpenSource!(c.marker),
                      "aria-label": `Open source ${c.marker}: ${displaySource(c.source)}`,
                    }
                  : {})}
                className={`flex w-full items-center gap-2.5 rounded-lg border border-edge bg-panel2 px-2.5 py-1.5 text-left text-sm transition ${
                  clickable ? "hover:border-edge2 hover:bg-panel" : ""
                }`}
              >
                <span
                  className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-semibold"
                  style={{ color, backgroundColor: rgba(color, 0.15) }}
                >
                  {c.marker}
                </span>
                <span className="min-w-0 flex-1 truncate text-fg" title={displaySource(c.source)}>
                  {displaySource(c.source)}
                  {loc && <span className="ml-1 font-mono text-xs text-fg3">· {loc}</span>}
                </span>
                {sm && c.score != null && (
                  <span className="inline-flex shrink-0 items-center gap-1" title={`${sm.label} · retrieval score ${c.score.toFixed(2)}`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${sm.dot}`} aria-hidden />
                    <span className="font-mono text-xs text-fg3">{c.score.toFixed(2)}</span>
                  </span>
                )}
                {c.method && (
                  <span className="tag hidden shrink-0 font-mono text-[10px] uppercase sm:inline-flex">
                    {c.method}
                  </span>
                )}
              </Tag>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
