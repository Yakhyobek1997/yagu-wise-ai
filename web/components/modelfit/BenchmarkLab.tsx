"use client";
import { useState } from "react";
import type { BenchmarkPlan, BenchmarkResult } from "@/lib/modelfit";
import { fetchBenchmarkPreview, runBenchmark } from "@/lib/modelfit";

const TASKS = ["latency", "throughput", "rag", "context_stress", "abstention"];
const QUANTS = ["q2_k", "q3_k", "q4_0", "q4_k", "q5_k", "q8", "fp16"];

export function BenchmarkLab({
  defaultModelId = "",
}: {
  defaultModelId?: string;
}) {
  const [modelId, setModelId] = useState(defaultModelId);
  const [quantization, setQuantization] = useState("q4_k");
  const [task, setTask] = useState("latency");
  const [numExamples, setNumExamples] = useState(10);
  const [plan, setPlan] = useState<BenchmarkPlan | null>(null);
  const [result, setResult] = useState<BenchmarkResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<"idle" | "preview" | "running" | "done">("idle");

  async function preview() {
    if (!modelId.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const p = await fetchBenchmarkPreview(modelId.trim(), quantization, task, numExamples);
      setPlan(p);
      setPhase("preview");
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function run() {
    if (!modelId.trim()) return;
    setLoading(true);
    setError(null);
    setPhase("running");
    try {
      const r = await runBenchmark(modelId.trim(), quantization, task, numExamples);
      setResult(r);
      setPlan(null);
      setPhase("done");
    } catch (e) {
      setError(String(e));
      setPhase("preview");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      {/* Config */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="col-span-2 sm:col-span-1 space-y-1">
          <label className="text-xs text-zinc-500">Model ID</label>
          <input
            className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-sm text-zinc-100 font-mono"
            placeholder="e.g. ollama:llama3.1:8b"
            value={modelId}
            onChange={(e) => setModelId(e.target.value)}
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-zinc-500">Quantization</label>
          <select
            className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-sm text-zinc-300"
            value={quantization}
            onChange={(e) => setQuantization(e.target.value)}
          >
            {QUANTS.map((q) => (
              <option key={q} value={q}>
                {q}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-xs text-zinc-500">Task</label>
          <select
            className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-sm text-zinc-300"
            value={task}
            onChange={(e) => setTask(e.target.value)}
          >
            {TASKS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-xs text-zinc-500">Examples</label>
          <input
            type="number"
            min={1}
            max={200}
            className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-sm text-zinc-100 font-mono"
            value={numExamples}
            onChange={(e) => setNumExamples(Number(e.target.value))}
          />
        </div>
      </div>

      <div className="flex gap-2">
        <button
          onClick={preview}
          disabled={loading || !modelId.trim()}
          className="px-4 py-1.5 rounded border border-sky-700 text-sky-400 text-sm hover:bg-sky-900/30 disabled:opacity-50"
        >
          Preview (dry run)
        </button>
        {phase === "preview" && plan && (
          <button
            onClick={run}
            disabled={loading}
            className="px-4 py-1.5 rounded bg-emerald-700 hover:bg-emerald-600 text-white text-sm disabled:opacity-50"
          >
            {loading ? "Running…" : "Run benchmark"}
          </button>
        )}
      </div>

      {error && <p className="text-sm text-red-400">Error: {error}</p>}

      {/* Preview plan */}
      {plan && phase === "preview" && (
        <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4 space-y-3 text-sm">
          <p className="text-amber-400 text-xs font-semibold">DRY RUN — No benchmark has run yet</p>
          <p className="text-zinc-300 font-mono">{plan.note}</p>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs">
            <span className="text-zinc-500">Model</span>
            <span className="font-mono text-zinc-200">{plan.model_id}</span>
            <span className="text-zinc-500">Quantization</span>
            <span className="font-mono text-zinc-200">{plan.quantization}</span>
            <span className="text-zinc-500">Task</span>
            <span className="font-mono text-zinc-200">{plan.task}</span>
            <span className="text-zinc-500">Examples</span>
            <span className="font-mono text-zinc-200">{plan.num_examples}</span>
            <span className="text-zinc-500">Est. duration</span>
            <span className="font-mono text-zinc-200">{plan.estimated_duration_min} min</span>
            <span className="text-zinc-500">Requires Ollama</span>
            <span className="font-mono text-zinc-200">{plan.requires_ollama ? "Yes" : "No"}</span>
            <span className="text-zinc-500">Auto-download</span>
            <span className="font-mono text-emerald-400">Never</span>
          </div>
          {plan.warnings.map((w, i) => (
            <p key={i} className="text-xs text-amber-400">
              ⚠ {w}
            </p>
          ))}
          <div className="space-y-1">
            <p className="text-xs text-zinc-500 uppercase">Sample prompts</p>
            {plan.sample_prompts.map((p, i) => (
              <p key={i} className="text-xs text-zinc-400 italic truncate">
                "{p}"
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Running */}
      {phase === "running" && (
        <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4 text-sm text-zinc-300">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-sky-400 animate-pulse" />
            Running benchmark against {modelId}…
          </div>
          <p className="text-xs text-zinc-500 mt-1">
            This may take several minutes. No model will be downloaded.
          </p>
        </div>
      )}

      {/* Result */}
      {result && phase === "done" && (
        <BenchmarkResultCard result={result} />
      )}
    </div>
  );
}

function BenchmarkResultCard({ result }: { result: BenchmarkResult }) {
  const statusColor =
    result.status === "completed"
      ? "text-emerald-400"
      : result.status === "failed"
        ? "text-red-400"
        : "text-zinc-400";

  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs text-zinc-500 font-mono">run/{result.run_id}</span>
        <span className={`text-xs font-semibold ${statusColor}`}>{result.status}</span>
      </div>

      {result.error && (
        <p className="text-sm text-red-400">Error: {result.error}</p>
      )}

      {result.status === "completed" && (
        <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs">
          <span className="text-zinc-500">Avg tok/s</span>
          <span className="font-mono text-emerald-400">
            {result.avg_tok_per_sec != null
              ? `${result.avg_tok_per_sec} (measured)`
              : "not measured"}
          </span>
          <span className="text-zinc-500">p50 latency</span>
          <span className="font-mono text-zinc-200">
            {result.p50_latency_ms != null ? `${result.p50_latency_ms} ms` : "—"}
          </span>
          <span className="text-zinc-500">p95 latency</span>
          <span className="font-mono text-zinc-200">
            {result.p95_latency_ms != null ? `${result.p95_latency_ms} ms` : "—"}
          </span>
          <span className="text-zinc-500">TTFT</span>
          <span className="font-mono text-zinc-200">
            {result.time_to_first_token_ms != null
              ? `${result.time_to_first_token_ms} ms`
              : "—"}
          </span>
          <span className="text-zinc-500">Peak memory</span>
          <span className="font-mono text-zinc-200">
            {result.peak_memory_gb != null ? `${result.peak_memory_gb} GB` : "—"}
          </span>
          <span className="text-zinc-500">Examples</span>
          <span className="font-mono text-zinc-200">
            {result.completed_examples}/{result.num_examples}
          </span>
        </div>
      )}

      {result.warnings.map((w, i) => (
        <p key={i} className="text-xs text-amber-400">
          ⚠ {w}
        </p>
      ))}
    </div>
  );
}
