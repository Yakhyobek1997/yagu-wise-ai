// Dependency-free unit tests for the proxy failover policy (run: npm run test:failover).
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Compile failover.ts -> JS with the bundled TypeScript compiler, then import it.
const dir = mkdtempSync(join(tmpdir(), "failover-test-"));
execFileSync(
  "node",
  [
    "node_modules/typescript/bin/tsc",
    "lib/failover.ts",
    "--module", "esnext",
    "--target", "es2021",
    "--moduleResolution", "bundler",
    "--outDir", dir,
  ],
  { stdio: "inherit" },
);
const { shouldFailover, resolveUpstreams, FAILOVER_STATUSES } = await import(join(dir, "failover.js"));

let passed = 0;
const t = (name, fn) => {
  fn();
  passed++;
  console.log("  ok", name);
};

t("shouldFailover only on gateway-class statuses", () => {
  for (const s of [502, 503, 504]) assert.equal(shouldFailover(s), true, `expected failover on ${s}`);
  for (const s of [200, 204, 400, 401, 404, 422, 500]) assert.equal(shouldFailover(s), false, `no failover on ${s}`);
  assert.equal(FAILOVER_STATUSES.size, 3);
});

t("no fallback configured -> single primary upstream (no buffering path)", () => {
  const u = resolveUpstreams("http://api:8000", "", false);
  assert.equal(u.length, 1);
  assert.equal(u[0].label, "primary");
  assert.equal(u[0].insecure, false);
});

t("fallback configured -> primary then fallback, trailing slashes trimmed", () => {
  const u = resolveUpstreams("http://localhost:8000/", "https://172.24.50.21:8443/api//", true);
  assert.equal(u.length, 2);
  assert.deepEqual(u.map((x) => x.label), ["primary", "fallback"]);
  assert.equal(u[0].base, "http://localhost:8000");
  assert.equal(u[1].base, "https://172.24.50.21:8443/api");
  assert.equal(u[1].insecure, true, "self-signed fallback must skip TLS verification");
});

t("fallback identical to primary is ignored", () => {
  const u = resolveUpstreams("http://api:8000", "http://api:8000/", false);
  assert.equal(u.length, 1);
});

console.log("\nFailover policy: " + passed + " tests passed");
