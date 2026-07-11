import Link from "next/link";
import { ChatPreview } from "@/components/landing/ChatPreview";

const REPO = "https://github.com/MHHamdan/Auralynq";

// Trust / value badges — the product promise at a glance.
const BADGES = [
  "Local-first",
  "$0 default",
  "Open source",
  "Compounding knowledge wiki",
  "Span-level visual grounding",
  "Hardware-aware ModelFit",
  "Citations on every answer",
  "Voice in / out",
  "Provider-agnostic",
];

export function Hero() {
  return (
    <section className="relative overflow-hidden">
      {/* ambient gradient orbs + grid */}
      <div className="absolute inset-0 grid-bg" aria-hidden />
      <div className="orb left-[-6rem] top-[-4rem] h-72 w-72 bg-brand/25 animate-orb-drift" aria-hidden />
      <div
        className="orb right-[-5rem] top-10 h-80 w-80 bg-brand2/30 animate-orb-drift"
        style={{ animationDelay: "3s" }}
        aria-hidden
      />
      <div
        className="orb bottom-[-6rem] left-1/3 h-72 w-72 bg-accent/25 animate-orb-drift"
        style={{ animationDelay: "6s" }}
        aria-hidden
      />

      <div className="relative mx-auto grid max-w-7xl items-center gap-10 px-4 py-16 md:px-6 md:py-24 lg:grid-cols-[1.05fr_0.95fr]">
        {/* copy */}
        <div className="reveal">
          <span className="chip mb-5 border-brand/30">
            <span className="h-1.5 w-1.5 rounded-full bg-brand animate-pulse-soft" />
            Local-first · $0 by default · Open source
          </span>
          <h1 className="text-display font-bold">
            Talk to <span className="gradient-text">your data.</span>
          </h1>
          <p className="mt-5 max-w-xl text-base font-medium leading-relaxed text-fg2 sm:text-lg">
            Voice-native RAG for private documents, grounded answers, PathRAG evidence, and
            observable AI pipelines.
          </p>
          <p className="mt-3 max-w-xl leading-relaxed text-fg3">
            Ask by text or voice and get cited, evidence-grounded answers — with the full retrieval
            trace visible — running entirely on your own machine, at zero cost by default.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link href="/chat" className="btn-cta">
              Launch app →
            </Link>
            <a href={REPO} target="_blank" rel="noopener noreferrer" className="btn-outline">
              <GitHubMark /> View on GitHub
            </a>
          </div>

          {/* trust / value badges */}
          <ul className="mt-8 flex flex-wrap gap-2">
            {BADGES.map((b) => (
              <li key={b} className="chip text-fg2">
                <span className="text-brand" aria-hidden>
                  ✓
                </span>
                {b}
              </li>
            ))}
          </ul>
        </div>

        {/* product preview */}
        <div className="reveal flex justify-center lg:justify-end" style={{ animationDelay: "0.15s" }}>
          <div className="animate-float w-full max-w-lg">
            <ChatPreview />
          </div>
        </div>
      </div>
    </section>
  );
}

function GitHubMark() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4" aria-hidden>
      <path d="M12 2C6.48 2 2 6.58 2 12.25c0 4.53 2.87 8.37 6.84 9.73.5.1.68-.22.68-.49 0-.24-.01-.87-.01-1.71-2.78.62-3.37-1.37-3.37-1.37-.45-1.18-1.11-1.49-1.11-1.49-.91-.64.07-.62.07-.62 1 .07 1.53 1.06 1.53 1.06.89 1.56 2.34 1.11 2.91.85.09-.66.35-1.11.63-1.36-2.22-.26-4.56-1.14-4.56-5.07 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.3.1-2.71 0 0 .84-.27 2.75 1.05a9.36 9.36 0 0 1 5 0c1.91-1.32 2.75-1.05 2.75-1.05.55 1.41.2 2.45.1 2.71.64.72 1.03 1.63 1.03 2.75 0 3.94-2.34 4.81-4.57 5.06.36.32.68.94.68 1.9 0 1.37-.01 2.47-.01 2.81 0 .27.18.6.69.49A10.04 10.04 0 0 0 22 12.25C22 6.58 17.52 2 12 2Z" />
    </svg>
  );
}
