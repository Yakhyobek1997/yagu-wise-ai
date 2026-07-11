"use client";
import { useState } from "react";
import {
  ChevronRight, CheckCircle2, AlertTriangle, XCircle, MinusCircle, Loader2, Circle,
  type LucideIcon,
} from "lucide-react";
import type { TraceStep } from "@/lib/api";

const STATUS: Record<TraceStep["status"], { icon: LucideIcon; cls: string }> = {
  success: { icon: CheckCircle2, cls: "text-ok" },
  warning: { icon: AlertTriangle, cls: "text-warn" },
  failed: { icon: XCircle, cls: "text-bad" },
  skipped: { icon: MinusCircle, cls: "text-fg3" },
  running: { icon: Loader2, cls: "text-brand animate-spin" },
  pending: { icon: Circle, cls: "text-fg3" },
};

/**
 * Collapsed-by-default reasoning trace shown under an answer (Perplexity Pro
 * Search pattern): don't overload until the user is curious, then reveal the
 * per-step plan + timings on demand. Full detail still lives in the Trace tab.
 */
export function AnswerSteps({ steps }: { steps: TraceStep[] }) {
  const [open, setOpen] = useState(false);
  if (!steps?.length) return null;
  const total = steps.reduce((a, s) => a + (s.duration_ms || 0), 0);

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="inline-flex items-center gap-1.5 text-xs text-fg3 transition hover:text-fg2"
      >
        <ChevronRight className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-90" : ""}`} aria-hidden />
        {open ? "Hide" : "Show"} reasoning
        <span className="font-mono text-fg3">· {steps.length} steps · {Math.round(total)}ms</span>
      </button>
      {open && (
        <ol className="mt-1.5 space-y-1 border-l border-edge pl-3 duration-200 animate-in fade-in-0 slide-in-from-top-1">
          {steps.map((s) => {
            const st = STATUS[s.status] ?? STATUS.pending;
            const Icon = st.icon;
            return (
              <li key={s.id} className="flex items-center gap-2 text-xs">
                <Icon className={`h-3 w-3 shrink-0 ${st.cls}`} aria-hidden />
                <span className="truncate text-fg2">{s.label || s.name}</span>
                {s.evidence_count != null && s.evidence_count > 0 && (
                  <span className="shrink-0 text-fg3">· {s.evidence_count} ev</span>
                )}
                <span className="ml-auto shrink-0 font-mono text-fg3">{Math.round(s.duration_ms)}ms</span>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
