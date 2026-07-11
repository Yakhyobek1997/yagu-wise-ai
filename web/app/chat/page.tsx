"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  AnswerResult,
  CorpusSummary,
  DeploymentMode,
  Citation,
  PathEvidence,
  StreamEvent,
  TraceSpan,
  TraceStep,
  VisualGrounding,
  askStreamWithStrategy,
  corpusSummary,
  deploymentMode,
  fetchSuggestions,
  health,
  statusSummary,
  corpusClearPreview,
  corpusClearConfirm,
} from "@/lib/api";
import { isInventoryQuestion } from "@/lib/format";
import { Message, type Turn } from "@/components/Message";
import { Toast } from "@/components/ui/Toast";
import { AnswerSteps } from "@/components/AnswerSteps";
import { StreamingEvidence } from "@/components/StreamingEvidence";
import { SourceScope } from "@/components/SourceScope";
import { WikiPanel } from "@/components/WikiPanel";
import { WatchPanel } from "@/components/WatchPanel";
import { CommandPalette, type Cmd } from "@/components/CommandPalette";
import { useRouter } from "next/navigation";
import { Plus, Cpu, Home, PanelRight, MessageSquarePlus, Zap, Palette } from "lucide-react";
import { THEME_KEY, nextTheme, coerceTheme } from "@/lib/theme";
import { TracePanel } from "@/components/TracePanel";
import { EvidencePaths } from "@/components/EvidencePaths";
import { IngestPanel } from "@/components/IngestPanel";
import { EvalPanel } from "@/components/EvalPanel";
import { SourceViewPanel } from "@/components/SourceViewPanel";
import { SourceWorkspaceModal } from "@/components/SourceWorkspaceModal";
import { AppBar } from "@/components/chat/AppBar";
import { PanelResizer } from "@/components/chat/PanelResizer";
import { Composer, type ChatMode } from "@/components/chat/Composer";
import { InspectorOverview, type RecentMeta } from "@/components/chat/InspectorOverview";
import { AgentActivityRail, type AgentActivity } from "@/components/chat/AgentActivityRail";
import { SettingsPanel, useUISettings } from "@/components/chat/SettingsPanel";
import { loadStoredStrategy } from "@/components/chat/AlgorithmSelector";
import { DemoBanner } from "@/components/DemoBanner";

const FALLBACK_SUGGESTIONS = [
  "Summarize the main topics in the indexed documents.",
  "What are the key entities and how do they relate?",
];
const STORE_KEY = "auralynq.chat.v1";
const TABS = ["overview", "trace", "evidence", "source", "ingest", "wiki", "eval"] as const;
type Tab = (typeof TABS)[number];

const TAB_ICON: Record<Tab, string> = {
  overview: "◎ ",
  trace:    "⬡ ",
  evidence: "◈ ",
  source:   "⬚ ",
  ingest:   "↑ ",
  wiki:     "▤ ",
  eval:     "▣ ",
};

function InlineSourceStrip({
  grounding,
  onOpen,
  onOpenWorkspace,
}: {
  grounding: import("@/lib/api").VisualGrounding;
  onOpen: () => void;
  onOpenWorkspace: () => void;
}) {
  const h = grounding.highlights[0];
  if (!h) return null;
  const stageCls =
    grounding.grounding_stage === "span"
      ? "text-ok"
      : grounding.grounding_stage === "page"
      ? "text-warn"
      : "text-fg3";
  return (
    <div className="mt-2 flex items-center gap-2 rounded-lg border border-edge bg-panel2 px-3 py-2 text-xs">
      <span className={`shrink-0 font-medium ${stageCls}`}>
        {grounding.grounding_stage === "span" ? "◉" : grounding.grounding_stage === "page" ? "◎" : "○"}
      </span>
      <span className="min-w-0 flex-1 truncate text-fg3">
        <span className="font-medium text-fg">{h.source_title.split("/").pop() || h.source_title}</span>
        {h.page != null && <span className="ml-1">· p.{h.page}</span>}
        <span className="ml-1 capitalize">{grounding.grounding_stage} match</span>
        {grounding.highlights.length > 1 && (
          <span className="ml-1 text-fg3">+{grounding.highlights.length - 1} more</span>
        )}
      </span>
      <button
        onClick={onOpen}
        className="shrink-0 rounded border border-edge px-2 py-0.5 text-fg3 hover:text-fg transition"
        title="Preview in inspector panel"
      >
        Preview
      </button>
      <button
        onClick={onOpenWorkspace}
        className="shrink-0 rounded border border-brand/40 bg-brand/5 px-2 py-0.5 font-medium text-brand hover:bg-brand/15 transition"
        title="Open full Source Workspace"
      >
        View source ↗
      </button>
    </div>
  );
}

function computeRisk(confidence: number, coverage: number): AgentActivity["riskLevel"] {
  if (confidence >= 0.8 && coverage >= 0.8) return "none";
  if (confidence >= 0.6 && coverage >= 0.6) return "low";
  if (confidence >= 0.4) return "medium";
  return "high";
}

export default function Chat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<ChatMode>("corpus");
  const [streaming, setStreaming] = useState(false);
  const [trace, setTrace] = useState<TraceSpan[]>([]);
  const [traceSteps, setTraceSteps] = useState<TraceStep[]>([]);
  const [paths, setPaths] = useState<PathEvidence[]>([]);
  const [seeds, setSeeds] = useState<string[]>([]);
  const [streamEntities, setStreamEntities] = useState<string[]>([]);
  const [streamSources, setStreamSources] = useState<Citation[]>([]);
  const [coverage, setCoverage] = useState(0);
  const [lastConfidence, setLastConfidence] = useState(0);
  const [lastRoute, setLastRoute] = useState("fast");
  const [lastStatus, setLastStatus] = useState<string>("answered");
  const [tab, setTab] = useState<Tab>("overview");
  const [showPanel, setShowPanel] = useState(false);
  const [toast, setToast] = useState<{ msg: string; id: number } | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>(FALLBACK_SUGGESTIONS);
  const [phoenixUrl, setPhoenixUrl] = useState<string | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);
  const [vectors, setVectors] = useState<number | null>(null);
  const [entities, setEntities] = useState<number | null>(null);
  const [hasAnswered, setHasAnswered] = useState(false);
  const [corpusRefreshKey, setCorpusRefreshKey] = useState(0);
  const [scopedDocIds, setScopedDocIds] = useState<string[] | null>(null);
  const [ragStrategy, setRagStrategy] = useState<string>("auralynq_rag");
  const [showSettings, setShowSettings] = useState(false);
  const [agentActivity, setAgentActivity] = useState<AgentActivity>({ phase: "idle" });
  const [deployMode, setDeployMode] = useState<DeploymentMode | null>(null);
  const [visualGrounding, setVisualGrounding] = useState<VisualGrounding | null>(null);
  const [activeCitation, setActiveCitation] = useState<string | null>(null);
  const [showWorkspace, setShowWorkspace] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const router = useRouter();
  // new-chat corpus-clear confirmation state
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [clearLoading, setClearLoading] = useState(false);
  const [clearError, setClearError] = useState<string | null>(null);

  const { settings, update: updateSettings } = useUISettings();

  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Load persisted RAG strategy
  useEffect(() => {
    setRagStrategy(loadStoredStrategy());
  }, []);

  // Bootstrap: status, suggestions, persisted conversation
  useEffect(() => {
    health()
      .then(() => setOnline(true))
      .catch(() => setOnline(false));
    fetchSuggestions(4)
      .then((s) => {
        if (s.suggestions?.length) setSuggestions(s.suggestions);
      })
      .catch(() => {});
    statusSummary()
      .then((s) => {
        setPhoenixUrl(s?.tracing?.phoenix_endpoint || null);
        setDeployMode(deploymentMode(s));
        const vecs = s?.index?.vectors ?? s?.corpus?.vector_count ?? null;
        const ents = s?.corpus?.entity_count ?? null;
        setVectors(vecs);
        setEntities(ents);
        if (vecs === 0) {
          try { localStorage.removeItem(STORE_KEY); } catch { /* ignore */ }
          setAgentActivity({ phase: "corpus_empty" });
          return;
        }
        try {
          const raw = localStorage.getItem(STORE_KEY);
          if (raw) {
            const restored: Turn[] = JSON.parse(raw);
            setTurns(restored);
            if (restored.length) setHasAnswered(true);
          }
        } catch {
          /* ignore corrupt cache */
        }
      })
      .catch(() => {
        try {
          const raw = localStorage.getItem(STORE_KEY);
          if (raw) {
            const restored: Turn[] = JSON.parse(raw);
            setTurns(restored);
            if (restored.length) setHasAnswered(true);
          }
        } catch {
          /* ignore corrupt cache */
        }
      });
  }, []);

  // Persist after each completed turn
  useEffect(() => {
    if (streaming) return;
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(turns.slice(-50)));
    } catch {
      /* quota / private mode */
    }
  }, [turns, streaming]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  const flash = useCallback((m: string) => {
    setToast({ msg: m, id: Date.now() });
  }, []);

  function patchLast(update: Partial<Turn>) {
    setTurns((t) => {
      if (t.length === 0) return t;
      const c = [...t];
      c[c.length - 1] = { ...c[c.length - 1], ...update };
      return c;
    });
  }

  const runStream = useCallback(async (q: string) => {
    setStreaming(true);
    setTrace([]);
    setTraceSteps([]);
    setPaths([]);
    setSeeds([]);
    setStreamEntities([]);
    setStreamSources([]);
    setCoverage(0);
    setLastStatus("answered");
    setVisualGrounding(null);
    setActiveCitation(null);
    setShowWorkspace(false);
    setAgentActivity({ phase: "query_received", algorithm: ragStrategy });
    const ac = new AbortController();
    abortRef.current = ac;
    try {
      await askStreamWithStrategy(
        q,
        ragStrategy,
        (e: StreamEvent) => {
          if (e.type === "meta") {
            setPaths(e.path_evidence || []);
            setSeeds(e.seeds || []);
            setStreamEntities(e.detected_entities?.length ? e.detected_entities : e.seeds || []);
            setStreamSources(e.sources || []);
            setCoverage(e.evidence_coverage ?? 0);
            setLastRoute(e.route);
            const isSystemRoute = ["corpus_inventory", "corpus_management", "app_help"].includes(e.route);
            setAgentActivity({
              phase: isSystemRoute ? "system_route" : "retrieval_started",
              route: e.route,
              algorithm: (e as any).rag_strategy || ragStrategy,
              coverage: e.evidence_coverage ?? 0,
            });
            setTab(e.route === "fast" ? "overview" : "evidence");
            patchLast({ route: e.route, rationale: e.rationale });
          } else if (e.type === "token") {
            setAgentActivity((prev) => ({ ...prev, phase: "generating" }));
            setTurns((t) => {
              // Guard: a token can arrive when the assistant turn isn't present
              // (e.g. a StrictMode remount racing the in-flight stream). Never
              // dereference an absent turn.
              if (t.length === 0 || t[t.length - 1]?.role !== "assistant") return t;
              const c = [...t];
              c[c.length - 1] = { ...c[c.length - 1], text: (c[c.length - 1].text ?? "") + (e.text ?? "") };
              return c;
            });
          } else if (e.type === "final") {
            setTrace(e.trace || []);
            setTraceSteps(e.trace_steps || []);
            const finalCov = e.evidence_coverage ?? 0;
            const finalConf = e.confidence ?? 0;
            setCoverage(finalCov);
            setLastConfidence(finalConf);
            setLastStatus(e.status || "answered");
            const risk = computeRisk(finalConf, finalCov);
            setAgentActivity({
              phase: e.status === "insufficient_evidence" ? "abstained" : "done",
              route: lastRoute,
              algorithm: (e as any).selected_rag_strategy || ragStrategy,
              coverage: finalCov,
              confidence: finalConf,
              riskLevel: risk,
              latencyMs: e.elapsed_ms,
              warnings: e.warnings,
              fallback: (e as any).fallback_strategy || null,
            });
            // Capture visual grounding — auto-show Source View side-by-side
            if (e.visual_grounding) {
              setVisualGrounding(e.visual_grounding);
              if (e.visual_grounding.visual_grounding_available) {
                setTab("source");
                setShowPanel(true);
              }
            }
            patchLast({
              text: e.answer,
              citations: e.citations,
              status: e.status,
              insufficient: e.insufficient_evidence_reason || null,
              confidence: e.confidence ?? 0,
              semanticCoverage: (e as any).semantic_coverage ?? undefined,
              model_fit: (e as any).model_fit ?? null,
            });
            if (e.status === "insufficient_evidence") setTab("evidence");
          }
        },
        ac.signal,
        scopedDocIds,
      );
    } catch (err) {
      if (ac.signal.aborted) {
        setTurns((t) => {
          const c = [...t];
          const last = c[c.length - 1];
          if (last?.role === "assistant" && !last.text)
            c[c.length - 1] = { ...last, text: "⏹ Stopped." };
          return c;
        });
        setAgentActivity({ phase: "idle" });
      } else {
        patchLast({ text: `Couldn't reach the backend: ${(err as Error).message}`, error: true });
        setAgentActivity({ phase: "error", error: (err as Error).message });
      }
    } finally {
      setStreaming(false);
      setHasAnswered(true);
      abortRef.current = null;
    }
  }, [ragStrategy, lastRoute, scopedDocIds]);

  const answerInventory = useCallback(async (q: string) => {
    setAgentActivity({ phase: "system_route", route: "corpus_inventory" });
    let summary: CorpusSummary | null = null;
    try {
      summary = await corpusSummary();
    } catch {
      /* fall through */
    }
    setTurns((t) => {
      const c = [...t];
      c[c.length - 1] = summary
        ? { role: "assistant", text: "", inventory: summary, question: q }
        : {
            role: "assistant",
            text: "I couldn't read the corpus inventory right now — the backend may be warming up.",
            error: true,
          };
      return c;
    });
    setHasAnswered(true);
    setTab("overview");
    setAgentActivity({ phase: "done", route: "corpus_inventory" });
  }, []);

  const shapeQuery = useCallback((q: string, m: ChatMode): string => {
    const t = q.trim();
    if (m === "summarize") {
      return t ? `Summarize the key points about: ${t}` : "Summarize the main topics in the indexed documents.";
    }
    return t;
  }, []);

  const send = useCallback(
    (raw: string) => {
      const q = shapeQuery(raw, mode);
      if (!q.trim() || streaming) return;
      setInput("");
      setShowPanel(false);
      const inventory = mode === "inventory" || isInventoryQuestion(q);
      setTurns((t) => [...t, { role: "user", text: q }, { role: "assistant", text: "" }]);
      if (inventory) {
        void answerInventory(q);
      } else {
        void runStream(q);
      }
    },
    [streaming, runStream, answerInventory, mode, shapeQuery],
  );

  const regenerate = useCallback(() => {
    if (streaming) return;
    const lastUser = [...turns].reverse().find((t) => t.role === "user");
    if (!lastUser) return;
    setTurns((t) => {
      const c = [...t];
      if (c.length && c[c.length - 1].role === "assistant") c.pop();
      c.push({ role: "assistant", text: "" });
      return c;
    });
    void runStream(lastUser.text);
  }, [streaming, turns, runStream]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    flash("Generation stopped");
  }, [flash]);

  const handleNewChat = useCallback(() => {
    const m = settings.newChatMode;
    if (m === "chat_only") {
      abortRef.current?.abort();
      setTurns([]);
      setTrace([]);
      setPaths([]);
      setSeeds([]);
      setHasAnswered(false);
      setTab("overview");
      setAgentActivity({ phase: "idle" });
      try { localStorage.removeItem(STORE_KEY); } catch { /* ignore */ }
      flash("New chat");
    } else if (m === "new_workspace") {
      abortRef.current?.abort();
      setTurns([]);
      setTrace([]);
      setPaths([]);
      setSeeds([]);
      setHasAnswered(false);
      setTab("ingest");
      setShowPanel(true);
      setAgentActivity({ phase: "idle" });
      try { localStorage.removeItem(STORE_KEY); } catch { /* ignore */ }
      flash("New workspace — manage your corpus in the Ingest panel");
    } else {
      // clear_corpus — open confirmation dialog
      setClearConfirmOpen(true);
      setClearError(null);
    }
  }, [settings.newChatMode, flash]);

  const executeClearCorpus = useCallback(async () => {
    setClearLoading(true);
    setClearError(null);
    try {
      const preview = await corpusClearPreview();
      await corpusClearConfirm(preview.confirmation_phrase);
      // Clear all local state
      abortRef.current?.abort();
      setTurns([]);
      setTrace([]);
      setPaths([]);
      setSeeds([]);
      setHasAnswered(false);
      setTab("overview");
      setAgentActivity({ phase: "corpus_empty" });
      try { localStorage.removeItem(STORE_KEY); } catch { /* ignore */ }
      // Refresh inventory
      const [s, sug] = await Promise.all([statusSummary(), fetchSuggestions(4)]);
      setVectors(s?.index?.vectors ?? s?.corpus?.vector_count ?? 0);
      setEntities(s?.corpus?.entity_count ?? 0);
      if (sug.suggestions?.length) setSuggestions(sug.suggestions);
      setCorpusRefreshKey((k) => k + 1);
      setClearConfirmOpen(false);
      flash("Corpus cleared — fresh workspace ready");
    } catch (err) {
      setClearError((err as Error).message || "Clear failed");
    } finally {
      setClearLoading(false);
    }
  }, [flash]);

  // Global shortcuts: Esc stops, Cmd+K new chat
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && streaming) stop();
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [streaming, stop]);

  function onVoice(r: AnswerResult & { transcript?: string }) {
    setTurns((t) => [
      ...t,
      { role: "user", text: r.transcript || "voice query", voice: true },
      { role: "assistant", text: r.answer, citations: r.citations, route: r.route },
    ]);
    setPaths(r.path_evidence || []);
    setSeeds(r.seeds || []);
    if (r.trace) setTrace(r.trace);
    setHasAnswered(true);
  }

  const openIngest = useCallback(() => {
    setShowPanel(true);
    setTab("ingest");
  }, []);

  const onCorpusDeleted = useCallback(async () => {
    setPaths([]);
    setSeeds([]);
    try {
      const [s, sug] = await Promise.all([statusSummary(), fetchSuggestions(4)]);
      const vecs = s?.index?.vectors ?? s?.corpus?.vector_count ?? 0;
      setVectors(vecs);
      setEntities(s?.corpus?.entity_count ?? 0);
      if (sug.suggestions?.length) setSuggestions(sug.suggestions);
      if (vecs === 0) setAgentActivity({ phase: "corpus_empty" });
    } catch {
      setVectors(0);
    }
    try { localStorage.removeItem(STORE_KEY); } catch { /* ignore */ }
    setCorpusRefreshKey((k) => k + 1);
    flash("Corpus updated — inventory refreshed");
  }, [flash]);

  const recentMeta: RecentMeta | null = hasAnswered
    ? { route: lastRoute, status: lastStatus, coverage, confidence: lastConfidence }
    : null;

  const lastAssistant = [...turns].reverse().find((t) => t.role === "assistant");

  const traceAlwaysVisible = settings.traceVisibility === "always" || settings.traceVisibility === "auto";

  return (
    <div className="flex h-[100dvh] flex-col bg-ink text-fg">
      <AppBar
        online={online}
        vectors={vectors}
        entities={entities}
        onNewChat={handleNewChat}
        onToggleInspector={() => setShowPanel((v) => !v)}
        inspectorOpen={showPanel}
        onToggleSettings={() => setShowSettings((v) => !v)}
      />

      <DemoBanner mode={deployMode} />

      {/* Settings overlay */}
      {showSettings && (
        <div className="fixed inset-0 z-50 flex items-start justify-end">
          <div
            className="fixed inset-0 bg-ink/60 backdrop-blur-sm"
            onClick={() => setShowSettings(false)}
          />
          <div className="relative z-10 mt-14 mr-3 w-80 rounded-xl border border-edge bg-panel shadow-lg">
            <div className="scroll-thin max-h-[80vh] overflow-y-auto p-3">
              <SettingsPanel
                settings={settings}
                onChange={updateSettings}
                onClose={() => setShowSettings(false)}
              />
            </div>
          </div>
        </div>
      )}

      {/* Clear corpus confirmation dialog */}
      {clearConfirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="fixed inset-0 bg-ink/70 backdrop-blur-sm"
            onClick={() => !clearLoading && setClearConfirmOpen(false)}
          />
          <div className="relative z-10 w-full max-w-md rounded-2xl border border-edge bg-panel p-6 shadow-xl">
            <h2 className="mb-2 text-base font-bold text-fg">Clear corpus and start fresh?</h2>
            <p className="mb-4 text-sm text-fg2">
              This will remove all indexed documents, vectors, and entities. Your chat history will also be cleared.
              This action cannot be undone.
            </p>
            {clearError && (
              <p className="mb-3 rounded border border-bad/30 bg-bad/10 p-2 text-sm text-bad">{clearError}</p>
            )}
            <div className="flex gap-2">
              <button
                className="btn-ghost flex-1"
                onClick={() => setClearConfirmOpen(false)}
                disabled={clearLoading}
              >
                Cancel
              </button>
              <button
                className="flex-1 rounded-xl border border-bad/40 bg-bad/10 px-4 py-2 text-sm font-medium text-bad transition hover:bg-bad/20 disabled:opacity-50"
                onClick={executeClearCorpus}
                disabled={clearLoading}
              >
                {clearLoading ? "Clearing…" : "Clear everything"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Full-viewport grid: chat | inspector */}
      <div
        className="grid w-full flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[minmax(0,1fr)_auto_var(--inspector-width,clamp(360px,30vw,560px))]"
      >
        {/* Conversation column */}
        <section className="flex min-h-0 flex-col">
          <div
            ref={scrollRef}
            role="log"
            aria-live="polite"
            aria-label="Conversation"
            className="scroll-thin flex-1 overflow-y-auto px-3 py-4 md:px-6 xl:px-8"
          >
            <div className="mx-auto max-w-[var(--chat-max-width,900px)] space-y-4">
              {turns.length === 0 ? (
                <EmptyConversation suggestions={suggestions} onAsk={send} onIngest={openIngest} />
              ) : (
                turns.map((t, i) => {
                  const isLastAssistant =
                    i === turns.length - 1 && t.role === "assistant";
                  const showVG =
                    isLastAssistant &&
                    !streaming &&
                    visualGrounding?.visual_grounding_available &&
                    (t.citations?.length ?? 0) > 0;
                  return (
                    <div key={i} className="msg-in">
                      {isLastAssistant && streaming && (streamEntities.length > 0 || streamSources.length > 0 || !!t.route) && (
                        <StreamingEvidence route={t.route} entities={streamEntities} sources={streamSources} />
                      )}
                      <Message
                        turn={t}
                        streaming={streaming}
                        isLast={i === turns.length - 1}
                        onRegenerate={t.role === "assistant" ? regenerate : undefined}
                        onAsk={send}
                        onIngest={openIngest}
                        onOpenSource={(marker) => {
                          setActiveCitation(String(marker));
                          setShowWorkspace(true);
                        }}
                      />
                      {showVG && (
                        <InlineSourceStrip
                          grounding={visualGrounding!}
                          onOpen={() => { setTab("source"); setShowPanel(true); }}
                          onOpenWorkspace={() => setShowWorkspace(true)}
                        />
                      )}
                      {isLastAssistant && !streaming && traceSteps.length > 0 && (
                        <AnswerSteps steps={traceSteps} />
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* sticky composer */}
          <div className="mx-auto w-full max-w-[var(--chat-max-width,900px)] px-2 pb-2">
            <Composer
              input={input}
              setInput={setInput}
              mode={mode}
              setMode={setMode}
              streaming={streaming}
              onSend={send}
              onStop={stop}
              onVoiceResult={onVoice}
              onUploadClick={openIngest}
              ragStrategy={ragStrategy}
              onRagStrategyChange={setRagStrategy}
            />
          </div>
        </section>

        {/* Draggable divider — expand the chat or the inspector on the fly (lg+). */}
        <PanelResizer />

        {/* Inspector — always visible on desktop (lg+), mobile drawer when showPanel */}
        <aside
          className={
            showPanel
              ? "fixed inset-0 z-50 flex flex-col border-l border-edge bg-ink/95 backdrop-blur-sm lg:static lg:min-h-0 lg:bg-panel/60"
              : "hidden min-h-0 flex-col border-l border-edge bg-panel/60 lg:flex"
          }
        >
          {/* Always-visible Agent Activity Rail */}
          {traceAlwaysVisible && (
            <div className="border-b border-edge px-3 py-2">
              <AgentActivityRail
                activity={agentActivity}
                traceSteps={traceSteps}
                streaming={streaming}
              />
            </div>
          )}

          <div className="flex items-center gap-0.5 overflow-x-auto border-b border-edge bg-panel/40 px-2 py-1.5">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                aria-pressed={tab === t}
                className={`tab capitalize text-xs ${tab === t ? "tab-active" : ""}`}
              >
                {TAB_ICON[t] && <span className="opacity-70">{TAB_ICON[t]}</span>}
                {t}
              </button>
            ))}
            <button
              onClick={() => setShowPanel(false)}
              className="btn-ghost ml-auto px-2 py-1 text-xs lg:hidden"
              aria-label="Close inspector"
            >
              ✕
            </button>
          </div>
          <div className="scroll-thin min-h-0 flex-1 overflow-y-auto p-3">
            {tab === "overview" && (
              <div className="space-y-3">
                <InspectorOverview
                  suggestions={suggestions}
                  recent={recentMeta}
                  onAsk={send}
                  onIngest={openIngest}
                  refreshKey={corpusRefreshKey}
                />
                <SourceScope refreshKey={corpusRefreshKey} onChange={setScopedDocIds} />
              </div>
            )}
            {tab === "trace" && (
              <TracePanel
                trace={trace}
                steps={traceSteps}
                meta={{
                  route: lastRoute,
                  status: lastStatus,
                  confidence: lastConfidence,
                  coverage,
                  phoenixUrl,
                }}
                visualGrounding={visualGrounding}
              />
            )}
            {tab === "evidence" && (
              <EvidencePaths
                paths={paths}
                seeds={seeds}
                coverage={coverage}
                citations={lastAssistant?.citations || []}
                visualGrounding={visualGrounding}
                onOpenSource={(cid) => {
                  setActiveCitation(cid);
                  setShowWorkspace(true);
                }}
                onOpenSourceTab={() => {
                  setShowWorkspace(true);
                }}
              />
            )}
            {tab === "source" && (
              <SourceViewPanel
                grounding={visualGrounding}
                activeCitation={activeCitation}
                onOpenWorkspace={
                  visualGrounding?.visual_grounding_available
                    ? () => setShowWorkspace(true)
                    : undefined
                }
              />
            )}
            {tab === "ingest" && (
              <div className="space-y-4">
                <IngestPanel onAsk={send} onDeleted={onCorpusDeleted} />
                <div className="border-t border-edge/60 pt-3">
                  <WatchPanel onSynced={onCorpusDeleted} />
                </div>
              </div>
            )}
            {tab === "wiki" && <WikiPanel refreshKey={corpusRefreshKey} />}
            {tab === "eval" && <EvalPanel />}
          </div>
        </aside>
      </div>

      {/* Source Workspace Modal — full-screen overlay */}
      {showWorkspace && (
        <SourceWorkspaceModal
          grounding={visualGrounding}
          citations={lastAssistant?.citations || []}
          activeCitation={activeCitation}
          onClose={() => setShowWorkspace(false)}
        />
      )}

      {toast && (
        <Toast key={toast.id} message={toast.msg} onClose={() => setToast(null)} />
      )}

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        commands={
          [
            { id: "new", group: "Chat", label: "New chat", icon: Plus, keywords: ["reset", "clear"], run: handleNewChat },
            {
              id: "focus",
              group: "Chat",
              label: "Focus composer",
              icon: MessageSquarePlus,
              run: () =>
                document.querySelector<HTMLTextAreaElement>('textarea[aria-label="Ask a question"]')?.focus(),
            },
            ...(visualGrounding?.visual_grounding_available
              ? [{ id: "src", group: "Chat", label: "Open Source Workspace", icon: PanelRight, run: () => setShowWorkspace(true) }]
              : []),
            { id: "modelfit", group: "Navigate", label: "Go to ModelFit", icon: Cpu, run: () => router.push("/modelfit") },
            { id: "home", group: "Navigate", label: "Go to Home", icon: Home, run: () => router.push("/") },
            { id: "s-aura", group: "Retrieval strategy", label: "Use Auralynq-RAG", icon: Zap, run: () => setRagStrategy("auralynq_rag") },
            { id: "s-hybrid", group: "Retrieval strategy", label: "Use Hybrid vector", icon: Zap, run: () => setRagStrategy("hybrid") },
            { id: "s-naive", group: "Retrieval strategy", label: "Use Naive vector", icon: Zap, run: () => setRagStrategy("naive_vector") },
            { id: "s-bm25", group: "Retrieval strategy", label: "Use Keyword BM25", icon: Zap, run: () => setRagStrategy("keyword_bm25") },
            {
              id: "theme",
              group: "Appearance",
              label: "Switch theme",
              icon: Palette,
              run: () => {
                const nx = nextTheme(coerceTheme(document.documentElement.dataset.theme));
                document.documentElement.dataset.theme = nx;
                try {
                  localStorage.setItem(THEME_KEY, nx);
                } catch {}
              },
            },
          ] as Cmd[]
        }
      />
    </div>
  );
}

const SUGGESTION_ICONS = ["◈", "◎", "◇", "◆"];

function EmptyConversation({
  suggestions,
  onAsk,
  onIngest,
}: {
  suggestions: string[];
  onAsk: (q: string) => void;
  onIngest: () => void;
}) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-8 px-4 text-center">
      {/* Hero */}
      <div className="space-y-4">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-brand/20 via-brand/10 to-brand2/20 ring-1 ring-brand/20 shadow-lg">
          <svg viewBox="0 0 32 32" fill="none" className="h-8 w-8" aria-hidden>
            <rect x="2"  y="13" width="4" height="6"  rx="2" fill="currentColor" className="text-brand"  opacity="0.6" />
            <rect x="8"  y="9"  width="4" height="14" rx="2" fill="currentColor" className="text-brand"  opacity="0.8" />
            <rect x="14" y="4"  width="4" height="24" rx="2" fill="currentColor" className="text-brand2" />
            <rect x="20" y="9"  width="4" height="14" rx="2" fill="currentColor" className="text-brand"  opacity="0.8" />
            <rect x="26" y="13" width="4" height="6"  rx="2" fill="currentColor" className="text-brand"  opacity="0.6" />
          </svg>
        </div>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            <span className="text-brand">Talk</span>
            <span className="text-fg"> to your </span>
            <span className="text-brand2">data</span>
          </h1>
          <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-fg2">
            Grounded, cited answers from your indexed documents — by text or voice.
          </p>
        </div>
      </div>

      {/* 2 × 2 suggestion grid */}
      <div className="grid w-full max-w-xl grid-cols-1 gap-2 sm:grid-cols-2">
        {suggestions.slice(0, 4).map((s, i) => (
          <button
            key={s}
            onClick={() => onAsk(s)}
            className="card card-hover group flex flex-col items-start gap-2 px-4 py-4 text-left"
          >
            <span
              className="text-lg text-brand transition-transform duration-200 group-hover:scale-110"
              aria-hidden
            >
              {SUGGESTION_ICONS[i % SUGGESTION_ICONS.length]}
            </span>
            <span className="text-sm leading-snug text-fg2">{s}</span>
          </button>
        ))}
      </div>

      <button onClick={onIngest} className="btn-outline flex items-center gap-2 text-sm">
        <svg
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-4 w-4"
          aria-hidden
        >
          <path d="M10 3v11M5 8l5-5 5 5M4 17h12" />
        </svg>
        Add documents to your corpus
      </button>
    </div>
  );
}
