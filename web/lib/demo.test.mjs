// Structural guards for the demo/offline deployment banner (Part 8). Same
// dependency-free, source-level approach as ui.test.mjs — asserts the banner
// and its backing deploymentMode() helper compose the required states without
// needing a DOM or a running backend.
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

t("api.ts exposes typed status fields and a deploymentMode helper", () => {
  const api = read("lib/api.ts");
  has(api, "export interface StatusResponse");
  for (const f of ["hf_space", "demo_mode", "public_demo", "allow_uploads"]) {
    has(api, f, `StatusResponse missing field: ${f}`);
  }
  has(api, "export function deploymentMode");
  has(api, "export interface DeploymentMode");
});

t("deploymentMode detects the offline $0 fallback providers", () => {
  const api = read("lib/api.ts");
  // extractive LLM + hash embeddings are the two offline fallbacks (ADR-0003)
  has(api, '"extractive answering"');
  has(api, '"hash embeddings"');
  has(api, "offlineFallback");
  // uploads default to allowed when the backend omits the field
  has(api, "s?.allow_uploads === false");
});

t("DemoBanner composes every deployment-mode state", () => {
  const b = read("components/DemoBanner.tsx");
  has(b, "Running in demo mode");
  has(b, "offline fallback");
  has(b, "uploads are disabled");
  has(b, "Hugging Face Space");
  has(b, "ephemeral");
});

t("DemoBanner renders nothing for a normal private deployment", () => {
  const b = read("components/DemoBanner.tsx");
  // guard: returns null unless at least one mode flag is set
  has(b, "if (!show || dismissed) return null");
});

t("DemoBanner is dismissible and accessible", () => {
  const b = read("components/DemoBanner.tsx");
  has(b, 'role="status"');
  has(b, "aria-label");
  has(b, "Dismiss deployment notice");
  has(b, "sessionStorage");
  has(b, "focus-visible:outline");
});

t("chat page renders the DemoBanner wired to /status", () => {
  const page = read("app/chat/page.tsx");
  has(page, "<DemoBanner");
  has(page, "deploymentMode(s)");
  has(page, "setDeployMode");
});

console.log(`\n${passed} demo-banner structure tests passed`);
