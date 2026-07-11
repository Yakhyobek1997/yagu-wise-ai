import type { ReactNode } from "react";

const POINTS: { title: string; body: string; icon: ReactNode }[] = [
  {
    title: "Compounding knowledge, not just retrieval",
    body: "Auralynq builds a persistent, cited wiki from your knowledge graph as you ingest — and flags when a new source contradicts a prior claim, keeping both with dates. Most RAG (and NotebookLM) re-derive everything each query and never tell you when your sources disagree.",
    icon: <path d="M4 5a2 2 0 0 1 2-2h9l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z M8 12h6M8 16h4M14 3v5h5" />,
  },
  {
    title: "Span-level visual source grounding",
    body: "Click any citation and the exact answer span is drawn as a bounding box on the original PDF page — pixel-accurate, not a fuzzy region highlight. No other open-source local RAG ties answer spans to visual proof this way.",
    icon: <path d="M4 5a2 2 0 0 1 2-2h9l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z M9 12h6M9 16h4M14 3v5h5" />,
  },
  {
    title: "Hardware-aware ModelFit Index",
    body: "Auralynq profiles your actual VRAM, RAM, and backend and scores every model with a will-it-run verdict — surfacing the best fit for your box, not the biggest or smallest. Nobody else in the local-RAG field ships predictive model selection.",
    icon: <path d="M9 3v2M15 3v2M9 19v2M15 19v2M3 9h2M3 15h2M19 9h2M19 15h2M6 6h12v12H6zM10 10h4v4h-4z" />,
  },
  {
    title: "Local-first by default",
    body: "Runs entirely on your machine via rootless Podman. No account, no telemetry you didn't opt into, $0 to start. Your documents never leave the box — no data shipped to anyone's cloud.",
    icon: <path d="M4 10V7a8 8 0 0 1 16 0v3M5 10h14a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2Z" />,
  },
  {
    title: "PPR-augmented PathRAG",
    body: "Our graph retriever blends flow-based path pruning with Personalised PageRank authority (0.4·flow + 0.6·ppr), fixing PathRAG's short-path bias. On multi-hop HotpotQA it lifts retrieval recall from 0.80 to 1.00.",
    icon: <path d="M5 6a2 2 0 1 0 0-.01M19 6a2 2 0 1 0 0-.01M12 18a2 2 0 1 0 0-.01M7 6h10M6 8l5 8M18 8l-5 8" />,
  },
  {
    title: "Evidence-gated abstention",
    body: "When lexical and semantic coverage both fall below threshold, the pipeline returns an abstention signal with retrieval diagnostics — retrieved passages, coverage scores, and gap analysis — rather than generating an unsupported output.",
    icon: <path d="M12 3 2 21h20L12 3ZM12 9v5M12 17h.01" />,
  },
  {
    title: "Auralynq-RAG: observable agentic pipeline",
    body: "Auralynq-RAG is our own RAG strategy: calibrated four-signal confidence, intent routing, evidence sufficiency control, citation validation, and hallucination risk scoring — with a full trace for every query, one of 13 runtime-switchable strategies.",
    icon: <path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 1-2-2V9m0 0h18" />,
  },
  {
    title: "Voice and text, one pipeline",
    body: "Spoken and typed questions flow through the same retrieval, grounding and citation path — so voice isn't a bolt-on demo, it's a first-class way to query your data.",
    icon: <path d="M9 3h6v8a3 3 0 0 1-6 0Z M5 11a7 7 0 0 0 14 0M12 18v3" />,
  },
  {
    title: "Open-source & provider-agnostic",
    body: "Apache-2.0 licensed, inspectable, swappable. Start fully local, then bring your own Cohere / OpenAI / Anthropic keys to upgrade any single layer without lock-in.",
    icon: <path d="M12 2 4 6v6c0 5 3.5 8 8 10 4.5-2 8-5 8-10V6l-8-4Z M9 12l2 2 4-4" />,
  },
];

function Glyph({ children }: { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5 text-brand"
      aria-hidden
    >
      {children}
    </svg>
  );
}

export function Differentiators() {
  return (
    <section id="why" className="relative mx-auto max-w-7xl px-4 py-14 md:px-6">
      <div className="mb-12 max-w-2xl">
        <p className="overline mb-2 text-accent">Why Auralynq</p>
        <h2 className="section-title">What makes Auralynq different?</h2>
        <p className="mt-3 text-lg text-fg2">
          Auralynq surfaces retrieval metrics, evidence coverage scores, and confidence signals
          at every inference step — not post-hoc.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {POINTS.map((p) => (
          <div key={p.title} className="card card-hover flex gap-3 p-5">
            <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-edge bg-panel2">
              <Glyph>{p.icon}</Glyph>
            </span>
            <div>
              <h3 className="text-base font-semibold text-fg">{p.title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-fg2">{p.body}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
