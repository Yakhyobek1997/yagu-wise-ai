"use client";
import { useEffect, useState } from "react";
import { CorpusSummary, corpusSummary, statusSummary } from "@/lib/api";
import { displaySource, timeAgo } from "@/lib/format";

// The inspector must never feel empty. Before any query is run we surface a
// useful overview: corpus snapshot, system status, last-answer summary,
// suggested questions, and an upload CTA.
export interface RecentMeta {
  route: string;
  status: string;
  coverage: number;
  confidence: number;
}

export function InspectorOverview({
  suggestions,
  recent,
  onAsk,
  onIngest,
  refreshKey = 0,
}: {
  suggestions: string[];
  recent: RecentMeta | null;
  onAsk: (q: string) => void;
  onIngest: () => void;
  refreshKey?: number;
}) {
  const [summary, setSummary] = useState<CorpusSummary | null>(null);
  const [providers, setProviders] = useState<{ subsystem: string; provider: string }[]>([]);
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    corpusSummary()
      .then(setSummary)
      .catch(() => setSummary(null));
    statusSummary()
      .then((s) => {
        setProviders(s.providers || []);
        setOnline(true);
      })
      .catch(() => setOnline(false));
  }, [refreshKey]);

  const types = summary ? Object.entries(summary.source_types || {}) : [];
  const topics = summary?.top_entities?.slice(0, 6) || [];

  return (
    <div className="space-y-3">
      {/* corpus snapshot */}
      <section className="card-inset">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-fg">Your corpus</h3>
          {summary && (
            <span className="text-[11px] text-fg3">indexed {timeAgo(summary.last_indexed)}</span>
          )}
        </div>
        {summary?.indexed ? (
          <>
            <div className="grid grid-cols-3 gap-1.5">
              <Stat value={summary.indexed_document_count} label="docs" />
              <Stat value={summary.vector_count} label="vectors" />
              <Stat value={summary.entity_count} label="entities" />
            </div>
            {types.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {types.map(([t, n]) => (
                  <span key={t} className="tag">
                    {t} · {n}
                  </span>
                ))}
              </div>
            )}
            {summary.document_titles?.length > 0 && (
              <ul className="mt-2 space-y-0.5 text-xs text-fg2">
                {summary.document_titles.slice(0, 4).map((d) => (
                  <li key={d} className="truncate" title={displaySource(d)}>
                    📄 {displaySource(d)}
                  </li>
                ))}
                {summary.document_titles.length > 4 && (
                  <li className="text-fg3">+{summary.document_titles.length - 4} more</li>
                )}
              </ul>
            )}
          </>
        ) : (
          <p className="text-sm text-fg3">
            No documents indexed yet. Upload PDFs, docs or audio to start asking grounded questions.
          </p>
        )}
        <button onClick={onIngest} className="btn-ghost mt-3 w-full text-sm">
          <span aria-hidden>＋</span> Add documents
        </button>
      </section>

      {/* first-run checklist — only before any document is indexed */}
      {summary && !summary.indexed && <FirstRunChecklist onIngest={onIngest} />}

      {/* system status */}
      <section className="card-inset">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-fg">System status</h3>
          <span className={`pill ${online === null ? "pill-neutral" : online ? "pill-ok" : "pill-bad"}`}>
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${
                online === null ? "bg-fg3" : online ? "bg-ok" : "bg-bad"
              }`}
            />
            {online === null ? "…" : online ? "Online" : "Offline"}
          </span>
        </div>
        {providers.length ? (
          <div className="flex flex-wrap gap-1">
            {providers.map((p) => (
              <span key={p.subsystem} className="tag" title={`${p.subsystem}: ${p.provider}`}>
                {p.subsystem}: <span className="text-brand">{p.provider}</span>
              </span>
            ))}
          </div>
        ) : (
          <p className="text-xs text-fg3">Provider status unavailable.</p>
        )}
      </section>

      {/* recent answer summary */}
      {recent && (
        <section className="card-inset">
          <h3 className="mb-2 text-sm font-semibold text-fg">Last answer</h3>
          <div className="grid grid-cols-3 gap-1.5">
            <Stat value={`${Math.round(recent.coverage * 100)}%`} label="coverage" />
            <Stat value={recent.confidence.toFixed(2)} label="confidence" />
            <Stat value={recent.route} label="route" />
          </div>
          <p className="mt-2 text-[11px] text-fg3">
            {recent.status === "insufficient_evidence"
              ? "Auralynq abstained — not enough evidence."
              : "Open the Trace and Evidence tabs above for the full breakdown."}
          </p>
        </section>
      )}

      {/* suggested questions */}
      <section className="card-inset">
        <h3 className="mb-2 text-sm font-semibold text-fg">Try asking</h3>
        <div className="flex flex-col gap-1.5">
          {(suggestions.length ? suggestions : ["Summarize the main topics in the indexed documents."]).map(
            (q) => (
              <button
                key={q}
                onClick={() => onAsk(q)}
                className="rounded-lg border border-edge bg-panel px-3 py-2 text-left text-sm text-fg2 transition hover:border-brand/50 hover:text-fg"
              >
                {q}
              </button>
            ),
          )}
        </div>
      </section>

      {topics.length > 0 && (
        <section className="card-inset">
          <h3 className="mb-2 text-sm font-semibold text-fg">Top topics</h3>
          <div className="flex flex-wrap gap-1">
            {topics.map((e) => (
              <span key={e.name} className="tag border-brand2/30 text-brand2">
                {e.name}
              </span>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function Stat({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="stat text-center">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

// First-run onboarding: the six things worth trying, in order. Guidance only —
// we don't track completion (that would need cross-app event plumbing); the
// point is to orient a brand-new visitor, so it's shown only until the first
// document is indexed.
const FIRST_RUN_STEPS: { label: string; hint: string }[] = [
  { label: "Upload a document", hint: "Ingest panel — a PDF, DOCX, TXT/MD, or audio file" },
  { label: "Ask a question", hint: "Type or speak a question about what you uploaded" },
  { label: "Click a citation", hint: "Every answer cites its sources — click one to verify" },
  { label: "Open the Source Workspace", hint: "See the exact page + highlighted span behind a claim" },
  { label: "Try ModelFit", hint: "The ModelFit page ranks local models for your hardware" },
  { label: "Run a benchmark", hint: "make eval / make bench — reproducible, written to reports/" },
];

function FirstRunChecklist({ onIngest }: { onIngest: () => void }) {
  return (
    <section className="card-inset" aria-label="First-run checklist">
      <h3 className="mb-2 text-sm font-semibold text-fg">First run — try these</h3>
      <ol className="space-y-1.5">
        {FIRST_RUN_STEPS.map((step, i) => (
          <li key={step.label} className="flex items-start gap-2 text-xs">
            <span
              aria-hidden
              className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-edge text-[10px] text-fg3"
            >
              {i + 1}
            </span>
            <span className="min-w-0">
              {i === 0 ? (
                <button
                  onClick={onIngest}
                  className="font-medium text-brand underline decoration-dotted hover:text-brand2"
                >
                  {step.label}
                </button>
              ) : (
                <span className="font-medium text-fg">{step.label}</span>
              )}
              <span className="block text-fg3">{step.hint}</span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
