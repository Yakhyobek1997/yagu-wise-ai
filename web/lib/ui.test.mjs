// Structural UI guards for the premium redesign. The project's test harness is
// dependency-free (no DOM runtime), so these assert that each redesigned surface
// composes the required sections, copy and states at the source level — catching
// accidental regressions of the acceptance criteria without a browser.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (p) => readFileSync(join(root, p), "utf8");

let passed = 0;
const t = (name, fn) => {
  fn();
  passed++;
  console.log("  ok", name);
};
const has = (src, needle, msg) =>
  assert.ok(src.includes(needle), msg || `expected to find: ${needle}`);

// ---- landing composes all main sections ---------------------------------
t("landing page renders all main sections", () => {
  const page = read("app/page.tsx");
  for (const s of ["Hero", "SystemStatus", "Features", "HowItWorks", "Differentiators", "Stack", "CTA", "Footer"]) {
    has(page, `<${s} `, `landing missing <${s}>`);
  }
});

t("hero has value prop, dual CTAs and trust badges", () => {
  const hero = read("components/landing/Hero.tsx");
  has(hero, "Voice-native RAG for private documents");
  has(hero, "/chat"); // launch CTA
  has(hero, "github.com/MHHamdan/Auralynq"); // github CTA
  for (const b of ["Local-first", "$0 default", "Open source", "Citations on every answer", "Voice in / out", "Provider-agnostic"]) {
    has(hero, b, `hero missing trust badge: ${b}`);
  }
});

t("system status surfaces the seven subsystems with health states", () => {
  const s = read("components/landing/SystemStatus.tsx");
  for (const g of ["API", "Corpus", "Vector DB", "Embeddings", "LLM", "ASR / TTS", "Tracing"]) {
    has(s, g, `status missing group: ${g}`);
  }
  for (const h of ["healthy", "degraded", "offline"]) has(s, h);
});

t("capabilities render six benefit cards", () => {
  const f = read("components/landing/Features.tsx");
  for (const c of [
    "Voice-native document chat",
    "Grounded answers with citations",
    "PathRAG graph reasoning",
    "Hybrid retrieval & reranking",
    "Agent trace & observability",
    "Local-first provider routing",
  ]) {
    has(f, c, `features missing card: ${c}`);
  }
});

t("how-it-works renders the nine-step pipeline", () => {
  const h = read("components/landing/HowItWorks.tsx");
  for (const step of ["Upload", "Parse", "Chunk", "Index", "Retrieve", "Rerank", "Reason", "Cite", "Observe"]) {
    has(h, step, `pipeline missing step: ${step}`);
  }
});

t("differentiators proof section exists", () => {
  const d = read("components/landing/Differentiators.tsx");
  has(d, "What makes Auralynq different?");
  has(d, "Evidence-gated abstention");
  has(d, "Local-first by default");
});

// ---- chat shell ----------------------------------------------------------
t("chat uses app bar, composer and never-empty inspector overview", () => {
  const page = read("app/chat/page.tsx");
  has(page, "<AppBar");
  has(page, "<Composer");
  has(page, "<InspectorOverview");
  has(page, '"overview"'); // default inspector tab
});

t("composer has mode selector, voice, upload and key hints", () => {
  const c = read("components/chat/Composer.tsx");
  for (const m of ["Ask corpus", "Summarize", "Inventory", "Web"]) has(c, m);
  has(c, "VoiceRecorder");
  has(c, "Upload a document");
  has(c, "Shift");
});

t("voice recorder exposes explicit states", () => {
  const v = read("components/VoiceRecorder.tsx");
  for (const st of ["idle", "listening", "transcribing", "speaking", "failed"]) has(v, st);
});

t("inspector overview is useful before any query", () => {
  const o = read("components/chat/InspectorOverview.tsx");
  for (const s of ["Your corpus", "System status", "Try asking"]) has(o, s);
});

t("inspector overview shows a first-run checklist for an empty corpus", () => {
  const o = read("components/chat/InspectorOverview.tsx");
  has(o, "First run");
  has(o, "!summary.indexed"); // only shown before any document is indexed
  for (const step of [
    "Upload a document",
    "Ask a question",
    "Click a citation",
    "Open the Source Workspace",
    "Try ModelFit",
    "Run a benchmark",
  ]) {
    has(o, step, `first-run checklist missing step: ${step}`);
  }
});

// ---- inspector panels ----------------------------------------------------
t("evidence panel has coverage, breakdown, debug disclosure and empty state", () => {
  const e = read("components/EvidencePaths.tsx");
  has(e, "Evidence coverage");
  has(e, "displaySource");
  has(e, "Debug · raw source");
  has(e, "Ask a question to see the evidence trail");
  has(e, "whySelected");
});

t("trace panel has summary dashboard and Phoenix card", () => {
  const tr = read("components/TracePanel.tsx");
  has(tr, "Hallu. risk");
  has(tr, "Open in Phoenix");
  has(tr, "not connected"); // degraded hint
  has(tr, "Run a query to see the trace");
});

t("eval panel has feedback widget and planned evals", () => {
  const ev = read("components/EvalPanel.tsx");
  has(ev, "Rate the last answer");
  has(ev, "Groundedness");
  has(ev, "Abstention correctness");
});

t("insufficient-evidence card uses soft warning copy", () => {
  const ie = read("components/InsufficientEvidence.tsx");
  has(ie, "Not enough evidence in your indexed documents");
  has(ie, "held back instead of guessing");
  has(ie, "border-warn"); // soft warning, not error red
});

t("corpus inventory renders the inventory fields", () => {
  const ci = read("components/CorpusInventory.tsx");
  for (const field of ["Documents", "Languages", "File types", "Last indexed", "Top topics"]) {
    has(ci, field, `inventory missing field: ${field}`);
  }
});

t("citations clean internal paths via displaySource", () => {
  has(read("components/Citations.tsx"), "displaySource");
  has(read("components/Message.tsx"), "CorpusInventory");
});

// ---- design system -------------------------------------------------------
t("design tokens define all three themes with status + text scale", () => {
  const css = read("app/globals.css");
  for (const th of ['[data-theme="dark"]', '[data-theme="light"]', '[data-theme="comfort"]']) has(css, th);
  for (const tok of ["--c-text-2", "--c-text-3", "--c-ok", "--c-warn", "--c-bad", "--ring"]) has(css, tok);
  has(css, ".focusable");
  has(css, ".evidence-strong");
});

// ---- new: trace rail, algorithm selector, settings -----------------------
t("agent activity rail is always visible in chat inspector", () => {
  const page = read("app/chat/page.tsx");
  has(page, "AgentActivityRail");
  has(page, "traceAlwaysVisible");
  has(page, "agentActivity");
});

t("agent activity rail has all required states", () => {
  const rail = read("components/chat/AgentActivityRail.tsx");
  has(rail, "idle");
  has(rail, "generating");
  has(rail, "abstained");
  has(rail, "corpus_empty");
  has(rail, "system_route");
  has(rail, "TraceMiniTimeline");
  has(rail, "AlgorithmBadge");
  has(rail, "RiskBadge");
  has(rail, "Ready — ask a question to see agent activity");
});

t("algorithm selector renders strategy dropdown near composer", () => {
  const sel = read("components/chat/AlgorithmSelector.tsx");
  has(sel, "RAG Algorithm");
  has(sel, "Available");
  has(sel, "Experimental");
  has(sel, "Planned");
  has(sel, "auralynq_rag");
  has(sel, "fetchRAGStrategies");
  has(sel, "auralynq.rag_strategy.v1");
});

t("composer includes algorithm selector", () => {
  const c = read("components/chat/Composer.tsx");
  has(c, "AlgorithmSelector");
  has(c, "ragStrategy");
  has(c, "onRagStrategyChange");
});

t("settings panel has all configurable options", () => {
  const sp = read("components/chat/SettingsPanel.tsx");
  has(sp, "Font Size");
  has(sp, "Density");
  has(sp, "Inspector Width");
  has(sp, "Trace Visibility");
  has(sp, "New Chat Behavior");
  has(sp, "chat_only");
  has(sp, "clear_corpus");
  has(sp, "--font-scale");
  has(sp, "--inspector-width");
});

t("css defines font-scale and density CSS variables", () => {
  const css = read("app/globals.css");
  has(css, "--font-scale");
  has(css, "--density-scale");
  has(css, "--inspector-width");
  has(css, "--chat-max-width");
});

t("new chat supports clear-corpus mode with confirmation", () => {
  const page = read("app/chat/page.tsx");
  has(page, "clear_corpus");
  has(page, "clearConfirmOpen");
  has(page, "executeClearCorpus");
  has(page, "This will remove all indexed documents");
});

t("app bar shows entities count and settings button", () => {
  const bar = read("components/chat/AppBar.tsx");
  has(bar, "entities");
  has(bar, "onToggleSettings");
  has(bar, "Display settings");
});

t("eval panel shows last query metrics from backend", () => {
  const ev = read("components/EvalPanel.tsx");
  has(ev, "evalLast");
  has(ev, "Last query metrics");
  has(ev, "exportEvalRun");
  has(ev, "Strategy comparison");
});

// ---- visual grounding & source view ----------------------------------------

t("source view tab added to chat inspector", () => {
  const page = read("app/chat/page.tsx");
  has(page, '"source"');
  has(page, "SourceViewPanel");
  has(page, "visualGrounding");
  has(page, "activeCitation");
});

t("source view panel has page viewer, overlay and legend", () => {
  const sv = read("components/SourceViewPanel.tsx");
  has(sv, "PageViewer");
  has(sv, "HighlightBox");
  has(sv, "ClaimGroundingView");
  has(sv, "normalized_bbox");
  has(sv, "reindex_required");
  has(sv, "visual_grounding_available");
  has(sv, "Source View");
  has(sv, "Reindex");
  has(sv, "grounding_stage");
});

t("source view panel handles unavailable grounding gracefully", () => {
  const sv = read("components/SourceViewPanel.tsx");
  has(sv, "Visual grounding not available");
  has(sv, "Ask a question to see source grounding");
});

t("source view panel has zoom controls", () => {
  const sv = read("components/SourceViewPanel.tsx");
  has(sv, "Zoom in");
  has(sv, "Zoom out");
  has(sv, "fit");
});

t("evidence panel has source view open button on citations", () => {
  const ev = read("components/EvidencePaths.tsx");
  has(ev, "onOpenSource");
  has(ev, "onOpenSourceTab");
  has(ev, "Open Source View");
  has(ev, "hasVisualGrounding");
  has(ev, "Visual grounding");
});

t("api has visual grounding types and fetchers", () => {
  const api = read("lib/api.ts");
  has(api, "VisualGrounding");
  has(api, "VisualHighlight");
  has(api, "ClaimGrounding");
  has(api, "fetchDocumentPages");
  has(api, "documentPageImageUrl");
  has(api, "visual_grounding_available");
  has(api, "grounding_stage");
  has(api, "normalized_bbox");
});

t("answer result type includes visual grounding field", () => {
  const api = read("lib/api.ts");
  has(api, "visual_grounding?: VisualGrounding | null");
});

t("source view panel renders highlight boxes with citation colors", () => {
  const sv = read("components/SourceViewPanel.tsx");
  has(sv, "CITATION_COLORS");
  has(sv, "colorFor");
  has(sv, "borderFor");
  has(sv, "color_index");
});

t("source view panel shows claim grounding with support status", () => {
  const sv = read("components/SourceViewPanel.tsx");
  has(sv, "supported");
  has(sv, "partial");
  has(sv, "unsupported");
  has(sv, "SUPPORT_CLS");
  has(sv, "SUPPORT_LABEL");
});

t("chat page clears visual grounding on new query", () => {
  const page = read("app/chat/page.tsx");
  has(page, "setVisualGrounding(null)");
  has(page, "setActiveCitation(null)");
});

// ---- Source Workspace Modal structural tests ----------------------------

t("SourceWorkspaceModal component file exists and exports correctly", () => {
  const sw = read("components/SourceWorkspaceModal.tsx");
  has(sw, "export function SourceWorkspaceModal");
  has(sw, "export interface SourceWorkspaceModalProps");
  has(sw, "grounding: VisualGrounding | null | undefined");
  has(sw, "citations: Citation[]");
  has(sw, "activeCitation: string | null");
  has(sw, "onClose: () => void");
});

t("SourceWorkspaceModal renders three-panel layout with citation and evidence panels", () => {
  const sw = read("components/SourceWorkspaceModal.tsx");
  has(sw, "CitationPanel");
  has(sw, "EvidencePanel");
  has(sw, "WorkspacePageViewer");
  has(sw, "grid-cols-[260px_1fr_280px]");
  has(sw, "Grounded Source Workspace");
});

t("SourceWorkspaceModal has zoom controls with fit-width preset", () => {
  const sw = read("components/SourceWorkspaceModal.tsx");
  has(sw, "ZOOM_PRESETS");
  has(sw, "ZOOM_LABELS");
  has(sw, "fit");
  has(sw, "setZoom");
});

t("SourceWorkspaceModal has page navigation controls", () => {
  const sw = read("components/SourceWorkspaceModal.tsx");
  has(sw, "navigatePage");
  has(sw, "hasPrev");
  has(sw, "hasNext");
  has(sw, "currentPageKey");
  has(sw, "ArrowRight");
});

t("SourceWorkspaceModal supports full-screen mode toggle", () => {
  const sw = read("components/SourceWorkspaceModal.tsx");
  has(sw, "fullscreen");
  has(sw, "setFullscreen");
  has(sw, "Show side panels");
  has(sw, "Full-screen PDF view");
});

t("SourceWorkspaceModal handles unavailable grounding gracefully", () => {
  const sw = read("components/SourceWorkspaceModal.tsx");
  has(sw, "visual_grounding_available");
  has(sw, "Visual grounding not available");
  has(sw, "Reindex");
});

t("SourceWorkspaceModal navigates to active citation page on open", () => {
  const sw = read("components/SourceWorkspaceModal.tsx");
  has(sw, "activeCitation");
  has(sw, "initialPageKey");
  has(sw, "setCurrentPageKey");
});

t("SourceWorkspaceModal closes on Escape key", () => {
  const sw = read("components/SourceWorkspaceModal.tsx");
  has(sw, "Escape");
  has(sw, "onClose");
  has(sw, "window.addEventListener");
});

t("WorkspacePageViewer places overlays with normalized bbox percentages", () => {
  const sw = read("components/SourceWorkspaceModal.tsx");
  has(sw, "normalized_bbox");
  has(sw, "position: \"absolute\"");
  has(sw, ".toFixed(3)}%");
});

t("chat page opens workspace modal when View source is clicked", () => {
  const page = read("app/chat/page.tsx");
  has(page, "showWorkspace");
  has(page, "setShowWorkspace");
  has(page, "SourceWorkspaceModal");
  has(page, "onOpenWorkspace");
});

t("chat page resets workspace state on new query", () => {
  const page = read("app/chat/page.tsx");
  has(page, "setShowWorkspace(false)");
});

t("InlineSourceStrip has two buttons: preview and view source workspace", () => {
  const page = read("app/chat/page.tsx");
  has(page, "onOpenWorkspace");
  has(page, "View source ↗");
  has(page, "Preview");
});

t("SourceViewPanel has Expand button to open workspace", () => {
  const sv = read("components/SourceViewPanel.tsx");
  has(sv, "onOpenWorkspace");
  has(sv, "Expand");
  has(sv, "Open full Source Workspace");
});

t("AlgorithmSelector groups strategies by status", () => {
  const sel = read("components/chat/AlgorithmSelector.tsx");
  has(sel, "GROUP_CONFIG");
  has(sel, "Available now");
  has(sel, "Experimental");
  has(sel, "Planned / requires setup");
  has(sel, "StatusGroup");
});

t("AlgorithmSelector planned strategies are non-selectable", () => {
  const sel = read("components/chat/AlgorithmSelector.tsx");
  has(sel, "selectable: false");
  has(sel, "cursor-not-allowed");
  has(sel, "disabled={!selectable}");
});

t("api.ts exports PageLayoutBlock and PageLayoutResponse types", () => {
  const api = read("lib/api.ts");
  has(api, "export interface PageLayoutBlock");
  has(api, "export interface PageLayoutResponse");
  has(api, "export async function fetchPageLayout");
});

t("api.ts exports fetchPageLayout with correct URL pattern", () => {
  const api = read("lib/api.ts");
  has(api, "/pages/${page}/layout");
  has(api, "encodeURIComponent(docId)");
});

console.log(`\n${passed} ui structure tests passed`);
