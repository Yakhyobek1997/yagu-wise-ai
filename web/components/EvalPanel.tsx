"use client";
import { useEffect, useState } from "react";
import { evalReport, evalLast, postEvalFeedback, exportEvalRun, runEval, type EvalMetrics } from "@/lib/api";

const FEEDBACK_KEY = "auralynq.feedback.v1";
type Vote = "helpful" | "not-helpful" | "citation-ok" | "citation-wrong" | "unsupported";

const FEEDBACK: { id: Vote; label: string; good?: boolean }[] = [
  { id: "helpful", label: "👍 Helpful", good: true },
  { id: "not-helpful", label: "👎 Not helpful" },
  { id: "citation-ok", label: "✓ Citation correct", good: true },
  { id: "citation-wrong", label: "✕ Citation wrong" },
  { id: "unsupported", label: "⚠ Answer unsupported" },
];

const PLANNED = [
  { name: "Groundedness", body: "Is every claim supported by retrieved evidence?" },
  { name: "Citation coverage", body: "Share of statements that carry a citation." },
  { name: "Retrieval quality", body: "recall@k · nDCG@10 · MRR across retrievers." },
  { name: "Answer latency", body: "p50 / p95 end-to-end response time." },
  { name: "Abstention correctness", body: "Does it refuse exactly when evidence is insufficient?" },
  { name: "Strategy comparison", body: "Side-by-side metrics across RAG strategies." },
];

function MetricRow({ label, value, cls }: { label: string; value: string; cls?: string }) {
  return (
    <div className="flex items-center justify-between py-0.5">
      <span className="text-xs text-fg3">{label}</span>
      <span className={`text-xs font-medium ${cls || "text-fg2"}`}>{value}</span>
    </div>
  );
}

export function EvalPanel() {
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [lastMetrics, setLastMetrics] = useState<EvalMetrics | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [flash, setFlash] = useState<string | null>(null);
  const [exportData, setExportData] = useState<any>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(FEEDBACK_KEY);
      if (raw) setCounts(JSON.parse(raw));
    } catch {
      /* ignore */
    }
    // Load last query metrics
    evalLast().then((m) => {
      if (m) setLastMetrics(m);
    }).catch(() => {});
  }, []);

  async function loadReport() {
    setLoading(true);
    try {
      setReport(await evalReport());
    } finally {
      setLoading(false);
    }
  }

  async function handleRunEval() {
    setRunning(true);
    setRunError(null);
    try {
      await runEval(); // returns immediately with status=running
      // Poll /eval/report every 5s until status != "running"
      let attempts = 0;
      const poll = async (): Promise<void> => {
        await new Promise((r) => setTimeout(r, 5000));
        attempts++;
        try {
          const r = await evalReport();
          if (r.status === "running" && attempts < 30) {
            return poll();
          }
          setReport(r);
        } catch {
          if (attempts < 30) return poll();
        }
      };
      await poll();
    } catch (e) {
      setRunError((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  async function handleExport() {
    try {
      const data = await exportEvalRun();
      setExportData(data);
    } catch {
      /* ignore */
    }
  }

  function vote(v: Vote) {
    const isGood = FEEDBACK.find((f) => f.id === v)?.good;
    // Post feedback to backend
    postEvalFeedback({
      answer_rating: isGood ? 5 : 2,
      citation_correct: v === "citation-ok" ? true : v === "citation-wrong" ? false : undefined,
      answer_supported: v === "helpful" ? true : v === "unsupported" ? false : undefined,
      notes: v,
    }).catch(() => {});

    setCounts((prev) => {
      const next = { ...prev, [v]: (prev[v] || 0) + 1 };
      try { localStorage.setItem(FEEDBACK_KEY, JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
    setFlash("Thanks — feedback recorded");
    setTimeout(() => setFlash(null), 1800);
  }

  const variants = report?.retrieval ? Object.entries(report.retrieval as Record<string, any>) : [];
  const hasReport = variants.length > 0;

  const riskCls = (r?: string) => {
    if (!r || r === "none" || r === "low") return "text-ok";
    if (r === "medium") return "text-warn";
    return "text-bad";
  };

  return (
    <div className="space-y-3">
      {/* last query metrics */}
      {lastMetrics && (
        <section className="card-inset">
          <h3 className="mb-2 text-sm font-semibold text-fg">Last query metrics</h3>
          <div className="divide-y divide-edge">
            {lastMetrics.strategy && <MetricRow label="Strategy" value={lastMetrics.strategy.replace(/_/g, " ")} cls="text-brand" />}
            {lastMetrics.route && <MetricRow label="Route" value={lastMetrics.route} />}
            {lastMetrics.confidence != null && (
              <MetricRow
                label="Confidence"
                value={lastMetrics.confidence.toFixed(3)}
                cls={lastMetrics.confidence >= 0.6 ? "text-ok" : "text-warn"}
              />
            )}
            {lastMetrics.evidence_coverage != null && (
              <MetricRow
                label="Evidence coverage"
                value={`${Math.round(lastMetrics.evidence_coverage * 100)}%`}
                cls={lastMetrics.evidence_coverage >= 0.6 ? "text-ok" : "text-warn"}
              />
            )}
            {lastMetrics.citations != null && <MetricRow label="Citations" value={String(lastMetrics.citations)} />}
            {lastMetrics.elapsed_ms != null && <MetricRow label="Latency" value={`${lastMetrics.elapsed_ms.toFixed(0)}ms`} />}
            {lastMetrics.status && (
              <MetricRow
                label="Status"
                value={lastMetrics.status}
                cls={lastMetrics.status === "answered" ? "text-ok" : "text-warn"}
              />
            )}
          </div>
          <button className="mt-2 btn-ghost w-full text-xs" onClick={handleExport}>
            Export run JSON
          </button>
          {exportData && (
            <pre className="mt-2 max-h-32 overflow-auto rounded border border-edge bg-panel2 p-2 text-[10px] text-fg3">
              {JSON.stringify(exportData.last_eval, null, 2)}
            </pre>
          )}
        </section>
      )}

      {/* manual feedback widget */}
      <section className="card-inset">
        <h3 className="mb-2 text-sm font-semibold text-fg">Rate the last answer</h3>
        <div className="flex flex-wrap gap-1.5">
          {FEEDBACK.map((f) => (
            <button
              key={f.id}
              onClick={() => vote(f.id)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                f.good
                  ? "border-ok/40 text-ok hover:bg-ok/10"
                  : "border-edge text-fg2 hover:border-warn/50 hover:text-warn"
              }`}
            >
              {f.label}
              {counts[f.id] ? <span className="ml-1 opacity-70">· {counts[f.id]}</span> : null}
            </button>
          ))}
        </div>
        {flash && <p className="mt-2 text-[11px] text-ok">{flash}</p>}
      </section>

      {/* report (if available) */}
      <section className="card-inset">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-fg">Evaluation report</h3>
          <div className="flex items-center gap-1.5">
            {hasReport && (
              <button className="btn-ghost px-2.5 py-1 text-xs" onClick={loadReport} disabled={loading}>
                {loading ? "Loading…" : "Reload"}
              </button>
            )}
            <button
              className="btn-ghost px-2.5 py-1 text-xs font-medium text-brand"
              onClick={handleRunEval}
              disabled={running}
              title="Run 3–5 queries against indexed corpus and compute live metrics"
            >
              {running ? "Running…" : "▶ Run evaluation"}
            </button>
          </div>
        </div>

        {running && (
          <div className="flex items-center gap-2 py-3 text-xs text-fg3">
            <span className="animate-spin">⟳</span>
            Running queries against corpus — this may take 30–60 s…
          </div>
        )}

        {runError && (
          <p className="text-xs text-bad">{runError}</p>
        )}

        {/* Inline eval report (from /eval/run) */}
        {report?.n_questions != null && (
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-1.5 text-xs">
              <div className="rounded-lg border border-edge bg-panel2 p-2 text-center">
                <div className="text-fg3">Questions run</div>
                <div className="text-base font-bold text-fg">{report.n_questions}</div>
              </div>
              <div className="rounded-lg border border-edge bg-panel2 p-2 text-center">
                <div className="text-fg3">Citation rate</div>
                <div className={`text-base font-bold ${report.citation_rate >= 0.6 ? "text-ok" : "text-warn"}`}>
                  {Math.round(report.citation_rate * 100)}%
                </div>
              </div>
              <div className="rounded-lg border border-edge bg-panel2 p-2 text-center">
                <div className="text-fg3">Avg confidence</div>
                <div className={`text-base font-bold ${report.avg_confidence >= 0.6 ? "text-ok" : "text-warn"}`}>
                  {report.avg_confidence?.toFixed(2)}
                </div>
              </div>
              <div className="rounded-lg border border-edge bg-panel2 p-2 text-center">
                <div className="text-fg3">Avg latency</div>
                <div className="text-base font-bold text-fg">{report.avg_latency_ms?.toFixed(0)}ms</div>
              </div>
            </div>
            {report.per_question?.length > 0 && (
              <div className="space-y-1">
                <p className="text-[11px] font-medium text-fg3">Per-question results</p>
                {report.per_question.map((r: any, i: number) => (
                  <div key={i} className="flex items-start gap-2 rounded border border-edge bg-panel2 px-2 py-1 text-[11px]">
                    <span className={`mt-0.5 shrink-0 font-mono ${r.status === "answered" ? "text-ok" : "text-warn"}`}>
                      {r.status === "answered" ? "✓" : "–"}
                    </span>
                    <span className="min-w-0 flex-1 text-fg3 truncate" title={r.question}>{r.question}</span>
                    {r.citations != null && <span className="shrink-0 text-fg3">{r.citations} cit</span>}
                    {r.confidence != null && <span className="shrink-0 text-fg3">{r.confidence.toFixed(2)}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Full retrieval report (from make eval) */}
        {hasReport && !report?.n_questions && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-fg3">
                <tr>
                  <th className="text-left font-medium">retriever</th>
                  <th className="font-medium">recall@k</th>
                  <th className="font-medium">nDCG@10</th>
                  <th className="font-medium">MRR</th>
                  <th className="font-medium">p50 ms</th>
                </tr>
              </thead>
              <tbody>
                {variants.map(([name, m]) => (
                  <tr key={name} className="border-t border-edge">
                    <td className="py-1 text-fg">{name}</td>
                    <td className="text-center text-fg2">{(m as any).recall_at_k}</td>
                    <td className="text-center text-fg2">{(m as any).ndcg_at_10}</td>
                    <td className="text-center text-fg2">{(m as any).mrr}</td>
                    <td className="text-center text-fg2">{(m as any).latency_p50_ms}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {report?.agentic?.ragas && (
              <p className="mt-2 text-xs text-fg3">
                Ragas ({report.agentic.ragas.provider}): faithfulness{" "}
                {report.agentic.ragas.faithfulness} · relevancy {report.agentic.ragas.answer_relevancy}{" "}
                · ctx-precision {report.agentic.ragas.context_precision}
              </p>
            )}
          </div>
        )}

        {!hasReport && !report?.n_questions && !running && (
          <p className="text-xs text-fg3">
            Click <strong>▶ Run evaluation</strong> to score the corpus live, or run{" "}
            <code className="text-brand">make eval</code> for a full retrieval benchmark.
          </p>
        )}
      </section>

      {/* planned evals */}
      <section className="card-inset">
        <h3 className="mb-2 text-sm font-semibold text-fg">Planned evaluations</h3>
        <ul className="space-y-1.5">
          {PLANNED.map((p) => (
            <li key={p.name} className="flex items-start gap-2 text-sm">
              <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" aria-hidden />
              <span>
                <span className="font-medium text-fg">{p.name}</span>{" "}
                <span className="text-fg3">— {p.body}</span>
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
