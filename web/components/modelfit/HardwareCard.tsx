"use client";
import type { HardwareProfile } from "@/lib/modelfit";

function Badge({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-xs font-mono ${
        ok ? "bg-emerald-900/40 text-emerald-300" : "bg-zinc-700 text-zinc-400"
      }`}
    >
      {label}
    </span>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5 border-b border-zinc-800 last:border-0">
      <span className="text-zinc-400 text-sm shrink-0">{label}</span>
      <span className="text-zinc-100 text-sm text-right font-mono">{value}</span>
    </div>
  );
}

export function HardwareCard({ hw }: { hw: HardwareProfile }) {
  return (
    <div className="rounded-xl border border-zinc-700 bg-zinc-900 p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-100 uppercase tracking-wider">
          Hardware Profile
        </h3>
        <span className="text-xs text-zinc-500">{hw.os.name}</span>
      </div>

      <div className="space-y-0">
        <Row label="CPU" value={hw.cpu.model || "unknown"} />
        <Row label="Cores" value={`${hw.cpu.cores_physical}P / ${hw.cpu.cores_logical}L`} />
        <Row label="RAM" value={`${hw.ram_gb} GB`} />
        {hw.gpus.length === 0 ? (
          <Row label="GPU" value={<span className="text-zinc-500">none detected</span>} />
        ) : (
          hw.gpus.map((gpu, i) => (
            <Row
              key={i}
              label={hw.gpus.length > 1 ? `GPU ${i}` : "GPU"}
              value={
                <span className="flex items-center gap-2">
                  <span>{gpu.name}</span>
                  <Badge label={`${gpu.vram_gb} GB`} ok={gpu.vram_gb > 0} />
                  <Badge label={gpu.backend.toUpperCase()} ok />
                </span>
              }
            />
          ))
        )}
        {hw.gpus.length > 1 && (
          <Row
            label="Total VRAM"
            value={<span className="text-sky-400 font-semibold">{hw.total_vram_gb} GB</span>}
          />
        )}
        <Row label="Disk free" value={`${hw.disk_free_gb} GB`} />
      </div>

      <div className="flex flex-wrap gap-2 pt-1">
        <Badge label="CUDA" ok={hw.cuda_available} />
        <Badge label="Metal" ok={hw.metal_available} />
        <Badge label="ROCm" ok={hw.rocm_available} />
        <Badge label="Ollama" ok={hw.ollama_available} />
        <Badge label="HF Cache" ok={hw.hf_available} />
      </div>

      {hw.warnings.length > 0 && (
        <ul className="mt-2 space-y-1">
          {hw.warnings.map((w, i) => (
            <li key={i} className="text-xs text-amber-400">
              ⚠ {w}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
