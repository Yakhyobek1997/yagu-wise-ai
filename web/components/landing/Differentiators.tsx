import type { ReactNode } from "react";

const POINTS: { title: string; body: string; icon: ReactNode }[] = [
  {
    title: "Knowledge that grows",
    body: "Builds a cited wiki from your documents and flags conflicting information.",
    icon: <path d="M4 5a2 2 0 0 1 2-2h9l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z M8 12h6M8 16h4M14 3v5h5" />,
  },
  {
    title: "Proof on the page",
    body: "Each citation opens the exact answer area in the original PDF.",
    icon: <path d="M4 5a2 2 0 0 1 2-2h9l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z M9 12h6M9 16h4M14 3v5h5" />,
  },
  {
    title: "Smart model matching",
    body: "Recommends models that fit your RAM, VRAM, and local setup.",
    icon: <path d="M9 3v2M15 3v2M9 19v2M15 19v2M3 9h2M3 15h2M19 9h2M19 15h2M6 6h12v12H6zM10 10h4v4h-4z" />,
  },
  {
    title: "Private by default",
    body: "Runs locally with no account or required telemetry. Your files stay on your machine.",
    icon: <path d="M4 10V7a8 8 0 0 1 16 0v3M5 10h14a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2Z" />,
  },
  {
    title: "Smarter graph search",
    body: "Combines PathRAG with PageRank to find stronger multi-step connections.",
    icon: <path d="M5 6a2 2 0 1 0 0-.01M19 6a2 2 0 1 0 0-.01M12 18a2 2 0 1 0 0-.01M7 6h10M6 8l5 8M18 8l-5 8" />,
  },
  {
    title: "Knows when to stop",
    body: "If evidence is weak, it explains the gap instead of inventing an answer.",
    icon: <path d="M12 3 2 21h20L12 3ZM12 9v5M12 17h.01" />,
  },
  {
    title: "Everything is visible",
    body: "Shows confidence, citations, retrieval steps, and risks for every answer.",
    icon: <path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 1-2-2V9m0 0h18" />,
  },
  {
    title: "Voice and text together",
    body: "Spoken and typed questions use the same grounding and citation pipeline.",
    icon: <path d="M9 3h6v8a3 3 0 0 1-6 0Z M5 11a7 7 0 0 0 14 0M12 18v3" />,
  },
  {
    title: "Open and flexible",
    body: "Open-source and provider-agnostic, with no lock-in.",
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
        <p className="overline mb-2 text-accent">Why YaguWiseAi</p>
        <h2 className="section-title">Why choose YaguWiseAi?</h2>
        <p className="mt-3 text-lg text-fg2">
          Private, transparent AI with source-backed answers.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {POINTS.map((point) => (
          <div key={point.title} className="card card-hover flex gap-3 p-5">
            <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-edge bg-panel2">
              <Glyph>{point.icon}</Glyph>
            </span>
            <div>
              <h3 className="text-base font-semibold text-fg">{point.title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-fg2">{point.body}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
