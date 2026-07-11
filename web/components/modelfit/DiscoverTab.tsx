"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { DiscoverEntry, DiscoverHardware, DiscoverResult } from "@/lib/modelfit";
import { discoverModels } from "@/lib/modelfit";
import { SystemReport } from "@/components/modelfit/SystemReport";
import { PullConfirmModal } from "@/components/modelfit/PullConfirmModal";
import { VerdictPill } from "@/components/modelfit/VerdictPill";
import { MemoryPlanner } from "@/components/modelfit/MemoryPlanner";

// ── Helpers ───────────────────────────────────────────────────────────────────

function scoreColor(s: number) {
  if (s >= 90) return { ring: "ring-emerald-500/60", text: "text-emerald-400", bg: "bg-emerald-500" };
  if (s >= 80) return { ring: "ring-sky-500/60",     text: "text-sky-400",     bg: "bg-sky-500"     };
  if (s >= 70) return { ring: "ring-amber-500/60",   text: "text-amber-400",   bg: "bg-amber-500"   };
  return          { ring: "ring-red-500/60",          text: "text-red-400",     bg: "bg-red-500"     };
}

const FIT_PILL: Record<string, string> = {
  comfortable:    "bg-emerald-900/50 text-emerald-300 ring-1 ring-emerald-700/40",
  tight:          "bg-amber-900/50 text-amber-300 ring-1 ring-amber-700/40",
  not_recommended:"bg-orange-900/50 text-orange-300 ring-1 ring-orange-700/40",
  impossible:     "bg-red-900/50 text-red-300 ring-1 ring-red-700/40",
};

const SOURCE_BADGE: Record<string, string> = {
  ollama:      "bg-sky-900/60 text-sky-300",
  huggingface: "bg-indigo-900/60 text-indigo-300",
  local:       "bg-zinc-700/80 text-zinc-300",
};

// Group raw quant labels (q4_k_m, q8_0, f16 …) into friendly bands (Jan's
// Small/Balanced/Large) so users pick a fidelity, not a cryptic code.
const QUANT_BANDS = ["Small", "Balanced", "Large"] as const;
type QuantBand = (typeof QUANT_BANDS)[number];
function quantBand(q: string): QuantBand {
  const n = Number(q.toLowerCase().match(/(?:iq|q)(\d+)/)?.[1]);
  if (!Number.isNaN(n)) return n <= 3 ? "Small" : n <= 5 ? "Balanced" : "Large";
  return "Large"; // f16 / bf16 / fp16 / f32 — full precision
}

const TASK_OPTIONS = [
  { id: "rag",           label: "RAG" },
  { id: "coding",        label: "Coding" },
  { id: "chat",          label: "Chat" },
  { id: "math",          label: "Math" },
  { id: "agents",        label: "Agents" },
  { id: "summarization", label: "Summary" },
];

function relativeTime(ms: number) {
  const s = Math.round(ms / 1000);
  if (s < 5)  return "just now";
  if (s < 60) return `${s}s ago`;
  return `${Math.round(s / 60)}m ago`;
}

// ── Sub-score bar ─────────────────────────────────────────────────────────────

function MiniBar({ label, value, col }: { label: string; value: number; col: string }) {
  return (
    <div className="space-y-0.5">
      <div className="flex justify-between text-[10px] text-zinc-500">
        <span>{label}</span>
        <span className="font-mono text-zinc-300">{Math.round(value)}</span>
      </div>
      <div className="h-1 rounded bg-zinc-800">
        <div className={`h-full rounded ${col}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

// ── Pull command copy ─────────────────────────────────────────────────────────

function PullCommand({ cmd }: { cmd: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(cmd).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }
  return (
    <div className="flex items-center gap-2 rounded bg-zinc-950 border border-zinc-700 px-3 py-2">
      <span className="text-zinc-500 text-xs font-mono select-none">$</span>
      <code className="text-xs text-zinc-200 font-mono flex-1 break-all">{cmd}</code>
      <button
        onClick={copy}
        className="shrink-0 text-[10px] px-2 py-0.5 rounded border border-zinc-600 text-zinc-400 hover:text-zinc-200 hover:border-zinc-400 transition-colors"
      >
        {copied ? "✓" : "copy"}
      </button>
    </div>
  );
}

// ── Expanded row detail panel ─────────────────────────────────────────────────

function ExpandedPanel({
  entry,
  onRequestPull,
}: {
  entry: DiscoverEntry;
  onRequestPull: (entry: DiscoverEntry) => void;
}) {
  const sc = scoreColor(entry.overall_score);
  const re = entry.resource_estimate;
  const isOllama = entry.source === "ollama";

  const bars = [
    { label: "Hardware fit", value: entry.hardware_fit },
    { label: "Speed fit",    value: entry.speed_fit },
    { label: "RAG fit",      value: entry.rag_fit },
    { label: "Task fit",     value: entry.task_fit },
    { label: "Deployment",   value: entry.deployment_fit },
  ];

  return (
    <div className="px-4 pb-4 pt-1 border-t border-zinc-800/70 bg-zinc-950/40 space-y-4">
      {/* Reason */}
      <p className="text-xs text-zinc-400 leading-relaxed">{entry.reason}</p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Score breakdown */}
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Score breakdown</p>
          {bars.map((b) => (
            <MiniBar key={b.label} label={b.label} value={b.value} col={sc.bg} />
          ))}
        </div>

        {/* Resource details */}
        <div className="space-y-2 text-xs">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Resources</p>
          <div className="space-y-1.5 text-zinc-300">
            <div className="flex justify-between">
              <span className="text-zinc-500">Quantization</span>
              <span className="font-mono">{entry.best_quantization}</span>
            </div>
            {re && (
              <>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Est. VRAM</span>
                  <span className="font-mono">{re.estimated_vram_gb} GB
                    <span className={`ml-1.5 text-[10px] px-1 rounded ${FIT_PILL[re.fit_level] ?? ""}`}>
                      {re.fit_level.replace("_", " ")}
                    </span>
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Est. RAM</span>
                  <span className="font-mono">{re.estimated_ram_gb} GB</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Rec. context</span>
                  <span className="font-mono">{re.recommended_context.toLocaleString()} tok</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Disk</span>
                  <span className="font-mono">{re.estimated_disk_gb} GB</span>
                </div>
              </>
            )}
            {entry.model_meta.parameter_count_b != null && (
              <div className="flex justify-between">
                <span className="text-zinc-500">Parameters</span>
                <span className="font-mono">{entry.model_meta.parameter_count_b}B</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-zinc-500">License</span>
              <span className="font-mono">{entry.model_meta.license}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Live memory planner — drag context, watch VRAM + verdict update */}
      {entry.model_meta.parameter_count_b != null && (
        <MemoryPlanner
          modelId={entry.model_id}
          paramsB={entry.model_meta.parameter_count_b}
          quantization={entry.best_quantization}
          initial={re}
        />
      )}

      {/* Quantization options — grouped by fidelity, best one flagged */}
      {entry.model_meta.available_quantizations.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
            Quantization options
          </p>
          <div className="flex flex-wrap gap-2">
            {QUANT_BANDS.map((band) => {
              const qs = entry.model_meta.available_quantizations.filter((q) => quantBand(q) === band);
              if (!qs.length) return null;
              return (
                <div key={band} className="min-w-[104px] flex-1 rounded-lg border border-zinc-800 bg-zinc-950/40 p-2">
                  <p className="mb-1 text-[10px] font-medium text-zinc-400">{band}</p>
                  <div className="flex flex-wrap gap-1">
                    {qs.map((q) => {
                      const rec = q === entry.best_quantization;
                      return (
                        <span
                          key={q}
                          className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${
                            rec ? "bg-sky-900/50 text-sky-200 ring-1 ring-sky-600/50" : "bg-zinc-800 text-zinc-400"
                          }`}
                        >
                          {q}
                          {rec && " ★"}
                        </span>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-[10px] text-zinc-600">★ Recommended for your hardware</p>
        </div>
      )}

      {/* Pull section */}
      {entry.pull_command && (
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
            {isOllama ? "Pull via Ollama" : "Download command"}
          </p>
          <PullCommand cmd={entry.pull_command} />

          {!entry.already_installed && (
            <button
              onClick={() => onRequestPull(entry)}
              className="flex items-center gap-2 px-4 py-1.5 rounded-lg bg-sky-700 hover:bg-sky-600 text-sm text-white font-medium transition-colors"
            >
              <span>{isOllama ? "↓" : "⎘"}</span> {isOllama ? "Pull now" : "Download command"}
            </button>
          )}
        </div>
      )}

      {/* Warnings */}
      {entry.warnings.length > 0 && (
        <ul className="space-y-0.5">
          {entry.warnings.map((w, i) => (
            <li key={i} className="text-[10px] text-amber-400">⚠ {w}</li>
          ))}
        </ul>
      )}
      {entry.model_meta.notes.length > 0 && (
        <ul className="space-y-0.5">
          {entry.model_meta.notes.map((n, i) => (
            <li key={i} className="text-[10px] text-zinc-500">{n}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Single model row ──────────────────────────────────────────────────────────

function ModelRow({
  entry,
  rank,
  onRequestPull,
}: {
  entry: DiscoverEntry;
  rank: number;
  onRequestPull: (entry: DiscoverEntry) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const installed = entry.already_installed;
  const sc = scoreColor(entry.overall_score);
  const re = entry.resource_estimate;
  const displayName = (entry.model_meta.display_name || entry.model_id)
    .replace(/^(ollama:|hf:|local:)/, "");

  return (
    <div
      className={`rounded-xl border transition-all duration-200 overflow-hidden
        ${expanded
          ? "border-zinc-600 bg-zinc-900"
          : "border-zinc-800 bg-zinc-900/50 hover:border-zinc-700 hover:bg-zinc-900"
        }`}
    >
      {/* Main row */}
      <button
        className="w-full text-left px-4 py-3 flex items-center gap-3 group"
        onClick={() => setExpanded((x) => !x)}
      >
        {/* Rank */}
        <span className="text-xs font-mono text-zinc-600 w-5 shrink-0 text-right">{rank}</span>

        {/* Score ring */}
        <div className={`w-10 h-10 shrink-0 rounded-full ring-2 ${sc.ring} flex items-center justify-center bg-zinc-950`}>
          <span className={`text-sm font-bold font-mono ${sc.text}`}>
            {Math.round(entry.overall_score)}
          </span>
        </div>

        {/* Name + badges */}
        <div className="flex-1 min-w-0 space-y-0.5">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-zinc-100 truncate">{displayName}</span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${SOURCE_BADGE[entry.source] ?? "bg-zinc-700 text-zinc-400"}`}>
              {entry.source}
            </span>
            {entry.model_meta.tasks.length > 0 && (
              <span className="text-[10px] text-zinc-600">
                {entry.model_meta.tasks.slice(0, 3).join(" · ")}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 text-[10px] text-zinc-500">
            <span className={sc.text}>{entry.label}</span>
            {entry.model_meta.parameter_count_b != null && (
              <span>{entry.model_meta.parameter_count_b}B params</span>
            )}
            <span>{entry.best_quantization}</span>
          </div>
        </div>

        {/* Will-it-run verdict — led prominently (our differentiator) */}
        {re && (
          <div className="hidden shrink-0 flex-col items-end gap-0.5 sm:flex">
            {re.verdict ? (
              <VerdictPill verdict={re.verdict} />
            ) : (
              <span className={`rounded px-2 py-0.5 font-mono text-xs ${FIT_PILL[re.fit_level] ?? "bg-zinc-800 text-zinc-400"}`}>
                {re.fit_level.replace("_", " ")}
              </span>
            )}
            <span className="font-mono text-[10px] text-zinc-500">~{re.estimated_vram_gb} GB</span>
          </div>
        )}

        {/* Status badge */}
        <div className="shrink-0">
          {installed ? (
            <span className="flex items-center gap-1 text-xs text-emerald-400 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
              Installed
            </span>
          ) : (
            <span className="text-xs text-sky-500 group-hover:text-sky-300 transition-colors font-medium">
              {entry.source === "ollama" ? "↓ Pull" : "⎘ Copy cmd"}
            </span>
          )}
        </div>

        {/* Chevron */}
        <span className={`text-zinc-600 text-xs transition-transform ${expanded ? "rotate-180" : ""}`}>
          ▾
        </span>
      </button>

      {/* Expanded detail */}
      {expanded && <ExpandedPanel entry={entry} onRequestPull={onRequestPull} />}
    </div>
  );
}

// ── Hardware strip ────────────────────────────────────────────────────────────

function HardwareStrip({ hw }: { hw: DiscoverHardware }) {
  const backendColor =
    hw.best_backend === "cuda"  ? "text-emerald-400" :
    hw.best_backend === "metal" ? "text-sky-400"     :
    hw.best_backend === "rocm"  ? "text-purple-400"  : "text-zinc-400";

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border border-zinc-800 bg-zinc-900/60 px-4 py-2.5 text-xs">
      <span className="text-zinc-500">
        CPU <span className="text-zinc-300 font-mono">{hw.cpu || hw.os || "—"}</span>
      </span>
      <span className="text-zinc-700">│</span>
      <span className="text-zinc-500">
        RAM <span className="text-zinc-300 font-mono">{hw.ram_gb} GB</span>
      </span>
      {hw.total_vram_gb > 0 && (
        <>
          <span className="text-zinc-700">│</span>
          <span className="text-zinc-500">
            VRAM{" "}
            <span className="text-emerald-400 font-mono font-semibold">{hw.total_vram_gb} GB</span>
            {hw.gpus.length > 1 && (
              <span className="text-zinc-600"> ×{hw.gpus.length} GPU</span>
            )}
          </span>
        </>
      )}
      <span className="text-zinc-700">│</span>
      <span className={`font-mono font-semibold ${backendColor}`}>
        {hw.best_backend.toUpperCase()}
      </span>
      <span className="text-zinc-700">│</span>
      <span className={hw.ollama_available ? "text-emerald-400" : "text-zinc-600"}>
        Ollama {hw.ollama_available ? "✓" : "✗"}
      </span>
    </div>
  );
}

// ── Copy Results modal ────────────────────────────────────────────────────────

function CopyResultsPanel({
  result,
  onClose,
}: {
  result: DiscoverResult;
  onClose: () => void;
}) {
  const [label, setLabel] = useState("");
  const [copied, setCopied] = useState(false);

  const payload = JSON.stringify(
    {
      device_label: label || "unknown",
      captured_at: new Date().toISOString(),
      hardware: result.hardware,
      discover_task: result.task,
      total_candidates: result.total_candidates,
      top_recommendations: result.recommendations.slice(0, 5).map((r, i) => ({
        rank: i + 1,
        model: r.model_meta.display_name || r.model_id,
        source: r.source,
        score: Math.round(r.overall_score),
        label: r.label,
        vram_gb: r.resource_estimate?.estimated_vram_gb ?? null,
        quantization: r.best_quantization,
        pull_command: r.pull_command,
        installed: r.already_installed,
      })),
    },
    null,
    2,
  );

  function copy() {
    navigator.clipboard.writeText(payload).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-2xl rounded-2xl border border-zinc-700 bg-zinc-900 shadow-2xl flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
          <div>
            <h2 className="text-sm font-semibold text-zinc-100">Copy Device Results</h2>
            <p className="text-xs text-zinc-500 mt-0.5">
              Paste this JSON into the chat to update the research doc
            </p>
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300 text-lg leading-none">×</button>
        </div>

        <div className="px-6 py-4 border-b border-zinc-800">
          <label className="block text-xs text-zinc-400 mb-1.5">Device label (optional)</label>
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. macbook-pro · ubuntu-local · windows-rtx"
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-sky-500"
          />
        </div>

        <div className="flex-1 overflow-auto px-6 py-4">
          <pre className="text-[11px] font-mono text-zinc-400 leading-relaxed whitespace-pre-wrap break-words">
            {payload}
          </pre>
        </div>

        <div className="px-6 py-4 border-t border-zinc-800 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200">
            Close
          </button>
          <button
            onClick={copy}
            className="px-5 py-2 rounded-lg bg-sky-700 hover:bg-sky-600 text-sm text-white font-medium transition-colors"
          >
            {copied ? "✓ Copied!" : "Copy to clipboard"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main DiscoverTab ──────────────────────────────────────────────────────────

export function DiscoverTab() {
  const [task, setTask] = useState<string>("rag");
  const [includeHf, setIncludeHf] = useState(true);
  const [result, setResult] = useState<DiscoverResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fetchedAt, setFetchedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState<string>("—");
  const [showCopy, setShowCopy] = useState(false);
  const [pullTarget, setPullTarget] = useState<DiscoverEntry | null>(null);

  // tick elapsed display every 5s
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    tickRef.current = setInterval(() => {
      if (fetchedAt) setElapsed(relativeTime(Date.now() - fetchedAt));
    }, 5000);
    return () => { if (tickRef.current) clearInterval(tickRef.current); };
  }, [fetchedAt]);

  const discover = useCallback(
    async (refresh = false) => {
      setLoading(true);
      setError(null);
      try {
        const r = await discoverModels(task, includeHf, refresh, 40);
        setResult(r);
        setFetchedAt(Date.now());
        setElapsed("just now");
      } catch (e) {
        setError(String(e).replace(/^Error:\s*/, ""));
      } finally {
        setLoading(false);
      }
    },
    [task, includeHf],
  );

  // Auto-fetch on mount and when task/source changes
  useEffect(() => { discover(false); }, [discover]);

  function handlePulled(modelId: string) {
    setResult((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        recommendations: prev.recommendations.map((r) =>
          r.model_id === modelId ? { ...r, already_installed: true } : r,
        ),
      };
    });
  }

  const installedCount = result?.recommendations.filter((r) => r.already_installed).length ?? 0;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="space-y-1">
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">
          Discover &amp; Setup
        </h2>
        <p className="text-xs text-zinc-500">
          Probes your hardware, queries live Ollama registry + HuggingFace, and ranks
          every available model against your machine. Review the report, then pull with one click.
        </p>
      </div>

      {/* System report hero card + agree-to-pull */}
      {result && (
        <SystemReport
          result={result}
          onPull={(entry) => setPullTarget(entry)}
          onRefresh={() => discover(true)}
          loading={loading}
        />
      )}

      {/* Compact hardware strip (kept for the ranked list below) */}
      {result && <HardwareStrip hw={result.hardware} />}

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Task pills */}
        <div className="flex gap-1 flex-wrap">
          {TASK_OPTIONS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTask(t.id)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                task === t.id
                  ? "bg-sky-800 text-sky-200 ring-1 ring-sky-600"
                  : "bg-zinc-800 text-zinc-400 hover:text-zinc-200"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <span className="text-zinc-700 hidden sm:inline">│</span>

        {/* Source toggles */}
        <div className="flex gap-2 text-xs">
          <label className="flex items-center gap-1.5 cursor-pointer text-zinc-400 hover:text-zinc-200">
            <input
              type="checkbox"
              checked
              disabled
              className="accent-sky-500"
            />
            Ollama
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer text-zinc-400 hover:text-zinc-200">
            <input
              type="checkbox"
              checked={includeHf}
              onChange={(e) => setIncludeHf(e.target.checked)}
              className="accent-indigo-500"
            />
            HuggingFace
          </label>
        </div>

        <div className="flex-1" />

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => discover(true)}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-700 text-xs text-zinc-400 hover:text-zinc-200 hover:border-zinc-500 transition-colors disabled:opacity-40"
          >
            <span className={loading ? "animate-spin" : ""}>⟳</span>
            {loading ? "Scanning…" : "Refresh"}
          </button>
          {result && (
            <button
              onClick={() => setShowCopy(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-300 transition-colors"
            >
              📋 Copy Results
            </button>
          )}
        </div>
      </div>

      {/* Status bar */}
      {result && !loading && (
        <div className="flex items-center gap-3 text-[11px] text-zinc-500">
          <span>
            <span className="text-zinc-300 font-medium">{result.total_candidates}</span> models scored
          </span>
          <span>·</span>
          <span>
            <span className="text-emerald-400 font-medium">{installedCount}</span> already installed
          </span>
          <span>·</span>
          <span>ranked by hardware fit</span>
          <span>·</span>
          <span>fetched {elapsed}</span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && !result && (
        <div className="space-y-2">
          {[...Array(6)].map((_, i) => (
            <div
              key={i}
              className="h-16 rounded-xl border border-zinc-800 bg-zinc-900/50 animate-pulse"
            />
          ))}
        </div>
      )}

      {/* Results list */}
      {result && !loading && (
        <div className="space-y-2">
          {result.recommendations.map((entry, i) => (
            <ModelRow
              key={entry.model_id}
              entry={entry}
              rank={i + 1}
              onRequestPull={(e) => setPullTarget(e)}
            />
          ))}
          {result.recommendations.length === 0 && (
            <p className="text-sm text-zinc-500">No models found for this combination of task and hardware.</p>
          )}
        </div>
      )}

      {/* Agree-to-pull confirmation */}
      {pullTarget && result && (
        <PullConfirmModal
          entry={pullTarget}
          hardware={result.hardware}
          onClose={() => setPullTarget(null)}
          onPulled={handlePulled}
        />
      )}

      {/* Copy results modal */}
      {showCopy && result && (
        <CopyResultsPanel result={result} onClose={() => setShowCopy(false)} />
      )}
    </div>
  );
}
