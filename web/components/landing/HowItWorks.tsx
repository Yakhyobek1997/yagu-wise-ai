import type { ReactNode } from "react";
import { ArrowRight } from "lucide-react";

type Phase = "ingest" | "answer" | "observe";

const PHASE_TINT: Record<Phase, string> = {
  ingest: "text-brand",
  answer: "text-brand2",
  observe: "text-accent",
};

const STEPS: { label: string; phase: Phase; icon: ReactNode }[] = [
  { label: "Upload", phase: "ingest", icon: <path d="M12 16V4m0 0L8 8m4-4 4 4M4 20h16" /> },
  { label: "Parse", phase: "ingest", icon: <path d="M5 4h11l3 3v13H5zM9 9h6M9 13h6M9 17h3" /> },
  { label: "Chunk", phase: "ingest", icon: <path d="M4 5h7v7H4zM13 5h7v4h-7zM13 13h7v6h-7zM4 14h7v5H4z" /> },
  { label: "Index", phase: "ingest", icon: <path d="M12 3v18M5 7l7-4 7 4M5 17l7 4 7-4M5 7v10M19 7v10" /> },
  { label: "Retrieve", phase: "answer", icon: <path d="M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14ZM21 21l-5-5" /> },
  { label: "Rerank", phase: "answer", icon: <path d="M7 4v16M7 4 4 7m3-3 3 3M17 20V4m0 16 3-3m-3 3-3-3" /> },
  { label: "Reason", phase: "answer", icon: <path d="M12 3a6 6 0 0 0-4 10.5V16a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2v-2.5A6 6 0 0 0 12 3ZM10 21h4" /> },
  { label: "Cite", phase: "answer", icon: <path d="M7 7h6M7 11h6M5 4h9l4 4v12H5zM14 4v4h4" /> },
  { label: "Observe", phase: "observe", icon: <path d="M3 12h4l3 8 4-16 3 8h4" /> },
];

function StepGlyph({ children, tint }: { children: ReactNode; tint: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`h-5 w-5 ${tint}`}
      aria-hidden
    >
      {children}
    </svg>
  );
}

export function HowItWorks() {
  return (
    <section id="how" className="relative mx-auto max-w-7xl px-4 py-14 md:px-6">
      <div className="mb-12 max-w-2xl">
        <p className="overline mb-2 text-brand2">How it works</p>
        <h2 className="section-title">Turn your documents into trusted answers</h2>
        <p className="mt-3 text-lg text-fg2">
          A clear, traceable process from upload to citation.
        </p>
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        <span className="chip"><span className="h-2 w-2 rounded-full bg-brand" /> Ingest</span>
        <span className="chip"><span className="h-2 w-2 rounded-full bg-brand2" /> Answer</span>
        <span className="chip"><span className="h-2 w-2 rounded-full bg-accent" /> Observe</span>
      </div>

      <ol className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-9">
        {STEPS.map((step, index) => (
          <li key={step.label} className="relative">
            <div className="card card-hover flex h-full flex-col items-center gap-2 p-4 text-center">
              <span className="text-[10px] font-semibold text-fg3">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="inline-flex rounded-lg border border-edge bg-panel2 p-2">
                <StepGlyph tint={PHASE_TINT[step.phase]}>{step.icon}</StepGlyph>
              </span>
              <span className="text-sm font-semibold text-fg">{step.label}</span>
            </div>
            {index < STEPS.length - 1 && (
              <ArrowRight
                className="absolute -right-2.5 top-1/2 z-10 hidden h-5 w-5 -translate-y-1/2 text-fg3 lg:block"
                aria-hidden
              />
            )}
          </li>
        ))}
      </ol>

      <p className="mt-6 text-sm text-fg3">
        Ask by text or voice. YaguWise AI finds the evidence, checks it, and returns a cited answer.
      </p>
    </section>
  );
}
