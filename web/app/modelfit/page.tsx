"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { HardwareProfile, ModelFitScore, ModelMeta } from "@/lib/modelfit";
import {
  fetchHardware,
  fetchRecommendations,
  fetchScore,
} from "@/lib/modelfit";
import { HardwareCard } from "@/components/modelfit/HardwareCard";
import { ModelFitScoreCard } from "@/components/modelfit/ModelFitScoreCard";
import { ModelSearch } from "@/components/modelfit/ModelSearch";
import { BenchmarkLab } from "@/components/modelfit/BenchmarkLab";
import { ComparisonTable } from "@/components/modelfit/ComparisonTable";
import { DiscoverTab } from "@/components/modelfit/DiscoverTab";

const TASK_TABS = [
  { id: "rag", label: "RAG" },
  { id: "coding", label: "Coding" },
  { id: "agents", label: "Agents" },
  { id: "summarization", label: "Summarization" },
];

const NAV_TABS = [
  "Discover & Setup",
  "Hardware",
  "Models",
  "Recommended",
  "Score Cards",
  "Benchmark Lab",
  "Comparison",
] as const;
type NavTab = (typeof NAV_TABS)[number];

export default function ModelFitPage() {
  const [tab, setTab] = useState<NavTab>("Discover & Setup");
  const [hw, setHw] = useState<HardwareProfile | null>(null);
  const [hwLoading, setHwLoading] = useState(true);
  const [hwError, setHwError] = useState<string | null>(null);

  const [recTask, setRecTask] = useState("rag");
  const [recs, setRecs] = useState<ModelFitScore[]>([]);
  const [recsLoading, setRecsLoading] = useState(false);

  const [selectedModel, setSelectedModel] = useState<ModelMeta | null>(null);
  const [scores, setScores] = useState<ModelFitScore[]>([]);
  const [scoringModel, setScoringModel] = useState<string | null>(null);

  useEffect(() => {
    fetchHardware()
      .then(setHw)
      .catch((e) => setHwError(String(e)))
      .finally(() => setHwLoading(false));
  }, []);

  async function loadRecs() {
    setRecsLoading(true);
    try {
      const r = await fetchRecommendations(recTask, 6);
      setRecs(r.recommendations);
    } catch {
      setRecs([]);
    } finally {
      setRecsLoading(false);
    }
  }

  useEffect(() => {
    if (tab === "Recommended") loadRecs();
  }, [tab, recTask]);

  async function scoreModel(model: ModelMeta) {
    setSelectedModel(model);
    setScoringModel(model.model_id);
    try {
      const s = await fetchScore(model.model_id);
      setScores((prev) => {
        const next = prev.filter((x) => x.model_id !== s.model_id);
        return [s, ...next];
      });
    } catch {
      // ignore
    } finally {
      setScoringModel(null);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Top bar */}
      <div className="border-b border-zinc-800 px-6 py-4 flex items-center gap-4">
        <Link
          href="/"
          className="flex items-center gap-1.5 rounded border border-zinc-700 px-2.5 py-1 text-xs text-zinc-400 hover:text-zinc-200 hover:border-zinc-500 transition-colors shrink-0"
          title="Back to chat"
        >
          ← Chat
        </Link>
        <h1 className="text-lg font-bold tracking-tight">
          Auralynq <span className="text-sky-400">ModelFit</span> Index
        </h1>
        <span className="hidden text-xs text-zinc-500 sm:inline">
          Hardware-aware model selection for local RAG
        </span>
      </div>

      {/* Nav */}
      <div className="border-b border-zinc-800 px-6 flex gap-1 overflow-x-auto">
        {NAV_TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-sm border-b-2 transition-colors whitespace-nowrap ${
              tab === t
                ? "border-sky-500 text-sky-400"
                : "border-transparent text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Discover & Setup tab */}
        {tab === "Discover & Setup" && <DiscoverTab />}

        {/* Hardware tab */}
        {tab === "Hardware" && (
          <div className="max-w-lg space-y-4">
            <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">
              Local Hardware
            </h2>
            {hwLoading && <p className="text-zinc-500 text-sm">Probing hardware…</p>}
            {hwError && (
              <p className="text-red-400 text-sm">Could not detect hardware: {hwError}</p>
            )}
            {hw && <HardwareCard hw={hw} />}
            {hw && (
              <div className="rounded-xl border border-zinc-700 bg-zinc-900 p-4 space-y-2 text-sm">
                <p className="text-zinc-400 font-semibold">Inference capabilities</p>
                <ul className="space-y-1 text-xs text-zinc-300">
                  <li>
                    Best backend:{" "}
                    <span className="font-mono text-sky-400">{hw.best_backend.toUpperCase()}</span>
                  </li>
                  {hw.total_vram_gb > 0 && (
                    <li>
                      Total VRAM:{" "}
                      <span className="font-mono">{hw.total_vram_gb} GB</span>
                    </li>
                  )}
                  <li>
                    Ollama:{" "}
                    <span className={hw.ollama_available ? "text-emerald-400" : "text-zinc-500"}>
                      {hw.ollama_available ? `available (${hw.ollama_version})` : "not detected"}
                    </span>
                  </li>
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Models tab */}
        {tab === "Models" && (
          <div className="space-y-4">
            <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">
              Model Search
            </h2>
            <ModelSearch
              onSelect={(m) => {
                scoreModel(m);
                setTab("Score Cards");
              }}
            />
          </div>
        )}

        {/* Recommended tab */}
        {tab === "Recommended" && (
          <div className="space-y-5">
            <div className="flex items-center gap-4">
              <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">
                Recommended for my hardware
              </h2>
              <div className="flex gap-1">
                {TASK_TABS.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setRecTask(t.id)}
                    className={`px-3 py-1 rounded text-xs ${
                      recTask === t.id
                        ? "bg-sky-800 text-sky-200"
                        : "text-zinc-500 hover:text-zinc-300"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
            {recsLoading && <p className="text-sm text-zinc-500">Scoring models…</p>}
            {!recsLoading && recs.length === 0 && (
              <p className="text-sm text-zinc-500">No recommendations available.</p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {recs.map((r) => (
                <div
                  key={r.model_id}
                  className="cursor-pointer hover:ring-1 hover:ring-sky-700 rounded-xl transition-all"
                  onClick={() => {
                    setScores((prev) => {
                      const next = prev.filter((x) => x.model_id !== r.model_id);
                      return [r, ...next];
                    });
                    setTab("Score Cards");
                  }}
                >
                  <ModelFitScoreCard score={r} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Score Cards tab */}
        {tab === "Score Cards" && (
          <div className="space-y-5">
            <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">
              ModelFit Score Cards
            </h2>
            {scoringModel && (
              <p className="text-sm text-zinc-500">Scoring {scoringModel}…</p>
            )}
            {scores.length === 0 && !scoringModel && (
              <p className="text-sm text-zinc-500">
                Select models from the Models or Recommended tab to see their score cards here.
              </p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {scores.map((s) => (
                <ModelFitScoreCard key={s.model_id} score={s} showDetails />
              ))}
            </div>
          </div>
        )}

        {/* Benchmark Lab tab */}
        {tab === "Benchmark Lab" && (
          <div className="space-y-4">
            <div className="space-y-1">
              <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">
                Benchmark Lab
              </h2>
              <p className="text-xs text-zinc-500">
                Benchmarks require explicit confirmation. No models are downloaded automatically.
                Always preview before running.
              </p>
            </div>
            <BenchmarkLab
              defaultModelId={selectedModel?.ollama_tag ? `ollama:${selectedModel.ollama_tag}` : ""}
            />
          </div>
        )}

        {/* Comparison tab */}
        {tab === "Comparison" && (
          <div className="space-y-4">
            <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">
              Model Comparison
            </h2>
            <ComparisonTable scores={scores} />
          </div>
        )}
      </div>
    </div>
  );
}
