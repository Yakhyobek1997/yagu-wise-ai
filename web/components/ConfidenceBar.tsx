"use client";

// Calibrated confidence breakdown — three orthogonal signals from the backend:
//   1. Retrieval quality  — mean chunk score / 0.7 reference (score_quality)
//   2. Citation coverage  — fraction of retrieved contexts the LLM actually cited
//   3. Semantic coverage  — cosine(query_emb, mean_context_emb) from FAIR-RAG SEA
//
// Theory: a single scalar confidence hides which signal is weak. Showing the
// breakdown lets the user decide whether to trust, rephrase, or ingest more data.

interface ConfidenceBreakdown {
  overall: number;
  scoreQuality?: number;
  citationCoverage?: number;
  semanticCoverage?: number;
}

function tier(v: number): "high" | "mid" | "low" {
  return v >= 0.65 ? "high" : v >= 0.38 ? "mid" : "low";
}

const TIER_CLS = {
  high: { bar: "bg-ok", text: "text-ok", label: "High" },
  mid:  { bar: "bg-warn", text: "text-warn", label: "Medium" },
  low:  { bar: "bg-bad", text: "text-bad", label: "Low" },
};

function Segment({
  label,
  value,
  tooltip,
}: {
  label: string;
  value: number;
  tooltip: string;
}) {
  const t = tier(value);
  const m = TIER_CLS[t];
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div title={tooltip}>
      <div className="mb-0.5 flex items-center justify-between">
        <span className="text-[10px] text-fg3">{label}</span>
        <span className={`text-[10px] font-semibold ${m.text}`}>{pct}%</span>
      </div>
      <div className="h-1 w-full rounded-full bg-edge">
        <div
          className={`h-1 rounded-full transition-all duration-500 ${m.bar}`}
          style={{ width: `${Math.max(pct, 2)}%` }}
        />
      </div>
    </div>
  );
}

export function ConfidenceBar({ data }: { data: ConfidenceBreakdown }) {
  const t = tier(data.overall);
  const m = TIER_CLS[t];
  const pct = Math.round(Math.max(0, Math.min(1, data.overall)) * 100);

  // Only show breakdown when individual signals are present.
  const hasBreakdown =
    data.scoreQuality != null ||
    data.citationCoverage != null ||
    data.semanticCoverage != null;

  return (
    <div className="mt-2.5 space-y-1.5 rounded-xl border border-edge bg-panel2/60 px-3 py-2">
      {/* overall confidence */}
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold text-fg">Answer confidence</span>
        <span className={`pill ${t === "high" ? "pill-ok" : t === "mid" ? "pill-warn" : "pill-bad"}`}>
          <span className={`inline-block h-1.5 w-1.5 rounded-full ${m.bar}`} />
          {m.label} · {pct}%
        </span>
      </div>

      {/* composite bar */}
      <div className="h-2 w-full overflow-hidden rounded-full bg-edge">
        <div
          className={`h-2 rounded-full transition-all duration-500 ${m.bar}`}
          style={{ width: `${Math.max(pct, 2)}%` }}
        />
      </div>

      {/* breakdown segments */}
      {hasBreakdown && (
        <details>
          <summary className="cursor-pointer text-[10px] text-fg3 hover:text-fg select-none">
            Breakdown ↓
          </summary>
          <div className="mt-1.5 space-y-1.5">
            {data.scoreQuality != null && (
              <Segment
                label="Retrieval quality"
                value={data.scoreQuality}
                tooltip="Mean retrieval score normalised to 0.7 reference (bge-m3 cross-encoder)"
              />
            )}
            {data.citationCoverage != null && (
              <Segment
                label="Citation coverage"
                value={data.citationCoverage}
                tooltip="Fraction of retrieved contexts the LLM actually cited in its answer"
              />
            )}
            {data.semanticCoverage != null && (
              <Segment
                label="Semantic coverage"
                value={data.semanticCoverage}
                tooltip="Cosine similarity between query embedding and mean context embedding (FAIR-RAG SEA)"
              />
            )}
          </div>
        </details>
      )}
    </div>
  );
}
