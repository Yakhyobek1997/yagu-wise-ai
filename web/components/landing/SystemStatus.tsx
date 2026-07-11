"use client";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { statusSummary } from "@/lib/api";

type Health = "healthy" | "degraded" | "offline" | "checking";

interface Group {
  key: string;
  label: string;
  value: string;
  health: Health;
  icon: ReactNode;
}

const ICON: Record<string, ReactNode> = {
  api: <path d="M4 7h16M4 12h16M4 17h10" />,
  corpus: <path d="M4 5a2 2 0 0 1 2-2h9l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z M14 3v5h5" />,
  vector: <path d="M12 3v18M5 7l7-4 7 4M5 17l7 4 7-4M5 7v10M19 7v10" />,
  embeddings: <path d="M6 6h.01M12 6h.01M18 6h.01M6 12h.01M12 12h.01M18 12h.01M6 18h.01M12 18h.01M18 18h.01" />,
  llm: <path d="M12 2a7 7 0 0 0-4 12.74V18a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2v-3.26A7 7 0 0 0 12 2ZM9 22h6" />,
  voice: <path d="M9 3h6v8a3 3 0 0 1-6 0Z M5 11a7 7 0 0 0 14 0M12 18v3" />,
  tracing: <path d="M3 12h4l3 8 4-16 3 8h4" />,
};

function Glyph({ name }: { name: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
      aria-hidden
    >
      {ICON[name]}
    </svg>
  );
}

const HEALTH_PILL: Record<Health, string> = {
  healthy: "pill-ok",
  degraded: "pill-warn",
  offline: "pill-bad",
  checking: "pill-neutral",
};
const HEALTH_LABEL: Record<Health, string> = {
  healthy: "Healthy",
  degraded: "Degraded",
  offline: "Offline",
  checking: "Checking…",
};

export function SystemStatus() {
  const [groups, setGroups] = useState<Group[] | null>(null);
  const [up, setUp] = useState<boolean | null>(null);

  useEffect(() => {
    statusSummary()
      .then((s) => {
        setUp(true);
        setGroups(buildGroups(s));
      })
      .catch(() => {
        setUp(false);
        setGroups(buildGroups(null));
      });
  }, []);

  const live: Group[] = groups ?? checkingGroups();

  return (
    <div className="mx-auto mt-12 max-w-5xl">
      <div className="mb-4 flex items-center justify-between px-1">
        <div>
          <p className="overline">Live system status</p>
          <p className="mt-1 text-sm text-fg3">Every subsystem, reported from your running stack.</p>
        </div>
        <span className={`pill ${up === null ? "pill-neutral" : up ? "pill-ok" : "pill-bad"}`}>
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              up === null ? "bg-fg3" : up ? "bg-ok animate-pulse-soft" : "bg-bad"
            }`}
          />
          {up === null ? "Connecting…" : up ? "API online" : "API offline"}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {live.map((g) => (
          <div key={g.key} className="card card-hover">
            <div className="flex items-start justify-between gap-2">
              <span className="inline-flex rounded-lg border border-edge bg-panel2 p-2 text-brand">
                <Glyph name={g.icon as string} />
              </span>
              <span className={`pill ${HEALTH_PILL[g.health]}`}>
                <span
                  className={`inline-block h-1.5 w-1.5 rounded-full ${
                    g.health === "healthy"
                      ? "bg-ok"
                      : g.health === "degraded"
                        ? "bg-warn"
                        : g.health === "offline"
                          ? "bg-bad"
                          : "bg-fg3"
                  }`}
                />
                {HEALTH_LABEL[g.health]}
              </span>
            </div>
            <h3 className="mt-3 text-sm font-semibold text-fg">{g.label}</h3>
            <p className="mt-0.5 truncate text-sm text-fg3" title={g.value}>
              {g.value}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- mapping the /status payload into the seven product subsystems --------

interface StatusPayload {
  providers?: { subsystem: string; provider: string }[];
  index?: { vectors?: number };
  corpus?: { indexed?: boolean; indexed_document_count?: number; vector_count?: number };
  tracing?: { provider?: string; enabled?: boolean; phoenix_endpoint?: string | null };
}

function provider(p: StatusPayload, key: string): string | null {
  const row = (p.providers || []).find((r) => r.subsystem === key);
  const v = row?.provider;
  return v && v !== "null" ? v : null;
}

function buildGroups(p: StatusPayload | null): Group[] {
  if (!p) {
    return checkingGroups().map((g) => ({ ...g, health: "offline" as Health, value: "unreachable" }));
  }
  const vectors = p.index?.vectors ?? p.corpus?.vector_count ?? 0;
  const docs = p.corpus?.indexed_document_count ?? 0;
  const indexed = !!p.corpus?.indexed || vectors > 0;

  const llm = provider(p, "llm");
  const vs = provider(p, "vector_store");
  const emb = provider(p, "embeddings");
  const asr = provider(p, "asr");
  const tts = provider(p, "tts");
  const tracingOn = !!p.tracing?.enabled;
  const tracingProv = p.tracing?.provider || (tracingOn ? "enabled" : "in-process");

  const presence = (v: string | null): Health => (v ? "healthy" : "degraded");

  return [
    { key: "api", label: "API", value: "FastAPI · online", health: "healthy", icon: "api" },
    {
      key: "corpus",
      label: "Corpus",
      value: indexed ? `${docs || "—"} document${docs === 1 ? "" : "s"} indexed` : "empty — ingest to begin",
      health: indexed ? "healthy" : "degraded",
      icon: "corpus",
    },
    {
      key: "vector",
      label: "Vector DB",
      value: vs ? `${vs} · ${vectors.toLocaleString()} vectors` : `${vectors.toLocaleString()} vectors`,
      health: vectors > 0 ? "healthy" : "degraded",
      icon: "vector",
    },
    { key: "embeddings", label: "Embeddings", value: emb || "not configured", health: presence(emb), icon: "embeddings" },
    { key: "llm", label: "LLM", value: llm || "not configured", health: presence(llm), icon: "llm" },
    {
      key: "voice",
      label: "ASR / TTS",
      value: asr || tts ? `${asr || "—"} · ${tts || "—"}` : "offline fallback",
      health: asr || tts ? "healthy" : "degraded",
      icon: "voice",
    },
    {
      key: "tracing",
      label: "Tracing",
      value: tracingProv,
      health: tracingOn ? "healthy" : "degraded",
      icon: "tracing",
    },
  ];
}

function checkingGroups(): Group[] {
  return [
    { key: "api", label: "API", icon: "api" },
    { key: "corpus", label: "Corpus", icon: "corpus" },
    { key: "vector", label: "Vector DB", icon: "vector" },
    { key: "embeddings", label: "Embeddings", icon: "embeddings" },
    { key: "llm", label: "LLM", icon: "llm" },
    { key: "voice", label: "ASR / TTS", icon: "voice" },
    { key: "tracing", label: "Tracing", icon: "tracing" },
  ].map((g) => ({ ...g, value: "checking…", health: "checking" as Health }));
}
