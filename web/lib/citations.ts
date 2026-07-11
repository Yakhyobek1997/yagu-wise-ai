// Shared citation presentation so an inline [n] chip, its source card, and the
// bounding-box highlight in the Source Workspace all use the SAME color and the
// SAME relevance language — the "number-matched" pattern (Perplexity/NotebookLM).

// 8-hue palette — kept in lockstep with SourceWorkspaceModal's highlight palette
// so chip [n] color == highlight box color == source card accent.
export const CITATION_PALETTE = [
  "rgb(59,130,246)", // blue
  "rgb(16,185,129)", // emerald
  "rgb(245,158,11)", // amber
  "rgb(139,92,246)", // violet
  "rgb(236,72,153)", // pink
  "rgb(14,165,233)", // sky
  "rgb(251,191,36)", // yellow
  "rgb(239,68,68)", // red
] as const;

/** Stable color for citation marker n (1-indexed). */
export function citationColor(marker: number): string {
  const i = (Math.max(1, marker) - 1) % CITATION_PALETTE.length;
  return CITATION_PALETTE[i];
}

export type Strength = "high" | "medium" | "low";

/** Map a 0–1 retrieval score to an evidence-strength band (same thresholds as
 *  EvidencePaths ScoreDot so the whole app agrees on what "strong" means). */
export function scoreStrength(score?: number | null): Strength | null {
  if (score == null || score <= 0) return null;
  if (score >= 0.7) return "high";
  if (score >= 0.4) return "medium";
  return "low";
}

export const STRENGTH_META: Record<Strength, { label: string; dot: string; text: string }> = {
  high: { label: "High relevance", dot: "bg-ok", text: "text-ok" },
  medium: { label: "Medium relevance", dot: "bg-warn", text: "text-warn" },
  low: { label: "Low relevance", dot: "bg-bad", text: "text-bad" },
};
