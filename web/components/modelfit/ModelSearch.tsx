"use client";
import { useState } from "react";
import type { ModelMeta } from "@/lib/modelfit";
import { fetchModels, fetchInstalledModels } from "@/lib/modelfit";

const TASKS = ["chat", "rag", "coding", "summarization", "agents", "vision", "multilingual"];
const FAMILIES = ["llama", "qwen", "mistral", "gemma", "phi", "deepseek", "unknown"];

interface Filters {
  q: string;
  source: string;
  family: string;
  task: string;
  embedding_only: boolean;
  open_license: boolean;
}

export function ModelSearch({
  onSelect,
}: {
  onSelect?: (model: ModelMeta) => void;
}) {
  const [filters, setFilters] = useState<Filters>({
    q: "",
    source: "",
    family: "",
    task: "",
    embedding_only: false,
    open_license: false,
  });
  const [models, setModels] = useState<ModelMeta[]>([]);
  const [loading, setLoading] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [searched, setSearched] = useState(false);

  async function search() {
    setLoading(true);
    setWarnings([]);
    try {
      const result = await fetchModels({
        q: filters.q,
        source: filters.source || undefined,
        family: filters.family || undefined,
        task: filters.task || undefined,
        embedding_only: filters.embedding_only,
        open_license: filters.open_license,
        limit: 50,
      });
      setModels(result.models);
      setSearched(true);
    } catch (e) {
      setWarnings([String(e)]);
    } finally {
      setLoading(false);
    }
  }

  async function syncInstalled() {
    setLoading(true);
    try {
      const result = await fetchInstalledModels();
      setModels(result.models);
      setWarnings(result.warnings);
      setSearched(true);
    } catch (e) {
      setWarnings([String(e)]);
    } finally {
      setLoading(false);
    }
  }

  function set(key: keyof Filters, value: string | boolean) {
    setFilters((f) => ({ ...f, [key]: value }));
  }

  return (
    <div className="space-y-4">
      {/* Filter row */}
      <div className="flex flex-wrap gap-2">
        <input
          className="bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-sm text-zinc-100 placeholder-zinc-500 flex-1 min-w-[160px]"
          placeholder="Search models…"
          value={filters.q}
          onChange={(e) => set("q", e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
        />
        <select
          className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-sm text-zinc-300"
          value={filters.source}
          onChange={(e) => set("source", e.target.value)}
        >
          <option value="">All sources</option>
          <option value="ollama">Ollama</option>
          <option value="huggingface">Hugging Face</option>
          <option value="local">Local</option>
        </select>
        <select
          className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-sm text-zinc-300"
          value={filters.family}
          onChange={(e) => set("family", e.target.value)}
        >
          <option value="">All families</option>
          {FAMILIES.map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
        <select
          className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-sm text-zinc-300"
          value={filters.task}
          onChange={(e) => set("task", e.target.value)}
        >
          <option value="">All tasks</option>
          {TASKS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1.5 text-sm text-zinc-400 cursor-pointer">
          <input
            type="checkbox"
            checked={filters.open_license}
            onChange={(e) => set("open_license", e.target.checked)}
            className="accent-sky-500"
          />
          Open license
        </label>
      </div>

      <div className="flex gap-2">
        <button
          onClick={search}
          disabled={loading}
          className="px-4 py-1.5 rounded bg-sky-700 hover:bg-sky-600 text-sm text-white disabled:opacity-50"
        >
          {loading ? "Searching…" : "Search"}
        </button>
        <button
          onClick={syncInstalled}
          disabled={loading}
          className="px-4 py-1.5 rounded border border-zinc-600 hover:border-zinc-400 text-sm text-zinc-300 disabled:opacity-50"
        >
          Sync Ollama installs
        </button>
      </div>

      {warnings.map((w, i) => (
        <p key={i} className="text-xs text-amber-400">
          ⚠ {w}
        </p>
      ))}

      {searched && models.length === 0 && (
        <p className="text-sm text-zinc-500">No models found.</p>
      )}

      {models.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-zinc-300">
            <thead>
              <tr className="text-left text-xs text-zinc-500 border-b border-zinc-800">
                <th className="pb-2 pr-4">Model</th>
                <th className="pb-2 pr-4">Family</th>
                <th className="pb-2 pr-4">Params</th>
                <th className="pb-2 pr-4">Context</th>
                <th className="pb-2 pr-4">Tasks</th>
                <th className="pb-2 pr-4">License</th>
                <th className="pb-2">Source</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m) => (
                <tr
                  key={m.model_id}
                  className="border-b border-zinc-800/50 hover:bg-zinc-800/50 cursor-pointer"
                  onClick={() => onSelect?.(m)}
                >
                  <td className="py-2 pr-4 font-mono text-xs text-zinc-100">
                    {m.display_name}
                    {m.gated && (
                      <span className="ml-1 text-amber-400 text-[10px]">[gated]</span>
                    )}
                    {m.embedding && (
                      <span className="ml-1 text-sky-400 text-[10px]">[embed]</span>
                    )}
                  </td>
                  <td className="py-2 pr-4 text-xs">{m.family}</td>
                  <td className="py-2 pr-4 text-xs font-mono">
                    {m.parameter_count_b != null ? `${m.parameter_count_b}B` : "?"}
                  </td>
                  <td className="py-2 pr-4 text-xs font-mono">
                    {m.context_length != null
                      ? `${(m.context_length / 1000).toFixed(0)}K`
                      : "?"}
                  </td>
                  <td className="py-2 pr-4 text-xs">{m.tasks.slice(0, 3).join(", ")}</td>
                  <td className="py-2 pr-4 text-xs">{m.license}</td>
                  <td className="py-2 text-xs text-zinc-500">{m.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
