"use client";
import { useEffect, useRef, useState } from "react";
import { RAGStrategyInfo, fetchRAGStrategies } from "@/lib/api";

const LATENCY_CLS: Record<string, string> = {
  fast: "text-ok",
  medium: "text-warn",
  slow: "text-bad",
};

const STRATEGY_LS_KEY = "auralynq.rag_strategy.v1";

export function loadStoredStrategy(): string {
  try {
    return localStorage.getItem(STRATEGY_LS_KEY) || "auralynq_rag";
  } catch {
    return "auralynq_rag";
  }
}

export function saveStoredStrategy(id: string) {
  try {
    localStorage.setItem(STRATEGY_LS_KEY, id);
  } catch {
    /* ignore */
  }
}

type StatusGroup = "available" | "experimental" | "planned";

const GROUP_CONFIG: Record<StatusGroup, { label: string; dot: string; selectable: boolean }> = {
  available:    { label: "Available now",         dot: "bg-ok",   selectable: true },
  experimental: { label: "Experimental",          dot: "bg-warn", selectable: true },
  planned:      { label: "Planned / requires setup", dot: "bg-fg3", selectable: false },
};

function StrategyRow({
  s,
  selected,
  defaultId,
  onSelect,
}: {
  s: RAGStrategyInfo;
  selected: boolean;
  defaultId: string;
  onSelect: (id: string) => void;
}) {
  const isDefault = s.id === defaultId || s.id === "auralynq_rag";
  const selectable = s.status !== "planned" && s.available;
  const dimmed = !selectable;

  return (
    <button
      role="option"
      aria-selected={selected}
      onClick={() => selectable && onSelect(s.id)}
      disabled={!selectable}
      className={`flex w-full flex-col gap-0.5 px-3 py-2 text-left transition ${
        selected
          ? "bg-brand/10"
          : selectable
          ? "hover:bg-panel2"
          : "cursor-not-allowed opacity-50"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          {selected && (
            <span aria-hidden className="text-brand text-xs">✓</span>
          )}
          <span className={`text-xs font-medium ${selected ? "text-brand" : dimmed ? "text-fg3" : "text-fg"}`}>
            {s.name}
          </span>
          {isDefault && (
            <span className="rounded-full bg-brand/15 px-1.5 py-0 text-[9px] font-semibold text-brand">default</span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {!dimmed && (
            <span className={`text-[10px] font-medium ${LATENCY_CLS[s.expected_latency]}`}>
              {s.expected_latency}
            </span>
          )}
        </div>
      </div>
      <p className="text-[10px] leading-snug text-fg3 line-clamp-2">{s.description}</p>
      {/* Setup requirements for unavailable/planned strategies */}
      {(!selectable && s.unavailable_reason) && (
        <p className="mt-0.5 text-[10px] text-warn leading-snug">
          Requires: {s.unavailable_reason.slice(0, 80)}
        </p>
      )}
      {/* Feature tags for available/experimental */}
      {selectable && s.required_features.length > 0 && (
        <div className="mt-0.5 flex flex-wrap gap-0.5">
          {s.required_features.slice(0, 3).map(f => (
            <span key={f} className="tag text-[9px]">{f.replace(/_/g, " ")}</span>
          ))}
        </div>
      )}
    </button>
  );
}

export function AlgorithmSelector({
  value,
  onChange,
}: {
  value: string;
  onChange: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [strategies, setStrategies] = useState<RAGStrategyInfo[]>([]);
  const [defaultId, setDefaultId] = useState("auralynq_rag");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchRAGStrategies()
      .then(({ strategies, default_strategy }) => {
        setStrategies(strategies);
        setDefaultId(default_strategy);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const current = strategies.find(s => s.id === value);
  const displayName = current?.name || value.replace(/_/g, " ");
  const isDefault = value === defaultId || value === "auralynq_rag";

  // Group strategies by status
  const groups: Record<StatusGroup, RAGStrategyInfo[]> = {
    available: strategies.filter(s => s.status === "available"),
    experimental: strategies.filter(s => s.status === "experimental"),
    planned: strategies.filter(s => s.status === "planned"),
  };

  function select(id: string) {
    onChange(id);
    saveStoredStrategy(id);
    setOpen(false);
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
        aria-haspopup="listbox"
        title="Select RAG strategy"
        className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition ${
          isDefault
            ? "border-brand/40 bg-brand/10 text-brand"
            : "border-edge bg-panel2 text-fg2 hover:text-fg"
        }`}
      >
        <span aria-hidden>⚡</span>
        <span className="max-w-[120px] truncate">{displayName}</span>
        <span aria-hidden className="text-fg3">▾</span>
      </button>

      {open && (
        <div
          role="listbox"
          aria-label="RAG strategy"
          className="absolute bottom-full left-0 z-50 mb-2 max-h-[420px] w-80 overflow-y-auto rounded-xl border border-edge bg-panel shadow-lg"
        >
          <div className="sticky top-0 border-b border-edge bg-panel px-3 py-2">
            <p className="text-xs font-semibold text-fg">RAG Algorithm</p>
            <p className="text-[10px] text-fg3">Choose how Auralynq retrieves and answers</p>
          </div>

          {(Object.keys(GROUP_CONFIG) as StatusGroup[]).map(group => {
            const items = groups[group];
            if (items.length === 0) return null;
            const cfg = GROUP_CONFIG[group];
            return (
              <div key={group}>
                {/* Group header */}
                <div className="flex items-center gap-1.5 border-b border-edge/50 bg-panel2/50 px-3 py-1.5">
                  <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-fg3">
                    {cfg.label}
                  </span>
                  <span className="ml-auto text-[10px] text-fg3">{items.length}</span>
                </div>
                {items.map(s => (
                  <StrategyRow
                    key={s.id}
                    s={s}
                    selected={s.id === value}
                    defaultId={defaultId}
                    onSelect={select}
                  />
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
