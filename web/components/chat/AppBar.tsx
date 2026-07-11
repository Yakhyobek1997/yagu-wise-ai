"use client";
import Link from "next/link";
import { ThemeToggle } from "@/components/ThemeToggle";

function WaveformLogo({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden>
      <rect x="1"  y="9"  width="3" height="6"  rx="1.5" fill="currentColor" opacity="0.55" />
      <rect x="6"  y="6"  width="3" height="12" rx="1.5" fill="currentColor" opacity="0.75" />
      <rect x="11" y="2"  width="3" height="20" rx="1.5" fill="currentColor" />
      <rect x="16" y="6"  width="3" height="12" rx="1.5" fill="currentColor" opacity="0.75" />
      <rect x="21" y="9"  width="3" height="6"  rx="1.5" fill="currentColor" opacity="0.55" />
    </svg>
  );
}

function CorpusStats({ vectors, entities }: { vectors: number; entities?: number | null }) {
  return (
    <span className="hidden items-center gap-1.5 rounded-full border border-edge bg-panel2/80 px-2.5 py-0.5 text-xs md:inline-flex">
      <span className="h-1.5 w-1.5 rounded-full bg-ok" />
      <span className="font-medium text-fg">{vectors.toLocaleString()}</span>
      <span className="text-fg3">vectors</span>
      {entities != null && entities > 0 && (
        <>
          <span className="text-edge">·</span>
          <span className="font-medium text-fg">{entities.toLocaleString()}</span>
          <span className="text-fg3">entities</span>
        </>
      )}
    </span>
  );
}

export function AppBar({
  online,
  vectors,
  entities,
  onNewChat,
  onToggleInspector,
  inspectorOpen,
  onToggleSettings,
}: {
  online: boolean | null;
  vectors: number | null;
  entities?: number | null;
  onNewChat: () => void;
  onToggleInspector: () => void;
  inspectorOpen: boolean;
  onToggleSettings?: () => void;
}) {
  return (
    <header className="sticky top-0 z-40 border-b border-edge bg-ink/90 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-[1920px] items-center justify-between gap-3 px-3 md:px-5">
        {/* Left: logo + status */}
        <div className="flex min-w-0 items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-2 font-bold tracking-tight text-fg"
            aria-label="Auralynq home"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-brand/30 to-brand2/30 text-brand ring-1 ring-brand/20">
              <WaveformLogo className="h-4 w-4" />
            </span>
            <span className="hidden text-base sm:inline">
              <span className="text-brand">Aura</span>
              <span className="text-brand2">lynq</span>
            </span>
          </Link>

          <span
            className={`pill text-xs ${online === null ? "pill-neutral" : online ? "pill-ok" : "pill-bad"}`}
            title={online ? "Backend online" : online === false ? "Backend offline" : "Connecting…"}
          >
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${
                online === null
                  ? "bg-fg3"
                  : online
                  ? "animate-pulse-soft bg-ok"
                  : "bg-bad"
              }`}
            />
            {online === null ? "Connecting" : online ? "Online" : "Offline"}
          </span>

          {online && vectors !== null && (
            <CorpusStats vectors={vectors} entities={entities} />
          )}
        </div>

        {/* Right: actions */}
        <div className="flex items-center gap-1.5">
          <Link
            href="/modelfit"
            className="hidden items-center gap-1.5 rounded-lg border border-edge px-2.5 py-1 text-xs text-fg3 transition hover:border-sky-700 hover:text-sky-400 sm:inline-flex"
            title="ModelFit Index — hardware-aware model selection"
          >
            <svg viewBox="0 0 16 16" fill="currentColor" className="h-3 w-3" aria-hidden>
              <path d="M2 11a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 01-1 1H3a1 1 0 01-1-1v-2zM6 7a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1H7a1 1 0 01-1-1V7zM10 3a1 1 0 011-1h2a1 1 0 011 1v10a1 1 0 01-1 1h-2a1 1 0 01-1-1V3z" />
            </svg>
            ModelFit
          </Link>

          <ThemeToggle compact />

          {onToggleSettings && (
            <button
              type="button"
              onClick={onToggleSettings}
              className="btn-ghost px-2 py-1.5 text-sm"
              aria-label="Display settings"
              title="Display settings"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden>
                <path
                  fillRule="evenodd"
                  d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
          )}

          <button
            type="button"
            onClick={onToggleInspector}
            aria-pressed={inspectorOpen}
            className="btn-ghost text-sm lg:hidden"
            aria-label="Toggle inspector panel"
          >
            {inspectorOpen ? "Hide panel" : "Inspector"}
          </button>

          <button
            type="button"
            onClick={onNewChat}
            className="btn-brand text-sm"
            title="New chat (⌘K)"
            aria-label="Start a new chat (Ctrl/Cmd+K)"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="h-3.5 w-3.5" aria-hidden>
              <path d="M8 2v12M2 8h12" />
            </svg>
            <span className="hidden sm:inline">New chat</span>
          </button>
        </div>
      </div>
    </header>
  );
}
