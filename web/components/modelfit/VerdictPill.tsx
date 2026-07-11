import { verdictMeta } from "@/components/modelfit/verdict";
import type { Verdict } from "@/lib/modelfit";

/** Prominent will-it-run verdict pill — the ModelFit differentiator no chat
 *  competitor ships. Icon + label, colored by the estimator's verdict. */
export function VerdictPill({
  verdict,
  className = "",
}: {
  verdict?: Verdict | null;
  className?: string;
}) {
  if (!verdict) return null;
  const meta = verdictMeta(verdict);
  const Icon = meta.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${meta.badgeClass} ${className}`}
      title={meta.label}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
      {meta.label}
    </span>
  );
}
