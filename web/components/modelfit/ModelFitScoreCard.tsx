"use client";
import type { ModelFitScore } from "@/lib/modelfit";

function ScoreBar({ label, value }: { label: string; value: number }) {
  const color =
    value >= 85
      ? "bg-emerald-500"
      : value >= 70
        ? "bg-sky-500"
        : value >= 50
          ? "bg-amber-500"
          : "bg-red-500";
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-zinc-400">
        <span>{label}</span>
        <span className="font-mono">{value}</span>
      </div>
      <div className="h-1.5 rounded bg-zinc-800">
        <div className={`h-full rounded ${color}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

const LABEL_COLOR: Record<string, string> = {
  "Excellent fit": "text-emerald-400",
  "Recommended": "text-sky-400",
  "Usable with limits": "text-amber-400",
  "Not recommended": "text-orange-400",
  "Does not fit": "text-red-400",
};

const FIT_LEVEL_COLOR: Record<string, string> = {
  comfortable: "text-emerald-400",
  tight: "text-amber-400",
  not_recommended: "text-orange-400",
  impossible: "text-red-400",
};

export function ModelFitScoreCard({
  score,
  showDetails = false,
}: {
  score: ModelFitScore;
  showDetails?: boolean;
}) {
  const re = score.resource_estimate;
  return (
    <div className="rounded-xl border border-zinc-700 bg-zinc-900 p-5 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-0.5">
          <div className="text-sm font-semibold text-zinc-100 truncate max-w-[200px]" title={score.model_id}>
            {score.model_id.replace(/^(ollama:|hf:|local:)/, "")}
          </div>
          <div className={`text-xs font-mono ${LABEL_COLOR[score.label] ?? "text-zinc-400"}`}>
            {score.label}
          </div>
        </div>
        <div className="text-3xl font-bold font-mono text-zinc-100 shrink-0">
          {Math.round(score.overall_score)}
        </div>
      </div>

      {/* Sub-scores */}
      <div className="space-y-2">
        <ScoreBar label="Hardware fit" value={score.hardware_fit} />
        <ScoreBar label="Speed fit" value={score.speed_fit} />
        <ScoreBar label="RAG fit" value={score.rag_fit} />
        <ScoreBar label="Task fit" value={score.task_fit} />
        <ScoreBar label="Deployment" value={score.deployment_fit} />
      </div>

      {/* Quick facts */}
      <div className="text-xs text-zinc-400 space-y-1">
        <div>
          Quantization:{" "}
          <span className="text-zinc-200 font-mono">{score.best_quantization}</span>
        </div>
        {re && (
          <>
            <div>
              Est. VRAM:{" "}
              <span className="font-mono text-zinc-200">{re.estimated_vram_gb} GB</span>
              {" "}
              <span className={`font-mono ${FIT_LEVEL_COLOR[re.fit_level] ?? ""}`}>
                ({re.fit_level.replace("_", " ")})
              </span>
            </div>
            <div>
              Rec. context:{" "}
              <span className="font-mono text-zinc-200">
                {re.recommended_context.toLocaleString()} tokens
              </span>
            </div>
          </>
        )}
        {score.benchmark?.avg_tok_per_sec != null ? (
          <div>
            Tok/s:{" "}
            <span className="font-mono text-emerald-400">
              {score.benchmark.avg_tok_per_sec} (measured)
            </span>
          </div>
        ) : (
          <div className="text-zinc-500 italic">tok/s: not measured yet</div>
        )}
        {score.estimate_used && (
          <div className="text-amber-500 italic text-[10px]">
            Speed score uses estimates — run benchmark for measured data.
          </div>
        )}
      </div>

      {/* Reason */}
      {showDetails && (
        <p className="text-xs text-zinc-400 border-t border-zinc-800 pt-3">{score.reason}</p>
      )}

      {/* Warnings */}
      {showDetails && score.warnings.length > 0 && (
        <ul className="space-y-1">
          {score.warnings.map((w, i) => (
            <li key={i} className="text-[10px] text-amber-400">
              ⚠ {w}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
