"use client";
import { useEffect, useRef, useState } from "react";
import { fetchEstimate, type ResourceEstimate } from "@/lib/modelfit";
import { VerdictPill } from "@/components/modelfit/VerdictPill";

const CTX_MIN = 2048;
const CTX_MAX = 32768;
const CTX_STEP = 2048;

function fmtCtx(n: number): string {
  return n >= 1024 ? `${Math.round(n / 1024)}K` : `${n}`;
}

/**
 * Live memory planner (LM Studio's best interaction): drag the context length
 * and watch the estimated VRAM + will-it-run verdict update. Debounce-calls the
 * authoritative backend estimator (never a client-side guess) so the numbers
 * stay honest — no model is touched, this is pure estimation.
 */
export function MemoryPlanner({
  modelId,
  paramsB,
  quantization,
  initial,
}: {
  modelId: string;
  paramsB: number;
  quantization: string;
  initial: ResourceEstimate | null;
}) {
  const [ctx, setCtx] = useState(initial?.context_tokens ?? 4096);
  const [est, setEst] = useState<ResourceEstimate | null>(initial);
  const [loading, setLoading] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setLoading(true);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      fetchEstimate(modelId, paramsB, quantization, ctx)
        .then(setEst)
        .catch(() => {})
        .finally(() => setLoading(false));
    }, 250);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [ctx, modelId, paramsB, quantization]);

  const vram = est?.estimated_vram_gb ?? 0;
  const headroom = est?.headroom_gb;
  const avail = headroom != null ? vram + headroom : null;
  const pct = avail && avail > 0 ? Math.min(100, (vram / avail) * 100) : null;
  const barCol = pct == null ? "bg-sky-500" : pct > 90 ? "bg-red-500" : pct > 75 ? "bg-amber-500" : "bg-sky-500";

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Memory planner</p>
        {est?.verdict && <VerdictPill verdict={est.verdict} />}
      </div>

      <div className="flex items-center justify-between text-xs">
        <span className="text-zinc-500">Context length</span>
        <span className="font-mono text-zinc-200">{fmtCtx(ctx)} tokens</span>
      </div>
      <input
        type="range"
        min={CTX_MIN}
        max={CTX_MAX}
        step={CTX_STEP}
        value={ctx}
        onChange={(e) => setCtx(Number(e.target.value))}
        className="w-full accent-sky-500"
        aria-label="Context length"
      />

      {pct != null && (
        <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-800">
          <div className={`h-full rounded-full transition-all duration-200 ${barCol}`} style={{ width: `${pct}%` }} />
        </div>
      )}

      <div className="flex items-center justify-between text-xs">
        <span className={`font-mono ${loading ? "text-zinc-500" : "text-zinc-200"}`}>
          ~{vram.toFixed(1)} GB{avail != null ? ` / ${avail.toFixed(1)} GB` : ""}
        </span>
        <span className="text-[10px] text-zinc-600">{loading ? "updating…" : "estimated"}</span>
      </div>
    </div>
  );
}
