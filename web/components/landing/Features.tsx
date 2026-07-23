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
    title: "A wiki that keeps learning",
    body: "YaguWise AI turns your documents into a cited wiki and keeps it updated. Conflicting sources are flagged, not hidden.",
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
    title: "Visual source proof",
    body: "Open any citation to see the exact answer area on the original PDF page.",
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
    title: "Models matched to your hardware",
    body: "Checks your RAM, VRAM, and backend, then recommends models your machine can run. Downloads require approval.",
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
    title: "Voice document chat",
    body: "Ask by voice and hear cited answers. Offline fallbacks work without the cloud.",
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
    title: "Cited, grounded answers",
    body: "Every answer links to its source. If evidence is weak, YaguWise AI says so instead of guessing.",
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
    title: "PathRAG reasoning",
    body: "Uses a knowledge graph to answer connected, multi-step questions.",
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
    title: "Better search and ranking",
    body: "Combines semantic and keyword search, then ranks the most useful context.",
    tint: "text-brand",
    ring: "ring-brand/15",
    icon: (tint: string) => (
      <Icon tint={tint}>
        <path d="M3 6h18M6 12h12M9 18h6" />
      </Icon>
    ),
  },
  {
    title: "Visible AI workflow",
    body: "See the selected route, evidence, response time, and reasoning trace.",
    tint: "text-accent2",
    ring: "ring-accent2/15",
    icon: (tint: string) => (
      <Icon tint={tint}>
        <path d="M3 12h4l3 8 4-16 3 8h4" />
      </Icon>
    ),
  },
  {
    title: "Local and flexible",
    body: "Runs on your machine by default. Connect other AI providers only when you choose.",
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
        <h2 className="section-title">Everything you need for private, grounded AI</h2>
        <p className="mt-3 text-lg text-fg2">
          Search, reason, cite, and monitor - all on your machine.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((feature) => (
          <div key={feature.title} className={`card card-hover group ring-1 ${feature.ring} p-6`}>
            <div className="mb-4 inline-flex rounded-xl border border-edge bg-panel2 p-2.5">
              {feature.icon(feature.tint)}
            </div>
            <h3 className="mb-2 text-lg font-semibold text-fg">{feature.title}</h3>
            <p className="text-sm leading-relaxed text-fg2">{feature.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
