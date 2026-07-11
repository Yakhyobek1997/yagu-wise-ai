import { TraceSpan, TraceStep, VisualGrounding } from "@/lib/api";

const STATUS_META: Record<string, { icon: string; cls: string; bar: string }> = {
  success: { icon: "✓", cls: "text-ok", bar: "bg-brand" },
  warning: { icon: "!", cls: "text-warn", bar: "bg-warn" },
  failed: { icon: "✕", cls: "text-bad", bar: "bg-bad" },
  skipped: { icon: "–", cls: "text-fg3", bar: "bg-edge2" },
  running: { icon: "…", cls: "text-brand", bar: "bg-brand" },
  pending: { icon: "○", cls: "text-fg3", bar: "bg-edge2" },
};

const RISK_CLS: Record<string, string> = {
  none: "text-ok",
  low: "text-ok",
  medium: "text-warn",
  high: "text-bad",
};

function _vgSteps(vg: VisualGrounding): Array<{ label: string; status: string; detail: string }> {
  const nH = vg.highlights.length;
  const nC = vg.claim_grounding.length;
  const hasImg = vg.highlights.some((h) => h.page_image_url);
  const imgCount = vg.highlights.filter((h) => h.page_image_url).length;
  return [
    {
      label: "Visual metadata lookup",
      status: nH > 0 ? "success" : "warning",
      detail: `${nH} citation${nH !== 1 ? "s" : ""} resolved`,
    },
    {
      label: "Grounding resolver",
      status: vg.visual_grounding_available ? "success" : "warning",
      detail: `stage: ${vg.grounding_stage}`,
    },
    {
      label: "Page image cache",
      status: hasImg ? "success" : "skipped",
      detail: hasImg ? `${imgCount} page${imgCount !== 1 ? "s" : ""} ready` : "no images cached",
    },
    {
      label: "Claim alignment",
      status: nC > 0 ? "success" : "skipped",
      detail: `${nC} claim${nC !== 1 ? "s" : ""} analysed`,
    },
  ];
}

export interface TraceMeta {
  route?: string;
  status?: string;
  confidence?: number;
  coverage?: number;
  elapsedMs?: number;
  phoenixUrl?: string | null;
}

function Stat({ label, value, cls }: { label: string; value: string; cls?: string }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${cls || ""}`}>{value}</div>
    </div>
  );
}

function PhoenixCard({ url }: { url?: string | null }) {
  if (url) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noreferrer"
        className="card-inset flex items-center justify-between gap-2 transition hover:border-edge2"
      >
        <div>
          <p className="text-sm font-semibold text-fg">Open in Phoenix</p>
          <p className="text-[11px] text-fg3">Full OpenTelemetry trace & spans</p>
        </div>
        <span className="pill pill-ok">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-ok" /> live ↗
        </span>
      </a>
    );
  }
  return (
    <div className="card-inset">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-fg">Phoenix tracing</p>
        <span className="pill pill-warn">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-warn" /> not connected
        </span>
      </div>
      <p className="mt-1 text-[11px] text-fg3">
        Set <code className="text-brand">AURALYNQ_TELEMETRY__PHOENIX_ENDPOINT</code> and start the
        Phoenix container to view full distributed traces.
      </p>
    </div>
  );
}

export function TracePanel({
  trace,
  steps,
  meta,
  visualGrounding,
}: {
  trace: TraceSpan[];
  steps?: TraceStep[];
  meta?: TraceMeta;
  visualGrounding?: VisualGrounding | null;
}) {
  // Prefer structured steps; fall back to raw spans so old payloads still render.
  const rows: TraceStep[] =
    steps && steps.length
      ? steps
      : (trace || []).map((s, i) => ({
          id: i,
          name: s.name,
          label: s.name,
          status: "success" as const,
          duration_ms: s.duration_ms,
          provider: (s.attributes?.provider as string) || null,
          evidence_count: null,
          warnings: [],
          attributes: s.attributes || {},
        }));

  if (!rows.length)
    return (
      <div className="space-y-3">
        <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
          <span className="text-3xl" aria-hidden>
            📊
          </span>
          <p className="text-sm font-medium text-fg">Run a query to see the trace.</p>
          <p className="max-w-xs text-xs text-fg3">
            Every step — intent, retrieval, graph expansion, reranking, sufficiency, generation —
            with status, latency and provider.
          </p>
        </div>
        <PhoenixCard url={meta?.phoenixUrl} />
      </div>
    );

  const max = Math.max(...rows.map((s) => s.duration_ms), 1);
  const total = rows.reduce((a, s) => a + s.duration_ms, 0);
  const bucket = (...keys: string[]) =>
    rows
      .filter((s) => keys.some((k) => s.name.toLowerCase().includes(k)))
      .reduce((a, s) => a + s.duration_ms, 0);
  const retrieval = bucket("retriev", "pathrag", "fus", "rerank");
  const generation = bucket("synthes");
  const abstained = meta?.status === "insufficient_evidence";
  const conf = meta?.confidence ?? 0;
  const cov = meta?.coverage ?? 0;
  const risk = abstained
    ? "none"
    : conf >= 0.6 && cov >= 0.6
      ? "low"
      : conf >= 0.4
        ? "medium"
        : "high";

  return (
    <div className="space-y-3">
      {/* summary dashboard */}
      <div className="grid grid-cols-3 gap-1.5">
        <Stat label="Total" value={`${(meta?.elapsedMs ?? total).toFixed(0)}ms`} />
        <Stat label="Retrieval" value={`${retrieval.toFixed(0)}ms`} />
        <Stat label="Generation" value={`${generation.toFixed(0)}ms`} />
        <Stat label="Coverage" value={`${Math.round(cov * 100)}%`} />
        <Stat label="Confidence" value={conf.toFixed(2)} />
        <Stat label="Hallu. risk" value={risk} cls={RISK_CLS[risk]} />
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="pill pill-neutral">route · {meta?.route || "—"}</span>
        <span className={`pill ${abstained ? "pill-warn" : "pill-ok"}`}>
          <span className={`inline-block h-1.5 w-1.5 rounded-full ${abstained ? "bg-warn" : "bg-ok"}`} />
          {abstained ? "abstained" : "answered"}
        </span>
      </div>

      {/* step timeline / waterfall */}
      <ol className="space-y-2">
        {rows.map((s) => {
          const sm = STATUS_META[s.status] || STATUS_META.success;
          return (
            <li key={s.id} className="text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="flex min-w-0 items-center gap-2">
                  <span className={`font-mono ${sm.cls}`} aria-hidden>
                    {sm.icon}
                  </span>
                  <span className="truncate text-fg">{s.label}</span>
                </span>
                <span className="shrink-0 text-fg3">{s.duration_ms.toFixed(1)}ms</span>
              </div>
              <div className="mt-1 h-1.5 w-full rounded-full bg-edge">
                <div
                  className={`h-1.5 rounded-full ${sm.bar}`}
                  style={{ width: `${Math.max((s.duration_ms / max) * 100, 3)}%` }}
                />
              </div>
              {(s.provider || s.evidence_count != null || (s.warnings && s.warnings.length > 0)) && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {s.provider && <span className="tag">provider · {s.provider}</span>}
                  {s.evidence_count != null && (
                    <span className="tag">evidence · {s.evidence_count}</span>
                  )}
                  {s.warnings?.map((w, j) => (
                    <span key={j} className="tag border-bad/40 text-bad">
                      {String(w).slice(0, 40)}
                    </span>
                  ))}
                </div>
              )}
            </li>
          );
        })}
      </ol>

      {/* Visual grounding pipeline steps */}
      {visualGrounding && (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <p className="stat-label">Visual Grounding Pipeline</p>
            <span
              className={`pill ${
                visualGrounding.grounding_stage === "span"
                  ? "pill-ok"
                  : visualGrounding.grounding_stage === "page"
                    ? "pill-warn"
                    : "pill-neutral"
              }`}
            >
              {visualGrounding.grounding_stage}
            </span>
          </div>
          <ol className="space-y-1">
            {_vgSteps(visualGrounding).map((step, i) => {
              const sm = STATUS_META[step.status] || STATUS_META.success;
              return (
                <li key={i} className="flex items-center gap-2 text-sm">
                  <span className={`shrink-0 font-mono ${sm.cls}`} aria-hidden>
                    {sm.icon}
                  </span>
                  <span className="flex-1 text-fg">{step.label}</span>
                  <span className="tag shrink-0">{step.detail}</span>
                </li>
              );
            })}
          </ol>
          {visualGrounding.warnings.length > 0 && (
            <p className="text-[11px] text-warn">{visualGrounding.warnings[0]}</p>
          )}
        </div>
      )}

      <PhoenixCard url={meta?.phoenixUrl} />
    </div>
  );
}
