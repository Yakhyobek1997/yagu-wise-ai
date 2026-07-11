import type { ReactNode } from "react";

function Icon({ children, tint }: { children: ReactNode; tint: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`h-6 w-6 ${tint}`}
      aria-hidden
    >
      {children}
    </svg>
  );
}

const FEATURES = [
  {
    title: "Compounding Wiki — knowledge that accumulates",
    body: "Beyond query-time RAG: as you ingest, Auralynq synthesizes durable, cited entity pages from the knowledge graph — compiled once, kept current. Answers consult these pre-built pages and file good answers back, so exploration compounds. When a new source contradicts a prior claim, it's flagged and dated (invalidate-not-delete) — never silently overwritten.",
    tint: "text-accent",
    ring: "ring-accent/15",
    icon: (tint: string) => (
      <Icon tint={tint}>
        <path d="M4 5a2 2 0 0 1 2-2h9l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z" />
        <path d="M14 3v5h5M8 12h6M8 16h4" />
      </Icon>
    ),
  },
  {
    title: "Span-level visual grounding",
    body: "Every citation resolves to an exact bounding box on the original PDF page, rendered in a full-screen Source Workspace at 144 DPI. Verify any claim against the pixels — not just a page number. Staged span → page → unavailable so you always know the grounding quality.",
    tint: "text-brand2",
    ring: "ring-brand2/15",
    icon: (tint: string) => (
      <Icon tint={tint}>
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <rect x="7" y="8" width="7" height="4" rx="1" />
        <path d="M7 15h10" />
      </Icon>
    ),
  },
  {
    title: "Hardware-aware ModelFit Index",
    body: "Profiles your VRAM, RAM and backend, then scores every candidate model with a will-it-run verdict and a 0–100 fit score. Surfaces the best model for your actual box — the ModelFitChip shows it on every answer. No model is ever downloaded without your confirmation.",
    tint: "text-accent",
    ring: "ring-accent/15",
    icon: (tint: string) => (
      <Icon tint={tint}>
        <rect x="6" y="6" width="12" height="12" rx="1" />
        <path d="M9 3v2M15 3v2M9 19v2M15 19v2M3 9h2M3 15h2M19 9h2M19 15h2M10 10h4v4h-4z" />
      </Icon>
    ),
  },
  {
    title: "Voice-native document chat",
    body: "Speak your question and hear the grounded answer back. Whisper ASR, speaker diarization and TTS are first-class — with deterministic offline fallbacks, no cloud required.",
    tint: "text-brand",
    ring: "ring-brand/15",
    icon: (tint: string) => (
      <Icon tint={tint}>
        <rect x="9" y="3" width="6" height="11" rx="3" />
        <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
      </Icon>
    ),
  },
  {
    title: "Grounded answers with citations",
    body: "Every claim links back to its source — document, page, speaker, timestamp. When retrieval coverage falls below threshold, the pipeline emits an abstention signal with diagnostic snippets rather than generating a low-confidence response.",
    tint: "text-brand2",
    ring: "ring-brand2/15",
    icon: (tint: string) => (
      <Icon tint={tint}>
        <path d="M4 5a2 2 0 0 1 2-2h9l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z" />
        <path d="M14 3v5h5M8 13h8M8 17h5" />
      </Icon>
    ),
  },
  {
    title: "PathRAG graph reasoning",
    body: "Builds a knowledge graph from your corpus and traverses flow-pruned relational paths, so multi-hop questions get reasoned answers — not keyword soup.",
    tint: "text-accent",
    ring: "ring-accent/15",
    icon: (tint: string) => (
      <Icon tint={tint}>
        <circle cx="5" cy="6" r="2" />
        <circle cx="19" cy="6" r="2" />
        <circle cx="12" cy="18" r="2" />
        <path d="M7 6h10M6 8l5 8M18 8l-5 8" />
      </Icon>
    ),
  },
  {
    title: "Hybrid retrieval & reranking",
    body: "Dense + sparse search fused with reciprocal-rank fusion, a cross-encoder reranker, MMR de-duplication and lost-in-the-middle reordering for precise context.",
    tint: "text-brand",
    ring: "ring-brand/15",
    icon: (tint: string) => (
      <Icon tint={tint}>
        <path d="M3 6h18M6 12h12M9 18h6" />
      </Icon>
    ),
  },
  {
    title: "Agent trace & observability",
    body: "An adaptive router picks fast vector search or deep graph traversal, runs a self-checking loop, and shows you the full reasoning trace, latencies and evidence paths.",
    tint: "text-accent2",
    ring: "ring-accent2/15",
    icon: (tint: string) => (
      <Icon tint={tint}>
        <path d="M3 12h4l3 8 4-16 3 8h4" />
      </Icon>
    ),
  },
  {
    title: "Local-first provider routing",
    body: "Runs entirely on your machine via rootless Podman — no account, no bill. Bring your own keys (Cohere, OpenAI, Anthropic) to upgrade any single layer when you want.",
    tint: "text-brand2",
    ring: "ring-brand2/15",
    icon: (tint: string) => (
      <Icon tint={tint}>
        <rect x="3" y="4" width="18" height="12" rx="2" />
        <path d="M7 20h10M9 16v4M15 16v4" />
      </Icon>
    ),
  },
];

export function Features() {
  return (
    <section id="features" className="relative mx-auto max-w-7xl px-4 py-14 md:px-6">
      <div className="mb-12 max-w-2xl">
        <p className="overline mb-2">Capabilities</p>
        <h2 className="section-title">Full-stack retrieval-augmented generation — single local binary, measurable at every layer</h2>
        <p className="mt-3 text-lg text-fg2">
          Encode, retrieve, rerank, synthesize — every stage instrumented and swappable.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f) => (
          <div key={f.title} className={`card card-hover group ring-1 ${f.ring} p-6`}>
            <div className="mb-4 inline-flex rounded-xl border border-edge bg-panel2 p-2.5">
              {f.icon(f.tint)}
            </div>
            <h3 className="mb-2 text-lg font-semibold text-fg">{f.title}</h3>
            <p className="text-sm leading-relaxed text-fg2">{f.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
