import { CheckCircle2, Cpu, AlertTriangle, XCircle, type LucideIcon } from "lucide-react";
import type { Verdict } from "@/lib/modelfit";

// Shared presentation for the estimator's will-it-run verdict, so the report
// card, the pull modal, and the ranked rows all speak the same language.
// Colors are design tokens (ok/info/warn/bad) so verdicts stay correct across
// the dark / light / comfort themes — never raw palette classes.
export interface VerdictMeta {
  label: string;
  icon: LucideIcon;
  /** For a solid banner/pill background. */
  badgeClass: string;
  /** For a coloured accent / bar fill. */
  barClass: string;
  /** For a text-only accent. */
  textClass: string;
}

export const VERDICT_META: Record<Verdict, VerdictMeta> = {
  runs_great: {
    label: "Runs great",
    icon: CheckCircle2,
    badgeClass: "bg-ok/15 text-ok ring-1 ring-ok/40",
    barClass: "bg-ok",
    textClass: "text-ok",
  },
  runs_ok: {
    label: "Runs (tight fit)",
    icon: CheckCircle2,
    badgeClass: "bg-info/15 text-info ring-1 ring-info/40",
    barClass: "bg-info",
    textClass: "text-info",
  },
  runs_offload: {
    label: "Runs with CPU offload — slower",
    icon: AlertTriangle,
    badgeClass: "bg-warn/15 text-warn ring-1 ring-warn/40",
    barClass: "bg-warn",
    textClass: "text-warn",
  },
  runs_cpu: {
    label: "Runs on CPU",
    icon: Cpu,
    badgeClass: "bg-info/15 text-info ring-1 ring-info/40",
    barClass: "bg-info",
    textClass: "text-info",
  },
  runs_cpu_tight: {
    label: "Runs on CPU — low RAM headroom",
    icon: AlertTriangle,
    badgeClass: "bg-warn/15 text-warn ring-1 ring-warn/40",
    barClass: "bg-warn",
    textClass: "text-warn",
  },
  too_big: {
    label: "Too big for this machine",
    icon: XCircle,
    badgeClass: "bg-bad/15 text-bad ring-1 ring-bad/40",
    barClass: "bg-bad",
    textClass: "text-bad",
  },
};

export function verdictMeta(v: Verdict | undefined | null): VerdictMeta {
  return (v && VERDICT_META[v]) || VERDICT_META.runs_cpu;
}
