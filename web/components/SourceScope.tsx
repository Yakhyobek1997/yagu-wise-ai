"use client";
import { useEffect, useState } from "react";
import { Check, FileText, Layers } from "lucide-react";
import { corpusDocuments, type CorpusDocument } from "@/lib/api";
import { displaySource } from "@/lib/format";

/**
 * NotebookLM-style source scoping: check/uncheck indexed documents to restrict
 * the next query's retrieval set. Reports the selected doc_ids to the parent
 * (null when everything is selected → search the whole corpus).
 */
export function SourceScope({
  refreshKey,
  onChange,
}: {
  refreshKey?: number;
  onChange: (docIds: string[] | null) => void;
}) {
  const [docs, setDocs] = useState<CorpusDocument[]>([]);
  const [included, setIncluded] = useState<Set<string>>(new Set());

  useEffect(() => {
    let alive = true;
    corpusDocuments()
      .then((d) => {
        if (!alive) return;
        setDocs(d);
        setIncluded(new Set(d.map((x) => x.doc_id))); // default: all in scope
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [refreshKey]);

  // Report scope up: all-selected → null (whole corpus), else the id list.
  const emit = (next: Set<string>) => {
    onChange(next.size === docs.length ? null : Array.from(next));
  };

  const toggle = (id: string) => {
    setIncluded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      emit(next);
      return next;
    });
  };
  const setAll = (all: boolean) => {
    const next = all ? new Set(docs.map((d) => d.doc_id)) : new Set<string>();
    setIncluded(next);
    emit(next);
  };

  if (docs.length === 0) return null;
  const n = included.size;
  const scoped = n !== docs.length;

  return (
    <div className="card-inset">
      <div className="mb-2 flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-fg2">
          <Layers className="h-3.5 w-3.5 text-fg3" aria-hidden />
          Scope retrieval
          <span className={`font-mono ${scoped ? "text-brand" : "text-fg3"}`}>
            {n}/{docs.length}
          </span>
        </span>
        <span className="flex gap-1.5 text-[11px]">
          <button type="button" onClick={() => setAll(true)} className="text-fg3 transition hover:text-fg">
            All
          </button>
          <span className="text-fg3">·</span>
          <button type="button" onClick={() => setAll(false)} className="text-fg3 transition hover:text-fg">
            None
          </button>
        </span>
      </div>
      <ul className="max-h-40 space-y-0.5 overflow-y-auto scroll-thin">
        {docs.map((d) => {
          const on = included.has(d.doc_id);
          return (
            <li key={d.doc_id}>
              <button
                type="button"
                role="checkbox"
                aria-checked={on}
                onClick={() => toggle(d.doc_id)}
                className="flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left text-xs transition hover:bg-panel2"
              >
                <span
                  className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                    on ? "border-brand bg-brand/20 text-brand" : "border-edge text-transparent"
                  }`}
                >
                  <Check className="h-3 w-3" aria-hidden />
                </span>
                <FileText className="h-3.5 w-3.5 shrink-0 text-fg3" aria-hidden />
                <span className={`flex-1 truncate ${on ? "text-fg2" : "text-fg3"}`} title={displaySource(d.title || d.source)}>
                  {displaySource(d.title || d.source)}
                </span>
                <span className="shrink-0 font-mono text-[10px] text-fg3">{d.chunks}</span>
              </button>
            </li>
          );
        })}
      </ul>
      {scoped && (
        <p className="mt-1.5 text-[10px] text-fg3">
          Next queries search {n} of {docs.length} documents.
        </p>
      )}
    </div>
  );
}
