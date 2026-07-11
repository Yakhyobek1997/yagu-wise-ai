// Dependency-free unit tests for the SSE parser (run: npm run test:sse).
// Regression guard for the CRLF bug that left the chat UI with no rendered answer.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Compile sse.ts -> JS with the TypeScript compiler already in devDependencies,
// then import it — keeps the test free of any JS test framework.
const dir = mkdtempSync(join(tmpdir(), "sse-test-"));
execFileSync(
  "node",
  [
    "node_modules/typescript/bin/tsc",
    "lib/sse.ts",
    "--module", "esnext",
    "--target", "es2021",
    "--moduleResolution", "bundler",
    "--outDir", dir,
  ],
  { stdio: "inherit" },
);
const { consumeSSE, parseSSEFrame } = await import(join(dir, "sse.js"));

const CR = "\r";
const LF = "\n";
const CRLF = CR + LF;
const SEP = CRLF + CRLF; // server frame separator

// Build the exact wire format the server emits (CRLF + keepalive comment line).
const stream =
  "event: meta" + CRLF + 'data: {"type":"meta","route":"fast"}' + SEP +
  ": ping - 2026-01-01" + SEP +
  "event: token" + CRLF + 'data: {"type":"token","text":"Hi"}' + SEP;

let passed = 0;
const t = (name, fn) => {
  fn();
  passed++;
  console.log("  ok", name);
};

t("consumeSSE splits CRLF frames and skips keepalive comments", () => {
  const { events, rest } = consumeSSE(stream);
  assert.equal(events.length, 2, "should parse meta + token (0 was the old CRLF bug)");
  assert.equal(events[0].type, "meta");
  assert.equal(events[1].type, "token");
  assert.equal(events[1].text, "Hi");
  assert.equal(rest, "");
});

t("consumeSSE keeps a trailing incomplete frame in rest", () => {
  const partial = "event: token" + CRLF + 'data: {"type":"token","text":"par';
  const { events, rest } = consumeSSE(stream + partial);
  assert.equal(events.length, 2);
  assert.ok(rest.includes("par"));
});

t("parseSSEFrame handles a single CRLF frame", () => {
  const ev = parseSSEFrame('data: {"type":"final","answer":"Paris"}' + CR);
  assert.equal(ev.type, "final");
  assert.equal(ev.answer, "Paris");
});

t("parseSSEFrame returns null for comment/blank frames", () => {
  assert.equal(parseSSEFrame(": ping" + CR), null);
  assert.equal(parseSSEFrame(""), null);
});

t("LF-only frames still parse", () => {
  const lf =
    'data: {"type":"token","text":"x"}' + LF + LF +
    'data: {"type":"token","text":"y"}' + LF + LF;
  const { events } = consumeSSE(lf);
  assert.equal(events.length, 2);
});

console.log("\nSSE parser: " + passed + " tests passed");
