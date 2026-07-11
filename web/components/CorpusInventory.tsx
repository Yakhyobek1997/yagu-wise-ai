"use client";
import type { CorpusSummary } from "@/lib/api";
import { displaySource, timeAgo } from "@/lib/format";

const SOURCE_TYPE_ICON: Record<string, string> = {
  pdf: "📕",
  markdown: "📝",
  audio: "🎙️",
  text: "📄",
  docx: "📘",
  unknown: "📄",
};

function sourceIcon(type: string) {
  return SOURCE_TYPE_ICON[type.toLowerCase()] ?? "📄";
}

// Renders a corpus-inventory answer (what's *in* the collection) instead of an
// evidence failure — for questions like "Is there any Arabic document in my
// collection?". Built from corpus metadata, so it's honest and instant.
export function CorpusInventory({
  summary,
  question,
}: {
  summary: CorpusSummary;
  question?: string;
}) {
  const types = Object.entries(summary.source_types || {});
  const langs = summary.languages || [];
  const failed = summary.failed_files || [];
  const titles = summary.document_titles || [];
  const topics = summary.top_entities || [];
  const lastDoc = summary.last_document_title ?? null;

  // Detect what specific sub-question the user is asking.
  const q = (question || "").toLowerCase();
  const askedAboutLastDoc = /\b(last|latest|most recent|recently)\b.*\b(document|file|upload|added|ingest)\b/.test(q)
    || /\bwhat.*last\b/.test(q);
  const askedLang = detectAskedLanguage(question || "");
  const langMatch =
    askedLang && langs.length
      ? langs.some((l) => l.toLowerCase().includes(askedLang.toLowerCase()))
      : null;

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center gap-2.5">
        <span
          aria-hidden
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-brand/20 bg-brand/10 text-lg"
        >
          🗂️
        </span>
        <div>
          <p className="font-semibold text-fg">Corpus inventory</p>
          <p className="text-xs text-fg3">
            {summary.indexed
              ? `${summary.indexed_document_count} document${
                  summary.indexed_document_count === 1 ? "" : "s"
                } · ${summary.vector_count.toLocaleString()} vectors · indexed ${timeAgo(summary.last_indexed)}`
              : "Nothing is indexed yet — upload documents to build your collection."}
          </p>
        </div>
      </div>

      {/* Direct answer for "last document added" queries */}
      {askedAboutLastDoc && (
        <div className="rounded-xl border border-brand/30 bg-brand/[0.07] p-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-brand mb-1">Last document added</p>
          {lastDoc ? (
            <p className="flex items-center gap-2 text-sm font-medium text-fg">
              <span aria-hidden>{sourceIcon(lastDoc.split(".").pop() ?? "")}</span>
              {displaySource(lastDoc)}
            </p>
          ) : (
            <p className="text-sm text-fg2">No upload history found — documents may have been indexed from disk.</p>
          )}
          {summary.last_indexed && (
            <p className="mt-1 text-xs text-fg3">Indexed {timeAgo(summary.last_indexed)}</p>
          )}
        </div>
      )}

      {/* Direct answer for language queries */}
      {askedLang && langMatch !== null && (
        <div className={`rounded-xl border p-3 text-sm ${langMatch ? "evidence-strong" : "evidence-weak"}`}>
          {langMatch ? (
            <span className="text-fg">
              ✓ Your collection includes <strong>{askedLang}</strong> content.
            </span>
          ) : (
            <span className="text-fg">
              No <strong>{askedLang}</strong> documents detected. Languages found:{" "}
              {langs.length ? langs.join(", ") : "unknown"}.
            </span>
          )}
        </div>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-2">
        <Field label="Documents">
          <span className="text-xl font-bold text-fg">{summary.indexed_document_count}</span>
        </Field>
        <Field label="Languages">
          {langs.length ? (
            <div className="flex flex-wrap gap-1">
              {langs.map((l) => (
                <span key={l} className="tag">
                  {l}
                </span>
              ))}
            </div>
          ) : (
            <span className="text-xs text-fg3">not detected</span>
          )}
        </Field>
        <Field label="File types">
          {types.length ? (
            <div className="flex flex-wrap gap-1">
              {types.map(([t, n]) => (
                <span key={t} className="tag">
                  {sourceIcon(t)} {t} · {n}
                </span>
              ))}
            </div>
          ) : (
            <span className="text-xs text-fg3">none</span>
          )}
        </Field>
        <Field label="Last indexed">
          <span className="text-sm font-medium text-fg2">{timeAgo(summary.last_indexed)}</span>
        </Field>
      </div>

      {/* Document list */}
      {titles.length > 0 && (
        <Field label={`Indexed files (${titles.length})`}>
          <ul className="space-y-1 text-xs">
            {titles.slice(0, 8).map((d, i) => (
              <li
                key={d}
                className={`flex items-center gap-1.5 truncate rounded-lg px-2 py-1 ${
                  i === 0 && lastDoc && displaySource(lastDoc) === displaySource(d)
                    ? "bg-brand/10 text-fg ring-1 ring-brand/20"
                    : "text-fg2"
                }`}
                title={displaySource(d)}
              >
                <span aria-hidden className="shrink-0">
                  {sourceIcon((d.split(".").pop() ?? ""))}
                </span>
                <span className="truncate">{displaySource(d)}</span>
              </li>
            ))}
            {titles.length > 8 && (
              <li className="px-2 text-fg3">+{titles.length - 8} more</li>
            )}
          </ul>
        </Field>
      )}

      {/* Top topics */}
      {topics.length > 0 && (
        <Field label="Top topics">
          <div className="flex flex-wrap gap-1">
            {topics.slice(0, 10).map((e) => (
              <span key={e.name} className="tag border-brand2/30 text-brand2">
                {e.name}
              </span>
            ))}
          </div>
        </Field>
      )}

      {/* Failed ingests */}
      {failed.length > 0 && (
        <Field label={`Failed to ingest (${failed.length})`}>
          <ul className="space-y-0.5 text-xs text-bad">
            {failed.slice(0, 5).map((f) => (
              <li key={f} className="flex items-center gap-1 truncate" title={f}>
                <span aria-hidden>⚠</span>
                {displaySource(f)}
              </li>
            ))}
          </ul>
        </Field>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="card-inset">
      <p className="stat-label mb-1">{label}</p>
      {children}
    </div>
  );
}

const LANGUAGES = [
  "arabic",
  "english",
  "french",
  "spanish",
  "german",
  "chinese",
  "japanese",
  "korean",
  "russian",
  "hindi",
  "portuguese",
  "italian",
  "dutch",
  "turkish",
  "persian",
  "urdu",
  "hebrew",
];

function detectAskedLanguage(q: string): string | null {
  const s = q.toLowerCase();
  for (const l of LANGUAGES) {
    if (s.includes(l)) return l.charAt(0).toUpperCase() + l.slice(1);
  }
  return null;
}
