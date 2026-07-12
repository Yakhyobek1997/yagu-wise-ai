"use client";
/**
 * HardwareGate — landing-page consent → hardware scan → model recommendations.
 *
 * Flow:
 *  1. First visit: consent modal appears after 2 s
 *  2. "Allow": modal closes, animated scan runs (hardware probe + model catalog)
 *  3. Results panel: hardware strip + top-3 ranked models with Pull/Install buttons
 *  4. "Skip": stores decision, shows a subtle chip in the section to revisit later
 *
 * localStorage key: "auralynq_hw_consent"  = "granted" | "skipped"
 *   - "granted"  → auto-scan on every page load (no modal)
 *   - "skipped"  → show the "Check hardware" chip until user explicitly allows
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type { DiscoverEntry } from "@/lib/modelfit";
import { discoverModels, pullModel } from "@/lib/modelfit";
import { detectClientHardware, clientFit, type ClientHardware } from "@/lib/clienthw";

// ── Constants ────────────────────────────────────────────────────────────────

const CONSENT_KEY = "auralynq_hw_consent";
const MODAL_DELAY_MS = 1800;

// ── Tiny helpers ─────────────────────────────────────────────────────────────

function scoreColor(s: number) {
  if (s >= 90) return { text: "text-emerald-400", bar: "bg-emerald-500", ring: "border-emerald-500/60" };
  if (s >= 80) return { text: "text-sky-400",     bar: "bg-sky-500",     ring: "border-sky-500/60"     };
  if (s >= 70) return { text: "text-amber-400",   bar: "bg-amber-500",   ring: "border-amber-500/60"   };
  return          { text: "text-red-400",          bar: "bg-red-500",     ring: "border-red-500/60"     };
}

const FIT_PILL: Record<string, string> = {
  comfortable:     "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  tight:           "bg-amber-500/10 text-amber-300 border-amber-500/30",
  not_recommended: "bg-orange-500/10 text-orange-300 border-orange-500/30",
  impossible:      "bg-red-500/10 text-red-300 border-red-500/30",
};

// ── Scan steps ────────────────────────────────────────────────────────────────

type StepStatus = "pending" | "running" | "done" | "error";

interface ScanStep {
  id: string;
  label: string;
  status: StepStatus;
  detail: string;
}

const INITIAL_STEPS: ScanStep[] = [
  { id: "hw",      label: "Detecting your device (OS, GPU, cores)", status: "pending", detail: "" },
  { id: "catalog", label: "Querying live model catalog",            status: "pending", detail: "" },
  { id: "rank",    label: "Ranking models for your device",         status: "pending", detail: "" },
];

function StepRow({ step }: { step: ScanStep }) {
  return (
    <div className="flex items-center gap-3 py-2">
      <span className="w-6 shrink-0 text-center">
        {step.status === "pending" && <span className="text-fg3">○</span>}
        {step.status === "running" && (
          <span className="inline-block animate-spin text-brand">⟳</span>
        )}
        {step.status === "done" && <span className="text-ok">✓</span>}
        {step.status === "error" && <span className="text-bad">✗</span>}
      </span>
      <span className={`text-sm ${step.status === "pending" ? "text-fg3" : "text-fg"}`}>
        {step.label}
      </span>
      {step.detail && (
        <span className="ml-auto text-xs font-mono text-fg3 hidden sm:block truncate max-w-[260px]">
          {step.detail}
        </span>
      )}
    </div>
  );
}

// ── Model card (top-3 on landing) ─────────────────────────────────────────────

const CLIENT_FIT_BADGE: Record<string, { label: string; cls: string }> = {
  runs: { label: "✓ Fits your device", cls: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30" },
  tight: { label: "~ Tight on your RAM", cls: "bg-amber-500/10 text-amber-300 border-amber-500/30" },
  too_big: { label: "✕ Too big for your device", cls: "bg-red-500/10 text-red-300 border-red-500/30" },
  unknown: { label: "", cls: "" },
};

function ModelCard({ entry, rank, clientHw }: { entry: DiscoverEntry; rank: number; clientHw: ClientHardware | null }) {
  const [installed, setInstalled] = useState(entry.already_installed);
  const [pulling, setPulling] = useState(false);
  const [pullErr, setPullErr] = useState<string | null>(null);
  const sc = scoreColor(entry.overall_score);
  const re = entry.resource_estimate;
  const name = (entry.model_meta.display_name || entry.model_id).replace(/^(ollama:|hf:|local:)/, "");
  const fit = clientHw ? clientFit(clientHw, re?.estimated_ram_gb) : "unknown";
  const fitBadge = CLIENT_FIT_BADGE[fit];

  async function doPull() {
    setPulling(true);
    setPullErr(null);
    try {
      await pullModel(entry.model_id);
      setInstalled(true);
    } catch (e) {
      setPullErr(String(e).replace(/^Error:\s*API .*?:\s*/, ""));
    } finally {
      setPulling(false);
    }
  }

  return (
    <div className="card card-hover flex flex-col gap-3 group">
      {/* rank + score */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono text-fg3">#{rank}</span>
        <div className={`w-11 h-11 rounded-full border-2 ${sc.ring} flex items-center justify-center bg-panel2`}>
          <span className={`text-base font-bold font-mono ${sc.text}`}>
            {Math.round(entry.overall_score)}
          </span>
        </div>
      </div>

      {/* name */}
      <div>
        <p className="font-semibold text-fg truncate" title={name}>{name}</p>
        <p className={`text-xs mt-0.5 font-medium ${sc.text}`}>{entry.label}</p>
      </div>

      {/* size + per-device fit */}
      <div className="flex items-center gap-2 flex-wrap">
        {re && (
          <span className={`text-xs px-2 py-0.5 rounded-full border font-mono ${FIT_PILL[re.fit_level] ?? "border-edge text-fg3"}`}>
            {re.estimated_ram_gb} GB RAM
          </span>
        )}
        <span className="text-xs text-fg3 font-mono">{entry.best_quantization}</span>
      </div>
      {fitBadge?.label && (
        <span className={`text-[11px] px-2 py-0.5 rounded-full border font-medium self-start ${fitBadge.cls}`}>
          {fitBadge.label}
        </span>
      )}

      {/* progress bar */}
      <div className="h-1 rounded-full bg-panel2 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${sc.bar}`}
          style={{ width: `${entry.overall_score}%` }}
        />
      </div>

      {/* action */}
      <div className="mt-auto pt-1">
        {installed ? (
          <span className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            Installed &amp; ready
          </span>
        ) : entry.source === "ollama" ? (
          pulling ? (
            <span className="text-xs text-fg3 flex items-center gap-1.5">
              <span className="animate-spin">⟳</span> Pulling…
            </span>
          ) : pullErr ? (
            <span className="text-xs text-bad truncate" title={pullErr}>{pullErr}</span>
          ) : (
            <button
              onClick={doPull}
              className="w-full text-xs font-semibold btn-cta py-1.5 px-3"
            >
              ↓ Pull now
            </button>
          )
        ) : (
          <Link
            href="/modelfit"
            className="text-xs text-brand hover:underline"
          >
            View in ModelFit →
          </Link>
        )}
      </div>
    </div>
  );
}

// ── Hardware summary strip ────────────────────────────────────────────────────

/** The visitor's own device, read from browser APIs (real per-device). */
function ClientHwStrip({ hw }: { hw: ClientHardware }) {
  const gpuColor = hw.gpuVendor === "NVIDIA" ? "text-emerald-400" : hw.gpuVendor === "Apple" ? "text-sky-400" : "text-fg";
  const Sep = () => <span className="hidden sm:block text-edge2">│</span>;
  return (
    <div className="card-inset flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
      <span className="text-fg3">
        OS <span className="font-mono text-fg">{hw.os}{hw.arch ? ` · ${hw.arch}` : ""}</span>
      </span>
      {hw.cpuCores != null && (
        <>
          <Sep />
          <span className="text-fg3">
            CPU <span className="font-mono text-fg">{hw.cpuCores} logical cores</span>
          </span>
        </>
      )}
      <Sep />
      <span className="text-fg3">
        RAM{" "}
        <span className="font-mono text-fg">
          {hw.ramGb != null ? `${hw.ramIsLowerBound ? "≥" : "~"}${hw.ramGb} GB` : "not exposed by browser"}
        </span>
      </span>
      {hw.gpu && (
        <>
          <Sep />
          <span className="text-fg3">
            GPU <span className={`font-mono font-medium ${gpuColor}`}>{hw.gpu}</span>
          </span>
        </>
      )}
      <Sep />
      <span className="text-fg3 text-xs italic">detected in your browser</span>
    </div>
  );
}

// ── Consent modal ─────────────────────────────────────────────────────────────

function ConsentModal({
  onAllow,
  onSkip,
}: {
  onAllow: () => void;
  onSkip: () => void;
}) {
  // Close on ESC
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onSkip(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onSkip]);

  const items = [
    { icon: "🖥", text: "Your device — OS, CPU cores & GPU — read in your browser" },
    { icon: "⚡", text: "Approximate memory, when your browser exposes it" },
    { icon: "🌐", text: "Live model sizes from the Ollama registry (external call)" },
    { icon: "🤗", text: "Popular GGUF models on HuggingFace Hub (external call)" },
  ];

  return (
    /* backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/80 backdrop-blur-sm animate-fade-up"
      onClick={(e) => { if (e.target === e.currentTarget) onSkip(); }}
    >
      {/* card */}
      <div className="glass w-full max-w-md shadow-2xl">
        {/* header */}
        <div className="px-6 pt-6 pb-4 border-b border-edge">
          <div className="flex items-center gap-3 mb-3">
            <span className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-brand/10 border border-brand/30 text-brand text-xl">
              🔍
            </span>
            <div>
              <h2 className="font-bold text-lg text-fg">System Check</h2>
              <p className="text-xs text-fg3">One-time permission · stored locally · never shared</p>
            </div>
          </div>
          <p className="text-sm text-fg2 leading-relaxed">
            To recommend the <span className="text-brand font-semibold">best AI models</span> for
            your hardware, Auralynq will probe your system and query live model catalogs.
          </p>
        </div>

        {/* what we check */}
        <div className="px-6 py-4 space-y-2.5">
          <p className="text-xs font-semibold uppercase tracking-wider text-fg3">What will be checked</p>
          {items.map((item) => (
            <div key={item.text} className="flex items-start gap-3 text-sm">
              <span className="shrink-0 mt-0.5">{item.icon}</span>
              <span className="text-fg2">{item.text}</span>
            </div>
          ))}
        </div>

        {/* privacy note */}
        <div className="mx-6 mb-4 px-3 py-2 rounded-lg bg-info/5 border border-info/20">
          <p className="text-xs text-fg3 leading-relaxed">
            <span className="text-info font-semibold">Privacy:</span> Your device details are read
            in your browser and never leave it. Only model-catalog lookups go out — to{" "}
            <span className="font-mono text-fg2">registry.ollama.ai</span> and{" "}
            <span className="font-mono text-fg2">huggingface.co</span> — and carry no personal data.
          </p>
        </div>

        {/* actions */}
        <div className="px-6 pb-6 flex flex-col sm:flex-row gap-3">
          <button onClick={onAllow} className="btn-cta flex-1 justify-center">
            Allow System Check
          </button>
          <button
            onClick={onSkip}
            className="btn-outline flex-1 justify-center text-fg3"
          >
            Skip for now
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Results panel (after scan) ────────────────────────────────────────────────

const FIT_RANK: Record<string, number> = { runs: 0, tight: 1, unknown: 2, too_big: 3 };

function deviceTier(hw: ClientHardware): string {
  if (hw.gpuVendor === "NVIDIA" || hw.gpuVendor === "AMD") return "well-equipped";
  if (hw.gpuVendor === "Apple") return "capable"; // unified memory
  if (hw.ramGb != null && hw.ramGb >= 16) return "capable";
  return "ready to run local AI";
}

function ResultsPanel({
  clientHw,
  entries,
  totalCandidates,
  onReset,
}: {
  clientHw: ClientHardware | null;
  entries: DiscoverEntry[];
  totalCandidates: number;
  onReset: () => void;
}) {
  // Re-rank by *this device's* fit (server ranks by its own hardware); keep the
  // server's order as the tie-breaker within a fit bucket.
  const ranked = clientHw
    ? [...entries].sort((a, b) => {
        const fa = FIT_RANK[clientFit(clientHw, a.resource_estimate?.estimated_ram_gb)];
        const fb = FIT_RANK[clientFit(clientHw, b.resource_estimate?.estimated_ram_gb)];
        return fa - fb || b.overall_score - a.overall_score;
      })
    : entries;
  const top3 = ranked.slice(0, 3);
  const canJudge = clientHw?.ramGb != null;

  return (
    <div className="space-y-6 animate-fade-up">
      {/* section header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="overline">Your device</p>
          <h2 className="section-title mt-1">
            Your machine is{" "}
            <span className="gradient-text">
              {clientHw ? deviceTier(clientHw) : "ready to run local AI"}
            </span>
          </h2>
          <p className="mt-2 text-fg3 text-sm">
            {totalCandidates} models from the live catalog ·{" "}
            {canJudge ? "top 3 that fit your device" : "top 3 by capability"} · sizes are per-model
          </p>
        </div>
        <button
          onClick={onReset}
          className="shrink-0 text-xs text-fg3 hover:text-fg border border-edge rounded-lg px-3 py-1.5 transition-colors"
        >
          Re-scan
        </button>
      </div>

      {/* the visitor's own device (browser-detected) */}
      {clientHw && <ClientHwStrip hw={clientHw} />}
      {clientHw && !canJudge && (
        <p className="text-xs text-fg3 -mt-3">
          Your browser doesn&apos;t expose exact RAM, so fit is estimated from OS/GPU only. Run
          Auralynq locally for an exact hardware probe.
        </p>
      )}

      {/* top 3 model cards, ranked for this device */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {top3.map((entry, i) => (
          <ModelCard key={entry.model_id} entry={entry} rank={i + 1} clientHw={clientHw} />
        ))}
      </div>

      {/* CTAs */}
      <div className="flex flex-wrap items-center gap-4 pt-2">
        <Link href="/modelfit" className="btn-cta">
          Explore all {totalCandidates} models →
        </Link>
        <Link href="/chat" className="btn-outline">
          Start chatting
        </Link>
        <span className="text-xs text-fg3 ml-auto hidden sm:block">
          Pull commands are one-click inside ModelFit
        </span>
      </div>
    </div>
  );
}

// ── Scan panel ────────────────────────────────────────────────────────────────

function ScanPanel({ onDone }: { onDone: (clientHw: ClientHardware | null, entries: DiscoverEntry[], total: number) => void }) {
  const [steps, setSteps] = useState<ScanStep[]>(INITIAL_STEPS);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  function setStep(id: string, patch: Partial<ScanStep>) {
    setSteps((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  }

  const runScan = useCallback(async () => {
    if (started.current) return;
    started.current = true;

    try {
      // Step 1 — detect THIS device in the browser (real per-visitor)
      setStep("hw", { status: "running" });
      const clientHw = await detectClientHardware();
      const hwLabel = [
        `${clientHw.os}${clientHw.arch ? ` · ${clientHw.arch}` : ""}`,
        clientHw.gpu ?? (clientHw.cpuCores ? `${clientHw.cpuCores} cores` : null),
      ]
        .filter(Boolean)
        .join(" · ");
      setStep("hw", { status: "done", detail: hwLabel });

      // Brief pause so user can read step 1
      await new Promise((r) => setTimeout(r, 400));

      // Step 2 — live catalog (server queries Ollama + HuggingFace registries)
      setStep("catalog", { status: "running" });
      const result = await discoverModels("rag", true, false, 30);
      setStep("catalog", {
        status: "done",
        detail: `${result.total_candidates} models from Ollama + HuggingFace`,
      });

      await new Promise((r) => setTimeout(r, 300));

      // Step 3 — rank models against THIS device (done in ResultsPanel)
      setStep("rank", { status: "running" });
      await new Promise((r) => setTimeout(r, 500));
      setStep("rank", { status: "done", detail: `matched to your ${clientHw.gpu ?? clientHw.os}` });

      await new Promise((r) => setTimeout(r, 400));

      onDone(clientHw, result.recommendations, result.total_candidates);
    } catch (e) {
      const msg = String(e).replace(/^Error:\s*/, "");
      setError(msg);
      setSteps((prev) =>
        prev.map((s) => (s.status === "running" ? { ...s, status: "error" } : s)),
      );
    }
  }, [onDone]);

  useEffect(() => { runScan(); }, [runScan]);

  return (
    <div className="card max-w-xl mx-auto animate-fade-up">
      <div className="flex items-center gap-3 mb-4 pb-3 border-b border-edge">
        <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-brand/10 border border-brand/30 text-brand text-sm animate-pulse-soft">
          🔍
        </span>
        <div>
          <p className="font-semibold text-fg text-sm">Scanning your system</p>
          <p className="text-xs text-fg3">This takes about 5 seconds</p>
        </div>
      </div>

      <div className="divide-y divide-edge">
        {steps.map((s) => <StepRow key={s.id} step={s} />)}
      </div>

      {error && (
        <div className="mt-4 rounded-lg bg-bad/10 border border-bad/30 px-3 py-2 text-sm text-bad">
          {error}
          <p className="text-xs mt-1 text-fg3">
            Make sure the Auralynq API is running at{" "}
            <code>{process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api"}</code>
          </p>
        </div>
      )}
    </div>
  );
}

// ── HardwareGate (exported) ───────────────────────────────────────────────────

type UIState =
  | { phase: "idle" }        // checking localStorage
  | { phase: "modal" }       // consent modal visible
  | { phase: "scanning" }    // scan in progress
  | { phase: "done"; clientHw: ClientHardware | null; entries: DiscoverEntry[]; total: number }
  | { phase: "skipped" };    // user said skip

export function HardwareGate() {
  const [state, setState] = useState<UIState>({ phase: "idle" });
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const consent = localStorage.getItem(CONSENT_KEY);
    if (consent === "granted") {
      setState({ phase: "scanning" });
    } else if (consent === "skipped") {
      setState({ phase: "skipped" });
    } else {
      // First visit — show modal after delay
      timerRef.current = setTimeout(() => {
        setState({ phase: "modal" });
      }, MODAL_DELAY_MS);
    }
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, []);

  function allow() {
    localStorage.setItem(CONSENT_KEY, "granted");
    setState({ phase: "scanning" });
  }

  function skip() {
    localStorage.setItem(CONSENT_KEY, "skipped");
    setState({ phase: "skipped" });
  }

  function reset() {
    localStorage.removeItem(CONSENT_KEY);
    setState({ phase: "scanning" });
  }

  function onScanDone(clientHw: ClientHardware | null, entries: DiscoverEntry[], total: number) {
    setState({ phase: "done", clientHw, entries, total });
  }

  // "skipped" state: show a subtle invite chip
  if (state.phase === "skipped") {
    return (
      <div className="flex justify-center py-2">
        <button
          onClick={allow}
          className="chip hover:border-brand/50 hover:text-brand transition-colors gap-2"
        >
          <span>🔍</span>
          Check hardware &amp; get model recommendations
        </button>
      </div>
    );
  }

  // "idle" — haven't checked storage yet, render nothing
  if (state.phase === "idle") return null;

  return (
    <>
      {/* Consent modal — floats above everything */}
      {state.phase === "modal" && (
        <ConsentModal onAllow={allow} onSkip={skip} />
      )}

      {/* Inline section — scanning or results */}
      {(state.phase === "scanning" || state.phase === "done") && (
        <section className="relative py-16 overflow-hidden">
          {/* ambient orbs */}
          <div className="orb left-[-4rem] top-8 h-64 w-64 bg-brand/10 animate-orb-drift" aria-hidden />
          <div className="orb right-[-3rem] bottom-4 h-56 w-56 bg-brand2/10 animate-orb-drift" style={{ animationDelay: "4s" }} aria-hidden />

          <div className="relative mx-auto max-w-5xl px-4 md:px-6">
            {state.phase === "scanning" && <ScanPanel onDone={onScanDone} />}
            {state.phase === "done" && (
              <ResultsPanel
                clientHw={state.clientHw}
                entries={state.entries}
                totalCandidates={state.total}
                onReset={reset}
              />
            )}
          </div>
        </section>
      )}
    </>
  );
}
