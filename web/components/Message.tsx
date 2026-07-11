"use client";
import Link from "next/link";
import type { Citation, CorpusSummary, InsufficientReason, ModelFitSnapshot } from "@/lib/api";
import { Citations } from "@/components/Citations";
import { ConfidenceBar } from "@/components/ConfidenceBar";
import { Markdown } from "@/components/Markdown";
import { CopyButton } from "@/components/CopyButton";
import { InsufficientEvidence } from "@/components/InsufficientEvidence";
import { CorpusInventory } from "@/components/CorpusInventory";

export interface Turn {
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  route?: string;
  rationale?: string;
  voice?: boolean;
  error?: boolean;
  status?: string;
  insufficient?: InsufficientReason | null;
  inventory?: CorpusSummary | null;
  question?: string;
  confidence?: number;
  semanticCoverage?: number;
  model_fit?: ModelFitSnapshot | null;
}

// Fit-level → semantic token (theme-aware across dark / light / comfort).
const FIT_COLOR: Record<string, string> = {
  "Excellent fit": "text-ok",
  "Recommended": "text-brand",
  "Usable with limits": "text-warn",
  "Not recommended": "text-warn",
  "Does not fit": "text-bad",
};

function ModelFitChip({ mf }: { mf: ModelFitSnapshot }) {
  const modelShort = mf.selected_model.replace(/^(ollama:|local:|hf:)/, "");
  const labelColor = FIT_COLOR[mf.fit_level ?? ""] ?? "text-fg3";
  return (
    <Link
      href="/modelfit"
      className="chip mt-2 !text-[11px] hover:border-edge2 transition-colors"
      title={`ModelFit: ${mf.fit_level ?? "scored"} — open ModelFit Index`}
    >
      <span className="text-fg3">model</span>
      <span className="max-w-[120px] truncate font-mono text-fg2">{modelShort}</span>
      {mf.fit_score != null && (
        <>
          <span className="text-fg3">·</span>
          <span className={`font-semibold ${labelColor}`}>{Math.round(mf.fit_score)}/100</span>
        </>
      )}
      {mf.quantization && (
        <>
          <span className="text-fg3">·</span>
          <span className="font-mono text-fg3">{mf.quantization}</span>
        </>
      )}
      {mf.estimated_vram_gb != null && (
        <>
          <span className="text-fg3">·</span>
          <span className="text-fg3">{mf.estimated_vram_gb.toFixed(1)} GB</span>
        </>
      )}
      {mf.estimate_used && <span className="italic text-fg3">est.</span>}
    </Link>
  );
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1 py-2" aria-label="Assistant is typing">
      <span className="typing-dot" />
      <span className="typing-dot" style={{ animationDelay: "0.18s" }} />
      <span className="typing-dot" style={{ animationDelay: "0.36s" }} />
    </span>
  );
}

const ROUTE_META: Record<string, { label: string; color: string; icon: string }> = {
  fast:   { label: "Fast retrieval",   color: "border-brand/40 text-brand",   icon: "⚡" },
  hybrid: { label: "Hybrid retrieval", color: "border-accent/40 text-accent",  icon: "◈" },
  graph:  { label: "Graph traversal",  color: "border-brand2/40 text-brand2", icon: "◎" },
};

function RouteTag({ route, rationale }: { route: string; rationale?: string }) {
  const meta = ROUTE_META[route] ?? { label: route, color: "border-edge text-fg3", icon: "·" };
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2 border-b border-edge/40 pb-3">
      <span className={`tag font-semibold ${meta.color}`}>
        <span aria-hidden>{meta.icon}</span>
        {meta.label}
      </span>
      {rationale && (
        <span className="truncate max-w-xs text-xs text-fg3" title={rationale}>
          {rationale}
        </span>
      )}
    </div>
  );
}

function AiDot() {
  return (
    <span
      className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand/30 to-brand2/30 ring-1 ring-brand/20 text-[10px] font-bold text-brand"
      aria-hidden
    >
      AI
    </span>
  );
}

export function Message({
  turn,
  streaming,
  isLast,
  onRegenerate,
  onAsk,
  onIngest,
  onOpenSource,
}: {
  turn: Turn;
  streaming: boolean;
  isLast: boolean;
  onRegenerate?: () => void;
  onAsk?: (q: string) => void;
  onIngest?: () => void;
  onOpenSource?: (marker: number) => void;
}) {
  if (turn.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-gradient-to-br from-brand2/25 to-brand/15 px-4 py-3 leading-relaxed shadow-sm ring-1 ring-brand2/20 text-fg">
          {turn.voice && (
            <span className="mr-1.5 text-xs opacity-60" aria-label="voice query">
              🎙
            </span>
          )}
          {turn.text}
        </div>
      </div>
    );
  }

  // Corpus-inventory answer renders its own card.
  if (turn.inventory) {
    return (
      <div className="flex items-start gap-2.5">
        <AiDot />
        <div className="flex-1 min-w-0 rounded-2xl rounded-tl-sm border border-edge bg-panel2 px-4 py-4 shadow-md">
          <CorpusInventory summary={turn.inventory} question={turn.question} />
        </div>
      </div>
    );
  }

  const empty = !turn.text;
  const live = streaming && isLast;
  const hasCitations = (turn.citations?.length ?? 0) > 0;

  return (
    <div className="group flex items-start gap-2.5">
      <AiDot />
      <div className="flex-1 min-w-0 rounded-2xl rounded-tl-sm border border-edge bg-panel2 px-4 py-3.5 shadow-md">
        {turn.route && <RouteTag route={turn.route} rationale={turn.rationale} />}

        {empty && live ? (
          <TypingDots />
        ) : turn.error ? (
          <p className="whitespace-pre-wrap leading-relaxed text-bad">{turn.text}</p>
        ) : (
          <div className="prose-answer">
            <Markdown
              text={turn.text}
              streaming={live}
              citations={turn.citations}
              onOpenCitation={onOpenSource}
            />
            {live && (
              <span className="ml-0.5 inline-block h-4 w-2 animate-pulse bg-brand/70 align-middle" />
            )}
          </div>
        )}

        {turn.insufficient && (
          <InsufficientEvidence reason={turn.insufficient} onAsk={onAsk} onIngest={onIngest} />
        )}

        {hasCitations && <Citations citations={turn.citations!} onOpenSource={onOpenSource} />}

        {!streaming && turn.model_fit && turn.model_fit.fit_score != null && (
          <ModelFitChip mf={turn.model_fit} />
        )}

        {!streaming && !turn.error && turn.confidence != null && turn.confidence > 0 && (
          <ConfidenceBar
            data={{
              overall: turn.confidence,
              semanticCoverage: turn.semanticCoverage,
            }}
          />
        )}

        {!streaming && !empty && !turn.error && (
          <div className="mt-2.5 flex items-center gap-4 opacity-0 transition-opacity duration-150 group-hover:opacity-100 focus-within:opacity-100">
            <CopyButton getText={() => turn.text} label="Copy" />
            {hasCitations && (
              <span className="text-xs text-fg3">
                {turn.citations!.length} source{turn.citations!.length === 1 ? "" : "s"}
              </span>
            )}
            {isLast && onRegenerate && (
              <button
                type="button"
                onClick={onRegenerate}
                aria-label="Regenerate answer"
                className="ml-auto inline-flex items-center gap-1 text-xs text-fg3 transition hover:text-brand"
              >
                ↻ Regenerate
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
