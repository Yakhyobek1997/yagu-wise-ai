"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  Activity,
  ArrowRight,
  AudioLines,
  Box,
  Database,
  FileText,
  Github,
  Grid3X3,
  Layers3,
  LockKeyhole,
  Mic,
  Network,
  Send,
  ShieldCheck,
} from "lucide-react";
import { statusSummary, type StatusResponse } from "@/lib/api";

const REPO = "https://github.com/Yakhyobek1997/yagu-wise-ai";

type Health = "healthy" | "degraded" | "offline" | "checking";

type StatusCard = {
  key: string;
  label: string;
  value: string;
  health: Health;
  icon: LucideIcon;
};

type ExtendedStatus = StatusResponse & {
  corpus: StatusResponse["corpus"] & { indexed_document_count?: number };
};

const BENEFITS: { label: string; icon: LucideIcon }[] = [
  { label: "Voice-native", icon: AudioLines },
  { label: "PathRAG", icon: Network },
  { label: "Grounded", icon: ShieldCheck },
  { label: "Observable", icon: Activity },
  { label: "Provider-agnostic", icon: Layers3 },
];

const STATS = [
  { value: "$0", label: "Default cost" },
  { value: "100%", label: "Local-capable" },
  { value: "7", label: "MCP tools" },
  { value: "<1s", label: "Fast-route answers" },
];

const SPARKLINES = [
  "2,30 14,26 24,32 36,22 48,27 59,18 72,24 83,12 96,19 107,5 120,14 132,8 145,18",
  "2,30 14,27 25,32 38,24 50,29 62,20 75,24 87,13 98,20 111,5 123,17 134,11 145,18",
  "2,29 14,25 27,31 39,23 51,27 64,18 76,24 89,12 101,20 114,4 127,15 139,10 145,18",
  "2,30 15,26 27,31 40,22 53,28 65,17 78,24 91,11 103,19 116,4 129,15 141,9 145,17",
  "2,31 15,26 28,30 41,21 54,27 67,16 80,23 93,10 106,18 119,3 132,14 145,9",
  "2,30 15,24 27,31 40,21 53,28 66,17 79,24 92,13 105,20 118,7 131,17 145,12",
  "2,30 14,26 27,31 40,22 53,28 66,18 79,24 92,12 105,20 118,5 131,15 145,10",
];

function provider(status: StatusResponse, subsystem: string): string | null {
  const value = status.providers.find((row) => row.subsystem === subsystem)?.provider;
  return value && value !== "null" ? value : null;
}

function cardsFromStatus(status: ExtendedStatus): StatusCard[] {
  const vectors = status.index?.vectors ?? status.corpus?.vector_count ?? 0;
  const documents = status.corpus?.indexed_document_count ?? (vectors > 0 ? 1 : 0);
  const embeddings = provider(status, "embeddings");
  const vector = provider(status, "vector_store");
  const llm = provider(status, "llm");
  const asr = provider(status, "asr");
  const tts = provider(status, "tts");
  const tracing = status.tracing?.provider || "in-process";

  return [
    { key: "api", label: "API", value: "FastAPI - online", health: "healthy", icon: Box },
    {
      key: "corpus",
      label: "Corpus",
      value: documents ? `${documents} document${documents === 1 ? "" : "s"} indexed` : "Ready for documents",
      health: documents ? "healthy" : "degraded",
      icon: FileText,
    },
    {
      key: "vector",
      label: "Vector DB",
      value: `${vector || "memory"} - ${vectors.toLocaleString()} vectors`,
      health: vectors ? "healthy" : "degraded",
      icon: Database,
    },
    {
      key: "embeddings",
      label: "Embeddings",
      value: embeddings || "not configured",
      health: embeddings ? "healthy" : "degraded",
      icon: Grid3X3,
    },
    {
      key: "llm",
      label: "LLM",
      value: llm || "not configured",
      health: llm ? "healthy" : "degraded",
      icon: ShieldCheck,
    },
    {
      key: "voice",
      label: "ASR / TTS",
      value: asr || tts ? `${asr || "off"} - ${tts || "off"}` : "offline fallback",
      health: asr || tts ? "healthy" : "degraded",
      icon: Mic,
    },
    { key: "tracing", label: "Tracing", value: tracing, health: "healthy", icon: Activity },
  ];
}

function waitingCards(health: Health = "checking"): StatusCard[] {
  const definitions: Array<[string, string, LucideIcon]> = [
    ["api", "API", Box],
    ["corpus", "Corpus", FileText],
    ["vector", "Vector DB", Database],
    ["embeddings", "Embeddings", Grid3X3],
    ["llm", "LLM", ShieldCheck],
    ["voice", "ASR / TTS", Mic],
    ["tracing", "Tracing", Activity],
  ];

  return definitions.map(([key, label, icon]) => ({
    key,
    label,
    value: health === "offline" ? "unreachable" : "checking...",
    health,
    icon,
  }));
}

function ChatPreview() {
  return (
    <div className="glass overflow-hidden border-edge2 shadow-glow">
      <div className="flex h-12 items-center gap-2 border-b border-edge bg-panel2/60 px-4">
        <span className="h-2.5 w-2.5 rounded-full bg-bad" />
        <span className="h-2.5 w-2.5 rounded-full bg-warn" />
        <span className="h-2.5 w-2.5 rounded-full bg-ok" />
        <span className="ml-2 text-xs font-medium text-fg3">yaguwiseai / chat</span>
        <span className="pill pill-ok ml-auto">
          <span className="h-1.5 w-1.5 rounded-full bg-ok" /> Live
        </span>
      </div>

      <div className="space-y-3.5 p-5">
        <div className="flex justify-end">
          <div className="max-w-[78%] rounded-2xl rounded-br-md border border-brand2/25 bg-brand2/15 px-4 py-3 text-sm text-fg">
            How does PathRAG prune relational paths?
          </div>
        </div>

        <div className="rounded-2xl border border-edge bg-panel2/80 p-4">
          <div className="mb-3 flex flex-wrap items-center gap-2 text-[11px]">
            <span className="tag border-brand2/30 bg-brand2/10 text-brand2">deep - graph</span>
            <span className="text-fg3">relational query to graph traversal</span>
          </div>
          <p className="text-sm leading-6 text-fg2">
            PathRAG scores candidate paths with a flow-based reliability metric, then prunes low-flow edges so only the most load-bearing relational chains reach the LLM
            <sup className="ml-0.5 text-brand">1</sup>.
          </p>
          <div className="mt-3 flex flex-wrap gap-2 text-[10px] text-fg3">
            <span className="tag">[1] pathrag.pdf - p.4 - 0.91</span>
            <span className="tag border-brand2/25 bg-brand2/10">Paris to capital_of to France</span>
          </div>
        </div>

        <div className="flex items-center gap-3 rounded-xl border border-edge bg-panel2/70 px-4 py-3">
          <span className="text-[11px] font-medium text-fg3">Evidence coverage</span>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-edge">
            <div className="h-full w-[82%] rounded-full bg-gradient-to-r from-brand to-brand2" />
          </div>
          <span className="text-xs font-semibold text-fg">82%</span>
        </div>

        <div className="flex items-center gap-3 rounded-xl border border-edge bg-panel2/80 px-4 py-3 text-sm text-fg3">
          <Mic className="h-4 w-4 text-brand" />
          <span className="flex-1">Ask YaguWise AI...</span>
          <span className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-brand to-brand2 text-[#06231e]">
            <Send className="h-4 w-4" />
          </span>
        </div>

        <div className="flex items-center justify-center gap-2 pt-0.5 text-[11px] text-fg3">
          <ShieldCheck className="h-4 w-4 text-brand" /> Cited. Grounded. Observable.
        </div>
      </div>
    </div>
  );
}

function StatusGrid() {
  const [cards, setCards] = useState<StatusCard[]>(waitingCards());
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    statusSummary()
      .then((status) => {
        setOnline(true);
        setCards(cardsFromStatus(status as ExtendedStatus));
      })
      .catch(() => {
        setOnline(false);
        setCards(waitingCards("offline"));
      });
  }, []);

  return (
    <section className="border-t border-edge px-3 pb-5 pt-5 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1536px]">
        <div className="mb-3 flex items-center justify-between gap-3">
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-ok">
            <span className="h-2 w-2 rounded-full bg-ok shadow-glow" /> Live system status
          </p>
          <span className={`pill ${online === false ? "pill-bad" : "pill-ok"}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${online === false ? "bg-bad" : "bg-ok"}`} />
            {online === null ? "Connecting" : online ? "API online" : "API offline"}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4 xl:grid-cols-7">
          {cards.map((card, index) => {
            const Icon = card.icon;
            const warning = card.health === "degraded";
            const down = card.health === "offline";
            const accent = warning ? "text-warn" : down ? "text-bad" : "text-ok";
            const pill = warning ? "pill-warn" : down ? "pill-bad" : card.health === "checking" ? "pill-neutral" : "pill-ok";
            return (
              <article key={card.key} className="min-w-0 rounded-xl border border-edge bg-panel p-3 shadow-sm">
                <div className="flex items-center gap-2.5">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-edge bg-panel2 text-brand">
                    <Icon className="h-5 w-5" />
                  </span>
                  <div className="min-w-0">
                    <h3 className="truncate text-sm font-semibold text-fg">{card.label}</h3>
                    <p className="mt-1 truncate text-[11px] text-fg3" title={card.value}>{card.value}</p>
                  </div>
                </div>
                <span className={`pill mt-3 px-2 py-0.5 text-[10px] ${pill}`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${warning ? "bg-warn" : down ? "bg-bad" : "bg-ok"}`} />
                  {card.health === "checking" ? "Checking" : card.health === "degraded" ? "Degraded" : card.health === "offline" ? "Offline" : "Healthy"}
                </span>
                <svg className={`mt-2 h-9 w-full ${accent}`} viewBox="0 0 148 36" fill="none" preserveAspectRatio="none" aria-hidden>
                  <polyline points={SPARKLINES[index]} stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" strokeLinecap="round" />
                </svg>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export function LandingShowcase() {
  return (
    <section className="relative overflow-hidden border-b border-edge bg-ink">
      <div className="grid-bg pointer-events-none absolute inset-0 opacity-90" />
      <div className="orb -left-40 top-16 h-96 w-96 bg-brand/15" />
      <div className="orb -right-32 -top-16 h-[34rem] w-[34rem] bg-brand2/20" />

      <div className="relative mx-auto max-w-[1536px] px-3 pb-5 pt-5 sm:px-6 lg:px-8">
        <div className="grid min-h-[470px] items-center gap-10 lg:grid-cols-[1.04fr_0.96fr] lg:gap-14">
          <div className="py-5 lg:py-8">
            <span className="chip px-4 py-2">
              <LockKeyhole className="h-3.5 w-3.5 text-ok" />
              Local-first <span className="text-fg3">-</span> Private by default <span className="text-fg3">-</span> Open source
            </span>

            <h1 className="mt-7 max-w-4xl text-[clamp(3.25rem,5.4vw,5.35rem)] font-bold leading-[0.98] tracking-[-0.055em] text-fg">
              <span className="block">Grounded answers</span>
              <span className="block">from <span className="gradient-text">your private data.</span></span>
            </h1>

            <p className="mt-6 max-w-2xl text-base leading-7 text-fg2 sm:text-lg">
              Voice-native RAG that runs on your machine.<br className="hidden sm:block" />
              PathRAG evidence, grounded citations, and full pipeline observability - all local, all yours.
            </p>

            <div className="mt-7 flex flex-wrap gap-3">
              <Link href="/chat" className="btn-cta px-6 py-3.5 text-sm">
                Launch YaguWise AI <ArrowRight className="h-4 w-4" />
              </Link>
              <a href={REPO} target="_blank" rel="noopener noreferrer" className="btn-outline px-6 py-3.5 text-sm">
                <Github className="h-4 w-4" /> View on GitHub
              </a>
            </div>

            <ul className="mt-7 flex flex-wrap gap-x-7 gap-y-3">
              {BENEFITS.map(({ label, icon: Icon }) => (
                <li key={label} className="flex items-center gap-2 text-xs text-fg2 sm:text-sm">
                  <Icon className="h-4 w-4 text-brand" /> {label}
                </li>
              ))}
            </ul>
          </div>

          <div className="pb-5 lg:pb-0">
            <ChatPreview />
          </div>
        </div>

        <div className="glass mt-2 grid grid-cols-2 overflow-hidden border-edge2 md:grid-cols-4">
          {STATS.map((stat, index) => (
            <div key={stat.label} className={`relative px-5 py-5 text-center ${index > 0 ? "md:before:absolute md:before:inset-y-4 md:before:left-0 md:before:w-px md:before:bg-edge" : ""}`}>
              <div className="gradient-text text-3xl font-bold">{stat.value}</div>
              <div className="mt-1 text-[11px] uppercase tracking-[0.08em] text-fg3">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>

      <StatusGrid />
    </section>
  );
}
