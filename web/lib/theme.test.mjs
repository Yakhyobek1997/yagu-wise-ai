// Dependency-free unit tests for the theme switcher logic (run: npm run test:theme).
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Compile theme.ts -> JS with the project's TypeScript, then import it.
const dir = mkdtempSync(join(tmpdir(), "theme-test-"));
execFileSync(
  "node",
  [
    "node_modules/typescript/bin/tsc",
    "lib/theme.ts",
    "--module", "esnext",
    "--target", "es2021",
    "--moduleResolution", "bundler",
    "--outDir", dir,
  ],
  { stdio: "inherit" },
);
const { THEME_ORDER, nextTheme, coerceTheme, isTheme } = await import(join(dir, "theme.js"));

let passed = 0;
const t = (name, fn) => {
  fn();
  passed++;
  console.log("  ok", name);
};

t("exposes the three modes in cycle order", () => {
  assert.deepEqual(THEME_ORDER, ["dark", "light", "comfort"]);
});

t("nextTheme cycles dark -> light -> comfort -> dark", () => {
  assert.equal(nextTheme("dark"), "light");
  assert.equal(nextTheme("light"), "comfort");
  assert.equal(nextTheme("comfort"), "dark");
});

t("isTheme validates membership", () => {
  assert.equal(isTheme("comfort"), true);
  assert.equal(isTheme("neon"), false);
  assert.equal(isTheme(null), false);
});

t("coerceTheme falls back to dark for garbage", () => {
  assert.equal(coerceTheme("light"), "light");
  assert.equal(coerceTheme("bogus"), "dark");
  assert.equal(coerceTheme(undefined), "dark");
});

console.log(`\nTheme switcher: ${passed} tests passed`);
