import { Citation, PathEvidence, VisualGrounding } from "@/lib/api";
import { coverageTier, displaySource } from "@/lib/format";

const TIER_META = {
  strong: { label: "Strong evidence", cls: "evidence-strong", bar: "bg-ok", dot: "bg-ok", pill: "pill-ok" },
  weak: { label: "Weak evidence", cls: "evidence-weak", bar: "bg-warn", dot: "bg-warn", pill: "pill-warn" },
  none: { label: "Insufficient evidence", cls: "evidence-none", bar: "bg-bad", dot: "bg-bad", pill: "pill-bad" },
} as const;

function CoverageHeader({ coverage }: { coverage: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, coverage)) * 100);
  const tier = coverageTier(coverage);
  const m = TIER_META[tier];
  return (
    <div className={`rounded-xl border p-3 ${m.cls}`}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-fg">Evidence coverage</span>
        <span className={`pill ${m.pill}`}>
          <span className={`inline-block h-1.5 w-1.5 rounded-full ${m.dot}`} />
          {m.label}
        </span>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <div className="h-2 flex-1 rounded-full bg-edge">
          <div className={`h-2 rounded-full ${m.bar}`} style={{ width: `${Math.max(pct, 2)}%` }} />
        </div>
        <span className="text-sm font-bold text-fg">{pct}%</span>
      </div>
      <p className="mt-1.5 text-[11px] text-fg3">
        Share of the question&apos;s key terms supported by retrieved evidence.
      </p>
    </div>
  );
}

function Breakdown({
  vector,
  graph,
  citations,
}: {
  vector: number;
  graph: number;
  citations: number;
}) {
  const items = [
    { label: "Vector hits", value: vector, tint: "text-brand" },
    { label: "Graph paths", value: graph, tint: "text-accent" },
    { label: "Reranked", value: citations, tint: "text-brand2" },
    { label: "Citations", value: citations, tint: "text-ok" },
  ];
  return (
    <div className="grid grid-cols-4 gap-1.5">
      {items.map((i) => (
        <div key={i.label} className="stat text-center">
          <div className={`text-base font-bold ${i.tint}`}>{i.value}</div>
          <div className="stat-label">{i.label}</div>
        </div>
      ))}
    </div>
  );
}

// "Why selected" copy by source type — explains the evidence to the user.
function whySelected(c: Citation): string {
  if (c.source_type === "audio") return "Top-ranked transcript segment matching your question.";
  if (c.source_type === "web") return "High-relevance passage from a retrieved web source.";
  if (c.method === "pathrag") return "Path-traversal evidence from the relational knowledge graph.";
  return "High-relevance passage from hybrid retrieval, kept after reranking.";
}

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
  if (c.page != null) return `Page ${c.page}`;
  return "";
}

function ScoreDot({ score }: { score: number }) {
  const cls =
    score >= 0.7 ? "bg-ok" : score >= 0.4 ? "bg-warn" : "bg-bad";
  const label =
    score >= 0.7 ? "High relevance" : score >= 0.4 ? "Medium relevance" : "Low relevance";
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${cls}`}
      title={`Retrieval score: ${score.toFixed(2)} — ${label}`}
      aria-label={label}
    />
  );
}

function MethodPill({ method }: { method: string }) {
  const cls =
    method === "pathrag"
      ? "border-accent/40 text-accent"
      : method === "hybrid"
        ? "border-brand/40 text-brand"
        : "border-edge text-fg3";
  return <span className={`tag shrink-0 ${cls}`}>{method}</span>;
}

function CitationCard({ c, onOpenSource, hasVisualGrounding }: {
  c: Citation;
  onOpenSource?: (citationId: string) => void;
  hasVisualGrounding?: boolean;
}) {
  const loc = cleanLocator(c);
  const hasScore = c.score != null && c.score > 0;
  const hasMethod = c.method != null && c.method !== "unknown";
  return (
    <li className="evidence-card">
      <div className="flex items-start gap-2">
        <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand2/15 text-xs font-semibold text-brand2">
          {c.marker}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-sm font-semibold text-fg" title={displaySource(c.source)}>
              {displaySource(c.source)}
            </span>
            <div className="flex shrink-0 items-center gap-1.5">
              {hasScore && <ScoreDot score={c.score!} />}
              {hasMethod && <MethodPill method={c.method!} />}
              <span className="pill pill-neutral">{c.source_type}</span>
            </div>
          </div>
          {loc && <p className="mt-0.5 text-xs text-fg3">{loc}</p>}
          {hasScore && (
            <div className="mt-1 flex items-center gap-1.5">
              <div className="h-1 w-20 rounded-full bg-edge">
                <div
                  className={`h-1 rounded-full ${c.score! >= 0.7 ? "bg-ok" : c.score! >= 0.4 ? "bg-warn" : "bg-bad"}`}
                  style={{ width: `${Math.round(c.score! * 100)}%` }}
                />
              </div>
              <span className="text-[10px] text-fg3">{Math.round(c.score! * 100)}% relevance</span>
            </div>
          )}
          <p className="mt-1.5 text-xs italic text-fg2">{whySelected(c)}</p>
          <div className="mt-1.5 flex items-center gap-2">
            {onOpenSource && (
              <button
                className="tag border-brand/40 text-brand hover:border-brand hover:bg-brand/10 transition text-[11px]"
                onClick={() => onOpenSource(String(c.marker))}
                title="Open source page in Source View"
              >
                {hasVisualGrounding ? "📄 Source" : "📄 Source (page-level)"}
              </button>
            )}
          </div>
          {c.source && c.source !== displaySource(c.source) && (
            <details className="mt-1.5">
              <summary className="cursor-pointer text-[10px] text-fg3 hover:text-fg2">
                Debug · raw source
              </summary>
              <p className="mt-0.5 break-all font-mono text-[10px] text-fg3">{c.source}</p>
            </details>
          )}
        </div>
      </div>
    </li>
  );
}

function Section({
  title,
  count,
  children,
  open = true,
}: {
  title: string;
  count?: number;
  children: React.ReactNode;
  open?: boolean;
}) {
  return (
    <details open={open} className="card-inset">
      <summary className="cursor-pointer text-sm font-semibold text-fg">
        {title}
        {typeof count === "number" && (
          <span className="ml-2 rounded-full bg-edge px-2 py-0.5 text-xs text-fg2">{count}</span>
        )}
      </summary>
      <div className="mt-2">{children}</div>
    </details>
  );
}

export function EvidencePaths({
  paths,
  seeds,
  coverage = 0,
  citations = [],
  visualGrounding,
  onOpenSource,
  onOpenSourceTab,
}: {
  paths: PathEvidence[];
  seeds: string[];
  coverage?: number;
  citations?: Citation[];
  visualGrounding?: VisualGrounding | null;
  onOpenSource?: (citationId: string) => void;
  onOpenSourceTab?: () => void;
}) {
  const hasAnything = paths?.length || citations?.length || seeds?.length;
  if (!hasAnything)
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
        <span className="text-3xl" aria-hidden>
          🔍
        </span>
        <p className="text-sm font-medium text-fg">Ask a question to see the evidence trail.</p>
        <p className="max-w-xs text-xs text-fg3">
          Vector hits, PathRAG graph paths, and the exact citations an answer was grounded on appear
          here — with a coverage score and per-source reasoning.
        </p>
      </div>
    );

  const vgAvailable = visualGrounding?.visual_grounding_available;
  const vgStage = visualGrounding?.grounding_stage ?? "unavailable";

  return (
    <div className="space-y-3">
      <CoverageHeader coverage={coverage} />
      <Breakdown
        vector={citations.length}
        graph={paths?.length || 0}
        citations={citations.length}
      />
      {/* Visual grounding status bar */}
      {visualGrounding !== undefined && visualGrounding !== null && (
        <div className={`rounded-xl border px-3 py-2 flex items-center justify-between gap-2 ${vgAvailable ? "border-brand/30 bg-brand/5" : "border-edge bg-surface"}`}>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-fg">Visual grounding</span>
            <span className={`pill ${vgStage === "span" ? "pill-ok" : vgStage === "page" ? "pill-warn" : "pill-neutral"}`}>
              {vgStage}
            </span>
          </div>
          {vgAvailable && onOpenSourceTab && (
            <button
              className="tag border-brand/40 text-brand hover:border-brand hover:bg-brand/10 transition text-[11px]"
              onClick={onOpenSourceTab}
            >
              Open Source View →
            </button>
          )}
          {!vgAvailable && (
            <span className="text-[11px] text-fg3">Reindex to enable</span>
          )}
        </div>
      )}

      <Section title="Citations" count={citations.length} open={citations.length > 0}>
        {citations.length ? (
          <ol className="space-y-2">
            {citations.map((c) => (
              <CitationCard
                key={c.marker}
                c={c}
                onOpenSource={onOpenSource}
                hasVisualGrounding={visualGrounding?.visual_grounding_available}
              />
            ))}
          </ol>
        ) : (
          <p className="text-xs text-fg3">No citations attached to the answer.</p>
        )}
      </Section>

      <Section title="Graph evidence · PathRAG" count={paths?.length || 0} open={!!paths?.length}>
        {seeds?.length > 0 && (
          <div className="mb-2 flex flex-wrap items-center gap-1">
            <span className="text-xs text-fg3">seeds:</span>
            {seeds.map((s) => (
              <span key={s} className="tag border-brand2/30 text-brand2">
                {s}
              </span>
            ))}
          </div>
        )}
        {paths?.length ? (
          <div className="space-y-2">
            {paths.map((p, i) => {
              const hasPpr = p.ppr_score != null && p.ppr_score > 0;
              const relColor =
                p.reliability >= 0.7 ? "bg-ok" : p.reliability >= 0.4 ? "bg-accent" : "bg-warn";
              return (
              <div key={i} className="evidence-card">
                {/* Chain: Node → relation → Node → ... */}
                <div className="flex flex-wrap items-center gap-1 text-sm">
                  {p.nodes.map((n, j) => (
                    <span key={j} className="flex items-center gap-1">
                      <span className="rounded-md bg-edge px-2 py-0.5 font-medium text-fg">{n}</span>
                      {j < p.relations.length && (
                        <span className="flex items-center gap-0.5 text-xs text-accent">
                          <span>—</span>
                          <span className="italic">{p.relations[j]}</span>
                          <span>→</span>
                        </span>
                      )}
                    </span>
                  ))}
                </div>
                {/* Reliability bar + PPR authority badge */}
                <div className="mt-2 flex items-center gap-2">
                  <div className="h-1.5 flex-1 rounded-full bg-edge">
                    <div
                      className={`h-1.5 rounded-full ${relColor}`}
                      style={{ width: `${Math.round(p.reliability * 100)}%` }}
                    />
                  </div>
                  <span className="text-xs text-fg3">
                    rel {p.reliability.toFixed(2)}
                  </span>
                  {hasPpr && (
                    <span
                      className="tag border-brand2/40 text-brand2"
                      title="Personalised PageRank terminal-node authority"
                    >
                      ppr {p.ppr_score!.toFixed(2)}
                    </span>
                  )}
                </div>
              </div>
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-fg3">
            No graph paths — this was answered by vector retrieval alone.
          </p>
        )}
      </Section>

      <p className="px-1 text-[11px] text-fg3">
        Passages are ranked by hybrid (dense + sparse) retrieval, expanded along reliable graph
        relations, reranked, then only the cited sources are kept.
      </p>
    </div>
  );
}
