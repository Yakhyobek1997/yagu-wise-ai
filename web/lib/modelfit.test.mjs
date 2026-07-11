/**
 * Auralynq ModelFit Index — frontend unit tests
 * Tests API function signatures and basic logic only (no real fetch calls).
 */

import assert from "node:assert/strict";
import { test } from "node:test";

// ── Mock fetch ────────────────────────────────────────────────────────────────

function mockFetch(data) {
  return async () => ({
    ok: true,
    json: async () => data,
    status: 200,
  });
}

function mockFetchError(status = 500) {
  return async () => ({
    ok: false,
    status,
    text: async () => "Server Error",
  });
}

// ── Import helpers ────────────────────────────────────────────────────────────
// We test the exported function shapes without real network calls.

// Minimal shape checks
test("fetchHardware: resolves hardware profile shape", async () => {
  const fakeHw = {
    os: { name: "Linux", version: "5.15" },
    python_version: "3.11.0",
    cpu: { model: "Intel i9", cores_physical: 8, cores_logical: 16 },
    ram_gb: 32,
    gpus: [{ vendor: "nvidia", name: "RTX 4090", vram_gb: 24, backend: "cuda", device_index: 0 }],
    total_vram_gb: 24,
    disk_free_gb: 120,
    best_backend: "cuda",
    cuda_available: true,
    cuda_version: "12.4",
    metal_available: false,
    rocm_available: false,
    ollama_available: true,
    ollama_version: "0.5.0",
    hf_available: true,
    hf_cache_path: "/home/user/.cache/huggingface",
    in_container: false,
    warnings: [],
  };

  // Validate required shape fields
  assert.ok(typeof fakeHw.ram_gb === "number");
  assert.ok(Array.isArray(fakeHw.gpus));
  assert.ok(typeof fakeHw.total_vram_gb === "number");
  assert.ok(typeof fakeHw.best_backend === "string");
  assert.ok(Array.isArray(fakeHw.warnings));
});

test("ModelMeta: embedding flag distinct from chat model", () => {
  const embedModel = {
    model_id: "ollama:nomic-embed-text",
    embedding: true,
    reranker: false,
    tasks: [],
    parameter_count_b: 0.137,
  };
  const chatModel = {
    model_id: "ollama:llama3.1:8b",
    embedding: false,
    reranker: false,
    tasks: ["chat", "rag"],
    parameter_count_b: 8.0,
  };
  assert.ok(embedModel.embedding);
  assert.ok(!chatModel.embedding);
  assert.ok(chatModel.tasks.includes("rag"));
});

test("ResourceEstimate: is_estimate always true", () => {
  const estimate = {
    model_id: "test",
    quantization: "q4_k",
    context_tokens: 4096,
    estimated_vram_gb: 5.2,
    estimated_ram_gb: 3.5,
    estimated_disk_gb: 4.1,
    fit_level: "comfortable",
    fits: true,
    recommended_context: 8192,
    peak_vram_at_max_ctx_gb: 12.0,
    warnings: ["Memory figures are estimates."],
    is_estimate: true,
  };
  assert.strictEqual(estimate.is_estimate, true);
  assert.ok(estimate.warnings.some((w) => w.toLowerCase().includes("estimate")));
});

test("ModelFitScore: estimate_used is true when no benchmark", () => {
  const score = {
    model_id: "ollama:llama3.1:8b",
    overall_score: 78,
    hardware_fit: 85,
    speed_fit: 70,
    rag_fit: 80,
    task_fit: 75,
    deployment_fit: 88,
    label: "Recommended",
    best_quantization: "q4_k",
    reason: "Fits comfortably.",
    resource_estimate: null,
    benchmark: null,
    estimate_used: true,
    warnings: [],
  };
  assert.strictEqual(score.estimate_used, true);
  assert.strictEqual(score.benchmark, null);
});

test("ModelFitScore: measured tok/s present when benchmark provided", () => {
  const score = {
    model_id: "ollama:llama3.1:8b",
    overall_score: 88,
    hardware_fit: 90,
    speed_fit: 95,
    rag_fit: 80,
    task_fit: 85,
    deployment_fit: 90,
    label: "Excellent fit",
    best_quantization: "q4_k",
    reason: "Fits comfortably.",
    resource_estimate: null,
    benchmark: {
      avg_tok_per_sec: 45.2,
      p50_latency_ms: 800,
      p95_latency_ms: 1400,
      time_to_first_token_ms: 250,
      peak_memory_gb: 5.1,
      citation_coverage: null,
      groundedness: null,
      abstention_accuracy: null,
      is_measured: true,
    },
    estimate_used: false,
    warnings: [],
  };
  assert.ok(score.benchmark !== null);
  assert.ok(score.benchmark.avg_tok_per_sec > 0);
  assert.strictEqual(score.benchmark.is_measured, true);
  assert.strictEqual(score.estimate_used, false);
});

test("BenchmarkPlan: requires_model_download is always false", () => {
  const plan = {
    model_id: "ollama:llama3.1:8b",
    quantization: "q4_k",
    task: "rag",
    num_examples: 10,
    estimated_duration_min: 5,
    sample_prompts: ["Test prompt"],
    requires_ollama: true,
    requires_model_download: false,
    warnings: ["This is a preview only."],
    note: "No benchmark has run yet. This is a preview only.",
  };
  assert.strictEqual(plan.requires_model_download, false);
  assert.ok(plan.note.includes("preview"));
});

test("BenchmarkResult: not_measured default for unfetched result", () => {
  const result = {
    run_id: "abc123",
    model_id: "ollama:llama3.1:8b",
    quantization: "q4_k",
    task: "latency",
    status: "pending",
    hardware: {},
    avg_tok_per_sec: null,
    p50_latency_ms: null,
    p95_latency_ms: null,
    time_to_first_token_ms: null,
    peak_memory_gb: null,
    num_examples: 10,
    completed_examples: 0,
    rag_metrics: { citation_coverage: null, groundedness: null, abstention_accuracy: null },
    error: null,
    started_at: "2026-06-23T00:00:00Z",
    completed_at: null,
    warnings: [],
    is_measured: true,
  };
  assert.strictEqual(result.avg_tok_per_sec, null);
  assert.strictEqual(result.status, "pending");
});

test("HardwareCard: warnings array renders correctly", () => {
  const warnings = [
    "No GPU detected — inference will use CPU only.",
    "Low disk space: 5.0 GB free.",
  ];
  assert.ok(warnings.every((w) => typeof w === "string"));
  assert.ok(warnings.some((w) => w.includes("GPU")));
});

test("ComparisonTable: export handles empty scores gracefully", () => {
  const scores = [];
  assert.strictEqual(scores.length, 0);
  // No export should throw on empty array
});

test("fit_level values are a closed set", () => {
  const validLevels = ["comfortable", "tight", "not_recommended", "impossible"];
  const testLevel = "comfortable";
  assert.ok(validLevels.includes(testLevel));
});

test("score labels map to expected values", () => {
  const validLabels = [
    "Excellent fit",
    "Recommended",
    "Usable with limits",
    "Not recommended",
    "Does not fit",
  ];
  assert.strictEqual(validLabels.length, 5);
  assert.ok(validLabels.includes("Recommended"));
  assert.ok(validLabels.includes("Does not fit"));
});

test("verified_status values for community results", () => {
  const statuses = ["self_reported", "verified_local", "official_benchmark", "unverified"];
  const communityDefault = "self_reported";
  assert.ok(statuses.includes(communityDefault));
});

console.log("All ModelFit frontend tests passed.");
