// Stylized product mockup shown in the hero — "show the product", confidently.
export function ChatPreview() {
  return (
    <div className="glass relative w-full overflow-hidden p-0">
      {/* window chrome / app bar */}
      <div className="flex items-center gap-2 border-b border-edge bg-panel2/60 px-4 py-2.5">
        <span className="h-3 w-3 rounded-full bg-bad/70" />
        <span className="h-3 w-3 rounded-full bg-warn/70" />
        <span className="h-3 w-3 rounded-full bg-ok/70" />
        <span className="ml-2 text-xs font-medium text-fg3">auralynq · /chat</span>
        <span className="pill pill-ok ml-auto">
          <span className="h-1.5 w-1.5 rounded-full bg-ok animate-pulse-soft" /> live
        </span>
      </div>

      <div className="space-y-3 p-4 sm:p-5">
        {/* user bubble */}
        <div className="flex justify-end">
          <div className="max-w-[80%] rounded-2xl rounded-br-md bg-brand2/15 px-4 py-2 text-sm text-fg ring-1 ring-brand2/25">
            How does PathRAG prune relational paths?
          </div>
        </div>

        {/* assistant answer */}
        <div className="rounded-2xl rounded-bl-md border border-edge bg-panel2 px-4 py-3 text-sm shadow-sm">
          <div className="mb-2 flex items-center gap-2 text-[11px]">
            <span className="pill border-brand2/40 text-brand2">deep · graph</span>
            <span className="text-fg3">relational query → graph traversal</span>
          </div>
          <p className="leading-relaxed text-fg2">
            PathRAG scores candidate paths with a flow-based reliability metric, then prunes
            low-flow edges so only the most load-bearing relational chains reach the LLM
            <sup className="text-brand">[1]</sup>.
          </p>
          <div className="mt-3 flex flex-wrap gap-1.5 text-[10px]">
            <span className="chip">[1] pathrag.pdf · p.4 · 0.91</span>
            <span className="chip border-accent/30 text-accent">Paris →[capital_of]→ France</span>
          </div>
        </div>

        {/* evidence coverage micro-strip */}
        <div className="flex items-center gap-2 rounded-xl border border-edge bg-panel2/60 px-3 py-2">
          <span className="text-[11px] font-medium text-fg3">Evidence coverage</span>
          <div className="h-1.5 flex-1 rounded-full bg-edge">
            <div className="h-1.5 w-[82%] rounded-full bg-ok" />
          </div>
          <span className="text-[11px] font-semibold text-fg">82%</span>
        </div>

        {/* faux composer */}
        <div className="flex items-center gap-2 rounded-xl border border-edge bg-panel2 px-3 py-2 text-sm text-fg3">
          <span aria-hidden>🎙</span>
          <span className="flex-1">Ask Auralynq…</span>
          <span className="rounded-md bg-brand px-2.5 py-0.5 text-xs font-semibold text-[#06231e]">
            Ask
          </span>
        </div>
      </div>
    </div>
  );
}
