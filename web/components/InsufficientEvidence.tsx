"use client";
import type { InsufficientReason } from "@/lib/api";
import { displaySource } from "@/lib/format";

/** Trustworthy abstention card — explains *why* Auralynq held back and what to
 * do next. Soft, informative styling (not an alarming error). */
export function InsufficientEvidence({
  reason,
  onAsk,
  onIngest,
}: {
  reason: InsufficientReason;
  onAsk?: (q: string) => void;
  onIngest?: () => void;
}) {
  return (
    <div className="mt-2 space-y-4 rounded-2xl border border-warn/30 bg-warn/[0.05] p-4">
      <div className="flex items-start gap-3">
        <span
          aria-hidden
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-warn/30 bg-warn/10 text-lg"
        >
          ⚖️
        </span>
        <div>
          <p className="text-base font-semibold text-fg">
            Not enough evidence in your indexed documents
          </p>
          <p className="mt-1 text-sm leading-relaxed text-fg2">
            Auralynq found related snippets, but they don&apos;t support a reliable answer — so it
            held back instead of guessing.
          </p>
        </div>
      </div>

      <div className="grid gap-2 text-xs sm:grid-cols-2">
        <div className="card-inset">
          <p className="stat-label mb-1">Detected entities</p>
          <div className="flex flex-wrap gap-1">
            {reason.detected_entities.length ? (
              reason.detected_entities.map((e) => (
                <span key={e} className="tag border-brand2/30 text-brand2">
                  {e}
                </span>
              ))
            ) : (
              <span className="text-fg3">none matched the corpus</span>
            )}
          </div>
        </div>
        <div className="card-inset">
          <p className="stat-label mb-1">Route attempted</p>
          <p className="font-mono text-sm text-fg">{reason.route_attempted}</p>
        </div>
      </div>

      {reason.retrieved_snippets.length > 0 ? (
        <details className="card-inset text-sm">
          <summary className="cursor-pointer font-medium text-fg2">
            Top retrieved snippets ({reason.retrieved_snippets.length}) — why they fell short
          </summary>
          <p className="mt-2 text-xs text-fg3">{reason.why_insufficient}</p>
          <ul className="mt-2 space-y-2">
            {reason.retrieved_snippets.map((s, i) => (
              <li key={i} className="rounded-lg border border-edge bg-panel p-2">
                <div className="flex items-center justify-between text-xs text-fg3">
                  <span className="truncate" title={displaySource(s.source)}>
                    {displaySource(s.source) || "source"}
                  </span>
                  <span>score {s.score.toFixed(3)}</span>
                </div>
                <p className="mt-1 text-xs text-fg2">{s.text}…</p>
              </li>
            ))}
          </ul>
        </details>
      ) : (
        <p className="text-xs text-fg3">{reason.why_insufficient}</p>
      )}

      {reason.suggested_questions.length > 0 && (
        <div>
          <p className="stat-label mb-1.5">Try a question the corpus can support</p>
          <div className="flex flex-col gap-1.5">
            {reason.suggested_questions.map((q) => (
              <button
                key={q}
                onClick={() => onAsk?.(q)}
                className="rounded-lg border border-edge bg-panel px-3 py-2 text-left text-sm text-fg2 transition hover:border-brand/50 hover:text-fg"
              >
                <span className="mr-1.5 text-brand" aria-hidden>
                  ↳
                </span>
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {reason.suggest_ingest && (
        <button onClick={onIngest} className="btn-brand w-full text-sm">
          <span aria-hidden>＋</span> Ingest relevant documents
        </button>
      )}
    </div>
  );
}
