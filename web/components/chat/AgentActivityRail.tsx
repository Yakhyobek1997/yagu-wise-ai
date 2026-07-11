"use client";
import {
  Circle, ArrowRight, Search, Zap, Library, ScanSearch, ArrowUpRight, Key,
  Share2, ArrowUpDown, CheckCircle2, PenLine, Link2, Check, Ban, X, Inbox, Info,
  Bot, CornerDownLeft, type LucideIcon,
} from "lucide-react";
import { TraceStep } from "@/lib/api";

export type AgentPhase =
  | "idle"
  | "query_received"
  | "intent_classified"
  | "algorithm_selected"
  | "corpus_check"
  | "retrieval_started"
  | "vector_hits"
  | "keyword_hits"
  | "graph_expansion"
  | "reranking"
  | "evidence_check"
  | "generating"
  | "citation_validation"
  | "done"
  | "abstained"
  | "error"
  | "corpus_empty"
  | "system_route";

export interface AgentActivity {
  phase: AgentPhase;
  route?: string;
  algorithm?: string;
  status?: string;
  step?: string;
  retrievalCount?: number;
  coverage?: number;
  provider?: string;
  latencyMs?: number;
  warnings?: string[];
  fallback?: string | null;
  riskLevel?: "none" | "low" | "medium" | "high";
  citationValid?: boolean;
  confidence?: number;
  error?: string;
  vectorHits?: number;
  keywordHits?: number;
  graphHits?: number;
}

const PHASE_LABELS: Record<AgentPhase, string> = {
  idle: "Ready",
  query_received: "Query received",
  intent_classified: "Intent classified",
  algorithm_selected: "Algorithm selected",
  corpus_check: "Checking corpus",
  retrieval_started: "Retrieval started",
  vector_hits: "Vector search",
  keyword_hits: "Keyword search",
  graph_expansion: "Graph expansion",
  reranking: "Reranking",
  evidence_check: "Evidence check",
  generating: "Generating answer",
  citation_validation: "Validating citations",
  done: "Done",
  abstained: "Abstained",
  error: "Error",
  corpus_empty: "No corpus",
  system_route: "System route",
};

const PHASE_ICONS: Record<AgentPhase, LucideIcon> = {
  idle: Circle,
  query_received: ArrowRight,
  intent_classified: Search,
  algorithm_selected: Zap,
  corpus_check: Library,
  retrieval_started: ScanSearch,
  vector_hits: ArrowUpRight,
  keyword_hits: Key,
  graph_expansion: Share2,
  reranking: ArrowUpDown,
  evidence_check: CheckCircle2,
  generating: PenLine,
  citation_validation: Link2,
  done: Check,
  abstained: Ban,
  error: X,
  corpus_empty: Inbox,
  system_route: Info,
};

const RISK_CLS: Record<string, string> = {
  none: "text-ok",
  low: "text-ok",
  medium: "text-warn",
  high: "text-bad",
};

const RISK_LABEL: Record<string, string> = {
  none: "none",
  low: "low",
  medium: "medium",
  high: "high",
};

function RiskBadge({ risk }: { risk?: string }) {
  if (!risk || risk === "none") return null;
  return (
    <span className={`tag border-current ${RISK_CLS[risk] || "text-fg3"}`}>
      risk · {RISK_LABEL[risk] || risk}
    </span>
  );
}

function AlgorithmBadge({ algorithm }: { algorithm?: string }) {
  if (!algorithm) return null;
  return (
    <span className="tag border-brand/40 text-brand">
      {algorithm.replace(/_/g, " ")}
    </span>
  );
}

function AgentStepBadge({ phase, active }: { phase: AgentPhase; active: boolean }) {
  const Icon = PHASE_ICONS[phase];
  const label = PHASE_LABELS[phase];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium transition-colors ${
        active
          ? "border-brand/50 bg-brand/10 text-brand"
          : "border-edge bg-panel2 text-fg3"
      }`}
    >
      <Icon aria-hidden className={`h-3 w-3 ${active ? "animate-pulse-soft" : ""}`} />
      {label}
    </span>
  );
}

function TraceMiniTimeline({ steps, active }: { steps: TraceStep[]; active: boolean }) {
  if (!steps.length) return null;
  const total = steps.reduce((a, s) => a + s.duration_ms, 0);
  const max = Math.max(...steps.map((s) => s.duration_ms), 1);
  return (
    <div className="mt-2 space-y-1">
      {steps.slice(0, 6).map((s) => (
        <div key={s.id} className="flex items-center gap-1.5 text-[10px]">
          <span className={`w-16 shrink-0 truncate text-fg3`}>{s.label}</span>
          <div className="h-1 flex-1 overflow-hidden rounded-full bg-edge">
            <div
              className={`h-1 rounded-full transition-all ${
                s.status === "failed" ? "bg-bad" : s.status === "warning" ? "bg-warn" : "bg-brand"
              }`}
              style={{ width: `${Math.max((s.duration_ms / max) * 100, 4)}%` }}
            />
          </div>
          <span className="w-10 shrink-0 text-right text-fg3">{s.duration_ms.toFixed(0)}ms</span>
        </div>
      ))}
      {total > 0 && (
        <div className="text-right text-[10px] text-fg3">{total.toFixed(0)}ms total</div>
      )}
    </div>
  );
}

export function AgentActivityRail({
  activity,
  traceSteps,
  streaming,
}: {
  activity: AgentActivity;
  traceSteps: TraceStep[];
  streaming: boolean;
}) {
  const { phase, route, algorithm, coverage, provider, latencyMs, warnings, fallback, riskLevel, confidence, error, vectorHits, keywordHits, graphHits } = activity;

  const isIdle = phase === "idle";
  const isDone = phase === "done" || phase === "abstained" || phase === "error" || phase === "system_route";

  return (
    <div className="rounded-xl border border-edge bg-panel2/80 p-3 text-sm">
      {/* header row */}
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-fg3">Agent Activity</span>
        <span
          className={`pill ${
            isIdle
              ? "pill-neutral"
              : streaming
              ? "pill-ok"
              : phase === "error"
              ? "pill-bad"
              : phase === "abstained"
              ? "pill-warn"
              : "pill-ok"
          }`}
        >
          <span
            className={`inline-block h-1.5 w-1.5 rounded-full ${
              isIdle
                ? "bg-fg3"
                : streaming
                ? "animate-pulse-soft bg-ok"
                : phase === "error"
                ? "bg-bad"
                : phase === "abstained"
                ? "bg-warn"
                : "bg-ok"
            }`}
          />
          {isIdle ? "idle" : streaming ? "running" : isDone ? "done" : "ready"}
        </span>
      </div>

      {/* idle state */}
      {isIdle && (
        <p className="text-xs text-fg3">
          Ready — ask a question to see agent activity.
        </p>
      )}

      {/* corpus empty state */}
      {phase === "corpus_empty" && (
        <p className="text-xs text-fg3">
          No corpus indexed — upload documents to enable retrieval.
        </p>
      )}

      {/* active / done state */}
      {!isIdle && phase !== "corpus_empty" && (
        <div className="space-y-2">
          {/* current step */}
          <div className="flex flex-wrap items-center gap-1.5">
            <AgentStepBadge phase={phase} active={streaming} />
            {algorithm && <AlgorithmBadge algorithm={algorithm} />}
            {route && route !== algorithm && (
              <span className="tag">route · {route}</span>
            )}
          </div>

          {/* metrics row */}
          <div className="flex flex-wrap gap-1.5 text-[11px]">
            {vectorHits != null && vectorHits > 0 && (
              <span className="tag"><ArrowUpRight className="h-3 w-3" aria-hidden /> {vectorHits} vectors</span>
            )}
            {keywordHits != null && keywordHits > 0 && (
              <span className="tag"><Key className="h-3 w-3" aria-hidden /> {keywordHits} keywords</span>
            )}
            {graphHits != null && graphHits > 0 && (
              <span className="tag"><Share2 className="h-3 w-3" aria-hidden /> {graphHits} graph</span>
            )}
            {coverage != null && (
              <span className={`tag ${coverage >= 0.6 ? "text-ok" : coverage >= 0.3 ? "text-warn" : "text-bad"}`}>
                cov · {Math.round(coverage * 100)}%
              </span>
            )}
            {confidence != null && isDone && (
              <span className={`tag ${confidence >= 0.6 ? "text-ok" : confidence >= 0.3 ? "text-warn" : "text-bad"}`}>
                conf · {confidence.toFixed(2)}
              </span>
            )}
            {provider && <span className="tag"><Bot className="h-3 w-3" aria-hidden /> {provider}</span>}
            {latencyMs != null && isDone && (
              <span className="tag">{latencyMs.toFixed(0)}ms</span>
            )}
            <RiskBadge risk={riskLevel} />
          </div>

          {/* fallback / warnings */}
          {fallback && (
            <p className="inline-flex items-center gap-1 text-[11px] text-warn">
              <CornerDownLeft className="h-3 w-3" aria-hidden /> Fell back to {fallback.replace(/_/g, " ")}
            </p>
          )}
          {warnings && warnings.length > 0 && (
            <div className="flex flex-col gap-0.5">
              {warnings.slice(0, 2).map((w, i) => (
                <span key={i} className="text-[10px] text-warn">{w.slice(0, 60)}</span>
              ))}
            </div>
          )}
          {error && (
            <p className="rounded border border-bad/30 bg-bad/10 p-1.5 text-[11px] text-bad">
              {error.slice(0, 100)}
            </p>
          )}

          {/* mini trace timeline — only when done */}
          {isDone && traceSteps.length > 0 && (
            <TraceMiniTimeline steps={traceSteps} active={streaming} />
          )}

          {/* abstained note */}
          {phase === "abstained" && (
            <p className="inline-flex items-center gap-1 text-[11px] text-warn">
              <Ban className="h-3 w-3 shrink-0" aria-hidden /> Insufficient evidence — Auralynq abstained rather than hallucinate.
            </p>
          )}

          {/* system route note */}
          {phase === "system_route" && (
            <p className="text-[11px] text-fg3">
              ℹ Answered from system metadata — retrieval skipped.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
