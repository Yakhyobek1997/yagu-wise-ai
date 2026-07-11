// Pure, framework-free presentation helpers — unit-testable in node.
// The backend cites sources by their stored path (e.g. an upload path like
// "/app/data/storage/uploads/2024/report.pdf"). Those internal paths must never
// be shown to users; we surface a clean, human filename instead and keep the
// raw value only behind a debug disclosure.

/** True for values that look like an internal storage / upload path. */
export function isInternalPath(source: string): boolean {
  if (!source) return false;
  return (
    source.includes("/app/data/") ||
    source.includes("/storage/") ||
    source.includes("/uploads/") ||
    /^[a-z]+:\/\//i.test(source) === false && source.includes("/") && source.startsWith("/")
  );
}

/**
 * Clean a citation source into a readable, user-facing label.
 * - strips directory paths → keeps the filename
 * - URL-decodes percent-encoding
 * - drops a leading content-hash/uuid prefix like "a1b2c3d4_name.pdf"
 * - falls back to the original (trimmed) string when nothing to clean
 */
export function displaySource(source: string | null | undefined): string {
  if (!source) return "Untitled source";
  let s = String(source).trim();
  if (!s) return "Untitled source";

  // Keep real http(s) URLs but show just host + last path segment.
  const urlMatch = /^(https?:\/\/)([^/]+)(\/.*)?$/i.exec(s);
  if (urlMatch) {
    const host = urlMatch[2].replace(/^www\./, "");
    const tail = (urlMatch[3] || "").split("/").filter(Boolean).pop();
    return tail ? `${host}/${decodeURIComponent(tail)}` : host;
  }

  // Otherwise treat as a filesystem path: take the basename.
  s = s.replace(/\\/g, "/");
  const base = s.split("/").filter(Boolean).pop() || s;
  let name = base;
  try {
    name = decodeURIComponent(base);
  } catch {
    /* leave as-is on malformed encoding */
  }
  // Drop a leading hex/uuid hash prefix used for dedupe (e.g. 8+ hex then _ or -).
  name = name.replace(/^[0-9a-f]{8,}[._-]/i, "");
  return name || "Untitled source";
}

/** Short relative-time label from an ISO timestamp. */
export function timeAgo(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return "never";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "unknown";
  const mins = Math.round((now - t) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

/** Map a 0..1 evidence-coverage score to a strength tier + label. */
export type EvidenceTier = "strong" | "weak" | "none";
export function coverageTier(coverage: number): EvidenceTier {
  const pct = Math.max(0, Math.min(1, coverage));
  if (pct >= 0.6) return "strong";
  if (pct >= 0.35) return "weak";
  return "none";
}

/**
 * Heuristic: does this question ask about the *collection itself* (what's
 * indexed, languages, file types, counts) rather than the documents' content?
 * Such questions should render a corpus-inventory answer, not an evidence
 * failure (e.g. "Is there any document in Arabic in my collection?").
 */
export function isInventoryQuestion(q: string): boolean {
  if (!q) return false;
  const s = q.toLowerCase();
  const corpusWord = /\b(corpus|collection|knowledge base|index(?:ed)?|library|uploaded|ingest(?:ed)?|documents?|files?|docs?)\b/.test(
    s,
  );
  const inventoryIntent =
    /\b(how many|what|which|list|are there|is there|any|do you have|contain|languages?|file types?|formats?|last (?:indexed|updated)|what'?s in)\b/.test(
      s,
    );
  // Strong single-phrase triggers.
  if (/\b(in my (?:collection|corpus|library)|in the (?:collection|corpus))\b/.test(s)) return true;
  if (/\bwhat (?:documents?|files?|docs?) /.test(s)) return true;
  if (/\b(languages?|file types?|formats?)\b/.test(s) && corpusWord) return true;
  // "Last document added/uploaded/ingested" and similar recency queries.
  if (/\b(last|latest|most recent|recently)\b.*\b(document|file|doc|upload|ingest|added)\b/.test(s)) return true;
  if (/\bwhat.*\b(last|latest|most recent)\b.*\b(document|file|upload)\b/.test(s)) return true;
  if (/\b(last|latest)\b.*\b(document|file)\b.*(add|upload|ingest)/.test(s)) return true;
  return corpusWord && inventoryIntent && s.length < 120;
}

/** Human label for a relevance/score value in [0,1]. */
export function relevanceLabel(score: number): string {
  if (score >= 0.66) return "high";
  if (score >= 0.4) return "medium";
  return "low";
}

/**
 * Heuristic: does this question request a corpus management action (delete,
 * clear, reset) rather than asking about corpus content?
 */
export function isCorpusManagementQuestion(q: string): boolean {
  if (!q) return false;
  const s = q.toLowerCase();
  // Explicit destructive intent
  if (/\b(delete|remove|wipe|clear|purge|erase|drop|reset)\b/.test(s) &&
      /\b(document|file|corpus|collection|index|vector|upload|pdf|docx|everything|all|data|last)\b/.test(s)) return true;
  if (/\b(how|can i|how do i|can you)\b.*\b(delete|remove|clear|wipe)\b/.test(s)) return true;
  if (/\bremove.*permanently\b/.test(s) || /\bdelete.*permanently\b/.test(s)) return true;
  if (/\b(clear|wipe|reset)\b.*\b(corpus|collection|vectors?|index|everything|all)\b/.test(s)) return true;
  if (/\b(delete|remove)\b.*\b(last|latest|most recent)\b.*\b(document|file|upload)\b/.test(s)) return true;
  return false;
}
