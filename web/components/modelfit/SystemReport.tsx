"use client";
import type { DiscoverEntry, DiscoverHardware, DiscoverResult, GPUInfo } from "@/lib/modelfit";
import { verdictMeta } from "@/components/modelfit/verdict";

// ── Small building blocks ─────────────────────────────────────────────────────

function Chip({ label, tone = "zinc" }: { label: string; tone?: "zinc" | "green" | "sky" | "amber" }) {
  const tones = {
    zinc: "bg-zinc-800 text-zinc-300",
    green: "bg-emerald-900/50 text-emerald-300",
    sky: "bg-sky-900/50 text-sky-300",
    amber: "bg-amber-900/50 text-amber-300",
  };
  return <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${tones[tone]}`}>{label}</span>;
}

function Stat({ label, value, accent }: { label: string; value: React.ReactNode; accent?: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</div>
      <div className={`text-sm font-mono ${accent ?? "text-zinc-100"}`}>{value}</div>
    </div>
  );
}

function backendTone(b: string) {
  return b === "cuda"
    ? "bg-emerald-900/50 text-emerald-300 ring-emerald-600/40"
    : b === "metal"
      ? "bg-sky-900/50 text-sky-300 ring-sky-600/40"
      : b === "rocm"
        ? "bg-purple-900/50 text-purple-300 ring-purple-600/40"
        : "bg-zinc-800 text-zinc-300 ring-zinc-600/40";
}

/** Per-GPU VRAM bar: used (other processes) + free. */
function GpuBar({ gpu }: { gpu: GPUInfo }) {
  const total = gpu.vram_gb || 0;
  const free = gpu.vram_free_gb ?? null;
  const usedPct = total > 0 && free != null ? Math.max(0, Math.min(100, ((total - free) / total) * 100)) : 0;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-zinc-300 truncate">{gpu.name}</span>
        <span className="text-zinc-400 font-mono shrink-0 ml-2">
          {total} GB{gpu.integrated ? " unified" : ""}
        </span>
      </div>
      {free != null && (
        <>
          <div className="h-1.5 rounded bg-zinc-800 overflow-hidden">
            <div className="h-full bg-zinc-500" style={{ width: `${usedPct}%` }} />
          </div>
          <div className="text-[10px] text-zinc-500 font-mono">
            {free} GB free · {(total - free).toFixed(1)} GB in use
          </div>
        </>
      )}
    </div>
  );
}

/** Usage gauge for the recommended model vs available memory, with 80% marker. */
function UsageGauge({ entry, hardware }: { entry: DiscoverEntry; hardware: DiscoverHardware }) {
  const re = entry.resource_estimate;
  if (!re) return null;
  const onGpu = hardware.total_vram_gb > 0;
  const capacity = onGpu ? hardware.total_vram_gb : hardware.ram_gb;
  const model = re.estimated_vram_gb;
  const pct = capacity > 0 ? Math.min(100, (model / capacity) * 100) : 0;
  const meta = verdictMeta(re.verdict);
  const freeNow = onGpu ? hardware.total_vram_free_gb ?? null : null;

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between">
        <span className="text-[10px] uppercase tracking-wider text-zinc-500">
          Estimated {onGpu ? "VRAM" : "RAM"} use
        </span>
        <span className="text-xs font-mono text-zinc-300">
          {model} / {capacity} GB
        </span>
      </div>
      <div className="relative h-3 rounded-full bg-zinc-800 overflow-hidden">
        <div className={`h-full rounded-full ${meta.barClass}`} style={{ width: `${pct}%` }} />
        {/* 80% headroom marker */}
        <div className="absolute top-0 bottom-0 w-px bg-zinc-400/70" style={{ left: "80%" }} title="80% headroom target" />
      </div>
      <div className="text-[10px] text-zinc-500 font-mono">
        {re.headroom_gb != null && re.headroom_gb >= 0
          ? `${re.headroom_gb} GB headroom`
          : "exceeds capacity"}
        {freeNow != null && ` · ${freeNow} GB free right now`}
        {" · dashed line = 80% target"}
      </div>
    </div>
  );
}

// ── Plain-language summary ────────────────────────────────────────────────────

function gpuSummary(gpus: GPUInfo[], totalVram: number): string {
  if (gpus.length === 0) return "no GPU";
  const first = gpus[0].name.replace(/NVIDIA GeForce |NVIDIA /i, "");
  const prefix = gpus.length > 1 ? `${gpus.length}× ${first}` : first;
  return `${prefix} (${totalVram} GB VRAM)`;
}

function buildSummary(hardware: DiscoverHardware, entry: DiscoverEntry): string {
  const re = entry.resource_estimate;
  const name = (entry.model_meta.display_name || entry.model_id).replace(/^(ollama:|hf:|local:)/, "");
  const hw = hardware.total_vram_gb > 0 ? gpuSummary(hardware.gpus, hardware.total_vram_gb) : `${hardware.ram_gb} GB RAM (CPU)`;
  if (!re) return `${name} is the best match for your ${hw}.`;
  const v = re.verdict;
  const use = `~${re.estimated_vram_gb} GB at ${entry.best_quantization}`;
  if (v === "runs_great") return `Your ${hw} runs ${name} comfortably — ${use}, ${re.headroom_gb} GB to spare.`;
  if (v === "runs_ok") return `Your ${hw} runs ${name} — ${use}, a tight but workable fit.`;
  if (v === "runs_offload")
    return `${name} needs ${use} — more than your ${hw}. It runs by offloading layers to system RAM (slower). A smaller model or lower quant would run fully on the GPU.`;
  if (v === "runs_cpu") return `${name} runs on your CPU — ${use} in RAM, ${re.headroom_gb} GB to spare.`;
  if (v === "runs_cpu_tight") return `${name} runs on your CPU but leaves little RAM headroom (${use}).`;
  return `${name} needs ${use} — too large for this machine. Pick a smaller model below.`;
}

// ── Main report ───────────────────────────────────────────────────────────────

export function SystemReport({
  result,
  onPull,
  onRefresh,
  loading,
  hosted = false,
}: {
  result: DiscoverResult;
  onPull: (entry: DiscoverEntry) => void;
  onRefresh: () => void;
  loading: boolean;
  /** True on a hosted demo (HF Space): the probe reads the SERVER, not the visitor's device. */
  hosted?: boolean;
}) {
  const hw = result.hardware;
  const top = result.recommendations[0] as DiscoverEntry | undefined;
  const onGpu = hw.total_vram_gb > 0;
  const meta = top?.resource_estimate ? verdictMeta(top.resource_estimate.verdict) : null;

  return (
    <div className="rounded-2xl border border-zinc-700 bg-gradient-to-b from-zinc-900 to-zinc-900/60 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
        <div>
          <h2 className="text-base font-semibold text-zinc-100">Your System Report</h2>
          <p className="text-xs text-zinc-500 mt-0.5">
            Detected hardware and the best-fitting model, ranked for {result.task ?? "your tasks"}.
          </p>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-700 text-xs text-zinc-400 hover:text-zinc-200 hover:border-zinc-500 transition-colors disabled:opacity-40"
        >
          <span className={loading ? "animate-spin" : ""}>⟳</span>
          {loading ? "Scanning…" : "Re-scan"}
        </button>
      </div>

      {/* Hosted-demo notice: the probe reads the Space's server, not the visitor's device. */}
      {hosted && (
        <div className="mx-6 mt-4 rounded-lg border border-amber-600/40 bg-amber-900/20 px-3.5 py-2.5 text-[11px] leading-relaxed text-amber-200/90">
          <span className="font-semibold text-amber-200">You&apos;re on the hosted demo.</span>{" "}
          This report profiles the <span className="font-semibold">Space&apos;s server</span>{" "}
          ({hw.os}
          {hw.arch ? ` · ${hw.arch}` : ""}) — not your own device. Models shown here would run on the
          server, not on your machine. To profile your Mac/PC and pull models onto it, run Auralynq
          locally (
          <a
            href="https://github.com/MHHamdan/Auralynq"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-amber-100"
          >
            one command
          </a>
          ).
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-zinc-800">
        {/* ── This machine ── */}
        <div className="p-6 space-y-4">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
              {hosted ? "Server (hosted demo)" : "This machine"}
            </span>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold ring-1 ${backendTone(hw.best_backend)}`}>
              {hw.best_backend.toUpperCase()}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-y-3 gap-x-4">
            <Stat label="OS" value={`${hw.os}${hw.arch ? ` · ${hw.arch}` : ""}`} />
            <Stat label="RAM" value={`${hw.ram_gb} GB`} accent="text-zinc-100 font-semibold" />
            <div className="col-span-2">
              <Stat label="CPU" value={hw.cpu || "unknown"} />
              <div className="flex flex-wrap gap-1.5 mt-1">
                {hw.cpu_cores_physical != null && (
                  <Chip label={`${hw.cpu_cores_physical}P / ${hw.cpu_cores_logical}L`} />
                )}
                {hw.avx2 && <Chip label="AVX2" tone="green" />}
                {hw.avx512 && <Chip label="AVX-512" tone="green" />}
              </div>
            </div>
          </div>

          {/* GPUs */}
          <div className="space-y-2 pt-1">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase tracking-wider text-zinc-500">
                {onGpu ? `GPU${hw.gpus.length > 1 ? `s · ${hw.gpus.length}` : ""}` : "GPU"}
              </span>
              {onGpu && (
                <span className="text-xs font-mono text-emerald-400 font-semibold">
                  {hw.total_vram_gb} GB total
                  {hw.total_vram_free_gb != null && ` · ${hw.total_vram_free_gb} free`}
                </span>
              )}
            </div>
            {hw.gpus.length === 0 ? (
              <p className="text-xs text-zinc-500">
                None detected — inference will use the CPU.
                {hw.in_container && " (Running in a container; host GPUs may be hidden.)"}
              </p>
            ) : (
              <div className="space-y-2.5">
                {hw.gpus.slice(0, 4).map((g, i) => (
                  <GpuBar key={i} gpu={g} />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Top pick ── */}
        <div className="p-6 space-y-4">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
            {hosted ? "Best pick for this server" : "Best pick for you"}
          </span>

          {!top ? (
            <p className="text-sm text-zinc-500">No models matched this machine and task.</p>
          ) : (
            <>
              {/* Model identity */}
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-lg font-semibold text-zinc-100 truncate">
                    {(top.model_meta.display_name || top.model_id).replace(/^(ollama:|hf:|local:)/, "")}
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 text-[11px] text-zinc-500">
                    <span className="uppercase">{top.source}</span>
                    {top.model_meta.parameter_count_b != null && <span>· {top.model_meta.parameter_count_b}B</span>}
                    <span>· {top.best_quantization}</span>
                    <span>· score {Math.round(top.overall_score)}</span>
                  </div>
                </div>
                {top.already_installed && (
                  <span className="shrink-0 flex items-center gap-1 text-xs text-emerald-400 font-medium">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Installed
                  </span>
                )}
              </div>

              {/* Verdict badge */}
              {meta && (
                <div className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 ${meta.badgeClass}`}>
                  <meta.icon className="h-4 w-4 shrink-0" aria-hidden />
                  <span className="text-sm font-semibold">{meta.label}</span>
                </div>
              )}

              {/* Usage gauge */}
              <UsageGauge entry={top} hardware={hw} />

              {/* Quick stats */}
              <div className="grid grid-cols-3 gap-3 pt-1">
                {top.resource_estimate && (
                  <>
                    <Stat label="Download" value={`${top.resource_estimate.estimated_disk_gb} GB`} />
                    <Stat label="RAM need" value={`${top.resource_estimate.estimated_ram_gb} GB`} />
                    <Stat
                      label="Max context"
                      value={`${(top.resource_estimate.recommended_context / 1024).toFixed(0)}K`}
                    />
                  </>
                )}
              </div>

              {/* Plain-language summary */}
              <p className="text-xs text-zinc-400 leading-relaxed">{buildSummary(hw, top)}</p>

              {/* CTA */}
              {!top.already_installed && top.pull_command && (
                <button
                  onClick={() => onPull(top)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-sm text-white font-semibold transition-colors"
                >
                  {top.source === "ollama" ? "↓ Pull this model" : "⎘ Get download command"}
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="px-6 py-2.5 border-t border-zinc-800 text-[11px] text-zinc-500 flex items-center gap-2">
        <span>
          <span className="text-zinc-300 font-medium">{result.total_candidates}</span> models scored against
          {hosted ? " the server's hardware" : " your hardware"}
        </span>
        <span className="text-zinc-700">·</span>
        <span>full ranking below ↓</span>
      </div>
    </div>
  );
}
