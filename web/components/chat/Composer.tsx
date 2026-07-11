"use client";
import { useEffect, useRef } from "react";
import { VoiceRecorder } from "@/components/VoiceRecorder";
import { AlgorithmSelector } from "@/components/chat/AlgorithmSelector";

export type ChatMode = "corpus" | "web" | "inventory" | "summarize";

export const MODES: { id: ChatMode; label: string; hint: string; enabled: boolean }[] = [
  { id: "corpus",    label: "Ask corpus", hint: "Grounded answer from your indexed documents",              enabled: true  },
  { id: "summarize", label: "Summarize",  hint: "Summarize the topic across the corpus",                    enabled: true  },
  { id: "inventory", label: "Inventory",  hint: "What's in your collection (docs, types, languages)",       enabled: true  },
  { id: "web",       label: "Web",        hint: "Disabled — enable a web provider to use",                  enabled: false },
];

const PLACEHOLDER: Record<ChatMode, string> = {
  corpus:    "Ask Auralynq about your documents…",
  summarize: "Summarize a topic (e.g. 'key findings on infection control')…",
  inventory: "Ask about your collection (e.g. 'any Arabic documents?')…",
  web:       "Web search is disabled",
};

export function Composer({
  input,
  setInput,
  mode,
  setMode,
  streaming,
  onSend,
  onStop,
  onVoiceResult,
  onUploadClick,
  ragStrategy,
  onRagStrategyChange,
}: {
  input: string;
  setInput: (v: string) => void;
  mode: ChatMode;
  setMode: (m: ChatMode) => void;
  streaming: boolean;
  onSend: (q: string) => void;
  onStop: () => void;
  onVoiceResult: (r: any) => void;
  onUploadClick: () => void;
  ragStrategy: string;
  onRagStrategyChange: (id: string) => void;
}) {
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 180)}px`;
  }, [input]);

  return (
    <div className="border-t border-edge bg-panel/95 px-3 py-3 backdrop-blur md:px-4">
      {/* Mode tabs + algorithm selector */}
      <div className="mb-2.5 flex items-center gap-1 overflow-x-auto">
        <div className="flex items-center rounded-xl border border-edge bg-panel2/70 p-0.5">
          {MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              disabled={!m.enabled}
              onClick={() => m.enabled && setMode(m.id)}
              aria-pressed={mode === m.id}
              title={m.hint}
              className={`rounded-lg px-3 py-1 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${
                mode === m.id
                  ? "bg-panel shadow-sm text-brand border border-brand/20"
                  : "text-fg3 hover:text-fg"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
        <div className="ml-auto shrink-0">
          <AlgorithmSelector value={ragStrategy} onChange={onRagStrategyChange} />
        </div>
      </div>

      {/* Composer card */}
      <div className="rounded-2xl border border-edge bg-panel2 shadow-sm transition-shadow focus-within:border-brand/50 focus-within:shadow-md">
        {/* Voice recorder row */}
        <div className="border-b border-edge/50 px-3 py-2">
          <VoiceRecorder onResult={onVoiceResult} compact />
        </div>

        {/* Text input row */}
        <form
          className="flex items-end gap-2 p-2"
          onSubmit={(e) => {
            e.preventDefault();
            onSend(input);
          }}
        >
          <button
            type="button"
            onClick={onUploadClick}
            aria-label="Upload a document"
            title="Upload a document"
            className="mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-edge bg-panel text-fg2 transition hover:border-brand/40 hover:text-brand"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4"
              aria-hidden
            >
              <path d="M12 16V4m0 0L8 8m4-4 4 4M5 20h14" />
            </svg>
          </button>

          <textarea
            ref={taRef}
            value={input}
            rows={1}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSend(input);
              }
            }}
            placeholder={PLACEHOLDER[mode]}
            aria-label="Ask a question"
            className="scroll-thin max-h-44 flex-1 resize-none bg-transparent px-2 py-2 text-sm leading-relaxed text-fg outline-none placeholder:text-fg3"
          />

          {streaming ? (
            <button
              type="button"
              onClick={onStop}
              className="btn-ghost mb-0.5 text-sm"
              aria-label="Stop generating (Esc)"
            >
              <span className="text-[10px]">◼</span> Stop
            </button>
          ) : (
            <button
              className="btn-cta mb-0.5 text-sm"
              disabled={!input.trim()}
              aria-label="Send"
            >
              Ask →
            </button>
          )}
        </form>
      </div>

      {/* Keyboard hint */}
      <div className="mt-1.5 flex items-center justify-between px-1 text-[11px] text-fg3">
        <span>
          <kbd className="rounded border border-edge bg-panel2 px-1 py-px">Enter</kbd> send ·{" "}
          <kbd className="rounded border border-edge bg-panel2 px-1 py-px">Shift↵</kbd> new line
        </span>
        <span className="hidden sm:inline opacity-70">Local-first · grounded · cited</span>
      </div>
    </div>
  );
}
