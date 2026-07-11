// Dependency-free unit tests for presentation helpers (run: npm run test:format).
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Compile format.ts -> JS with the project's TypeScript, then import it.
const dir = mkdtempSync(join(tmpdir(), "format-test-"));
execFileSync(
  "node",
  [
    "node_modules/typescript/bin/tsc",
    "lib/format.ts",
    "--module",
    "esnext",
    "--target",
    "es2021",
    "--moduleResolution",
    "bundler",
    "--outDir",
    dir,
  ],
  { stdio: "inherit" },
);
const {
  displaySource,
  isInternalPath,
  timeAgo,
  coverageTier,
  relevanceLabel,
  isInventoryQuestion,
} = await import(join(dir, "format.js"));

let passed = 0;
const t = (name, fn) => {
  fn();
  passed++;
  console.log("  ok", name);
};

t("displaySource strips internal upload paths to filename", () => {
  assert.equal(displaySource("/app/data/storage/uploads/2024/report.pdf"), "report.pdf");
  assert.equal(displaySource("/app/data/storage/uploads/pathrag.pdf"), "pathrag.pdf");
});

t("displaySource drops a leading content-hash prefix", () => {
  assert.equal(displaySource("/uploads/a1b2c3d4e5f6_quarterly.docx"), "quarterly.docx");
});

t("displaySource decodes percent-encoding", () => {
  assert.equal(displaySource("/storage/My%20Report.pdf"), "My Report.pdf");
});

t("displaySource keeps plain titles untouched", () => {
  assert.equal(displaySource("PathRAG paper"), "PathRAG paper");
});

t("displaySource shows host + tail for http urls", () => {
  assert.equal(displaySource("https://www.example.com/docs/intro.html"), "example.com/intro.html");
});

t("displaySource handles empty/nullish", () => {
  assert.equal(displaySource(""), "Untitled source");
  assert.equal(displaySource(null), "Untitled source");
  assert.equal(displaySource(undefined), "Untitled source");
});

t("isInternalPath flags storage paths but not plain titles", () => {
  assert.equal(isInternalPath("/app/data/storage/uploads/x.pdf"), true);
  assert.equal(isInternalPath("PathRAG paper"), false);
  assert.equal(isInternalPath("report.pdf"), false);
});

t("timeAgo formats relative time", () => {
  const now = Date.parse("2024-01-01T12:00:00Z");
  assert.equal(timeAgo(null, now), "never");
  assert.equal(timeAgo("2024-01-01T11:59:50Z", now), "just now");
  assert.equal(timeAgo("2024-01-01T11:30:00Z", now), "30m ago");
  assert.equal(timeAgo("2024-01-01T09:00:00Z", now), "3h ago");
  assert.equal(timeAgo("garbage", now), "unknown");
});

t("coverageTier maps coverage to strength", () => {
  assert.equal(coverageTier(0.9), "strong");
  assert.equal(coverageTier(0.45), "weak");
  assert.equal(coverageTier(0.1), "none");
});

t("relevanceLabel buckets scores", () => {
  assert.equal(relevanceLabel(0.8), "high");
  assert.equal(relevanceLabel(0.5), "medium");
  assert.equal(relevanceLabel(0.2), "low");
});

t("isInventoryQuestion detects collection/inventory questions", () => {
  assert.equal(isInventoryQuestion("Is there any document in Arabic in my collection?"), true);
  assert.equal(isInventoryQuestion("What documents are indexed?"), true);
  assert.equal(isInventoryQuestion("How many files are in the corpus?"), true);
  assert.equal(isInventoryQuestion("What languages are in my documents?"), true);
  assert.equal(isInventoryQuestion("What file types do you have?"), true);
});

t("isInventoryQuestion ignores content questions", () => {
  assert.equal(isInventoryQuestion("How does PathRAG prune relational paths?"), false);
  assert.equal(isInventoryQuestion("Summarize the treatment for sepsis."), false);
  assert.equal(isInventoryQuestion(""), false);
});

console.log(`\n${passed} format tests passed`);
