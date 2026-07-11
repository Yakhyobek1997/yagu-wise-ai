"use client";
import type { ModelFitScore } from "@/lib/modelfit";

const FIT_COLOR: Record<string, string> = {
  comfortable: "text-emerald-400",
  tight: "text-amber-400",
  not_recommended: "text-orange-400",
  impossible: "text-red-400",
};

const LABEL_SHORT: Record<string, string> = {
  "Excellent fit": "★★★",
  "Recommended": "★★",
  "Usable with limits": "★",
  "Not recommended": "–",
  "Does not fit": "✗",
};

export function ComparisonTable({ scores }: { scores: ModelFitScore[] }) {
  if (scores.length === 0) {
    return (
      <p className="text-sm text-zinc-500">
        No models scored yet. Use Model Search to select models and compute scores.
      </p>
    );
  }

  function exportCSV() {
    const header = [
      "model_id", "quantization", "overall", "hardware_fit", "speed_fit",
      "rag_fit", "task_fit", "deployment_fit", "label", "vram_gb", "disk_gb",
      "tok_per_sec_measured", "fit_level",
    ].join(",");
    const rows = scores.map((s) => {
      const re = s.resource_estimate;
      return [
        JSON.stringify(s.model_id),
        s.best_quantization,
        s.overall_score,
        s.hardware_fit,
        s.speed_fit,
        s.rag_fit,
        s.task_fit,
        s.deployment_fit,
        JSON.stringify(s.label),
        re?.estimated_vram_gb ?? "",
        re?.estimated_disk_gb ?? "",
        s.benchmark?.avg_tok_per_sec ?? "",
        re?.fit_level ?? "",
      ].join(",");
    });
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "modelfit-comparison.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  function exportJSON() {
    const blob = new Blob([JSON.stringify(scores, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "modelfit-comparison.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  function exportMarkdown() {
    const header = `| Model | Quant | Score | HW | Speed | RAG | VRAM est. | Tok/s | Fit | Label |`;
    const sep    = `|-------|-------|------:|---:|------:|----:|----------:|------:|-----|-------|`;
    const rows = scores.map((s) => {
      const re   = s.resource_estimate;
      const model = s.model_id.replace(/^(ollama:|hf:|local:)/, "");
      const toks  = s.benchmark?.avg_tok_per_sec != null ? String(s.benchmark.avg_tok_per_sec) : "—";
      const vram  = re ? `${re.estimated_vram_gb} GB` : "—";
      const fit   = re?.fit_level?.replace("_", " ") ?? "unknown";
      const speed = `${Math.round(s.speed_fit)}${s.estimate_used ? "*" : ""}`;
      return `| ${model} | ${s.best_quantization} | ${Math.round(s.overall_score)} | ${Math.round(s.hardware_fit)} | ${speed} | ${Math.round(s.rag_fit)} | ${vram} | ${toks} | ${fit} | ${s.label} |`;
    });
    const md = [`## Auralynq ModelFit Comparison`, ``, header, sep, ...rows, ``, `\\* speed score uses estimates — run benchmark for measured tok/s`].join("\n");
    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "modelfit-comparison.md";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2 justify-end">
        <button
          onClick={exportCSV}
          className="px-3 py-1 text-xs rounded border border-zinc-700 text-zinc-400 hover:text-zinc-200"
        >
          Export CSV
        </button>
        <button
          onClick={exportJSON}
          className="px-3 py-1 text-xs rounded border border-zinc-700 text-zinc-400 hover:text-zinc-200"
        >
          Export JSON
        </button>
        <button
          onClick={exportMarkdown}
          className="px-3 py-1 text-xs rounded border border-zinc-700 text-zinc-400 hover:text-zinc-200"
        >
          Export Markdown
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs text-zinc-300 border-collapse">
          <thead>
            <tr className="text-left text-[10px] text-zinc-500 border-b border-zinc-800">
              <th className="pb-2 pr-3">Model</th>
              <th className="pb-2 pr-3">Quant</th>
              <th className="pb-2 pr-3 text-right">Score</th>
              <th className="pb-2 pr-3 text-right">HW</th>
              <th className="pb-2 pr-3 text-right">Speed</th>
              <th className="pb-2 pr-3 text-right">RAG</th>
              <th className="pb-2 pr-3">VRAM est.</th>
              <th className="pb-2 pr-3">Disk est.</th>
              <th className="pb-2 pr-3">Tok/s</th>
              <th className="pb-2 pr-3">Fit</th>
              <th className="pb-2">Label</th>
            </tr>
          </thead>
          <tbody>
            {scores.map((s) => {
              const re = s.resource_estimate;
              return (
                <tr key={s.model_id} className="border-b border-zinc-800/40 hover:bg-zinc-800/30">
                  <td className="py-1.5 pr-3 font-mono text-zinc-100 max-w-[160px] truncate">
                    {s.model_id.replace(/^(ollama:|hf:|local:)/, "")}
                  </td>
                  <td className="py-1.5 pr-3 font-mono">{s.best_quantization}</td>
                  <td className="py-1.5 pr-3 text-right font-bold text-zinc-100">
                    {Math.round(s.overall_score)}
                  </td>
                  <td className="py-1.5 pr-3 text-right">{Math.round(s.hardware_fit)}</td>
                  <td className="py-1.5 pr-3 text-right">
                    {Math.round(s.speed_fit)}
                    {s.estimate_used && <span className="text-zinc-600 ml-0.5">*</span>}
                  </td>
                  <td className="py-1.5 pr-3 text-right">{Math.round(s.rag_fit)}</td>
                  <td className="py-1.5 pr-3 font-mono">
                    {re ? `${re.estimated_vram_gb} GB` : "—"}
                    <span className="text-zinc-600 ml-0.5">est.</span>
                  </td>
                  <td className="py-1.5 pr-3 font-mono">
                    {re ? `${re.estimated_disk_gb} GB` : "—"}
                  </td>
                  <td className="py-1.5 pr-3 font-mono">
                    {s.benchmark?.avg_tok_per_sec != null ? (
                      <span className="text-emerald-400">{s.benchmark.avg_tok_per_sec}</span>
                    ) : (
                      <span className="text-zinc-600 italic">not run</span>
                    )}
                  </td>
                  <td className={`py-1.5 pr-3 font-mono ${FIT_COLOR[re?.fit_level ?? ""] ?? ""}`}>
                    {re?.fit_level?.replace("_", " ") ?? "unknown"}
                  </td>
                  <td className="py-1.5 text-zinc-300">
                    {LABEL_SHORT[s.label] ?? ""} {s.label}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="text-[10px] text-zinc-600 mt-1">
          * speed score uses estimates — run benchmark for measured tok/s
        </p>
      </div>
    </div>
  );
}
