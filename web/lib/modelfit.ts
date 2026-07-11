/**
 * Auralynq ModelFit Index — API client
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export interface GPUInfo {
  vendor: string;
  name: string;
  vram_gb: number;
  backend: string;
  device_index: number;
  vram_free_gb?: number | null;
  vram_used_gb?: number | null;
  integrated?: boolean;
}

export interface HardwareProfile {
  os: { name: string; version: string };
  python_version: string;
  cpu: {
    model: string;
    cores_physical: number;
    cores_logical: number;
    arch?: string;
    avx2?: boolean;
    avx512?: boolean;
  };
  ram_gb: number;
  gpus: GPUInfo[];
  total_vram_gb: number;
  total_vram_free_gb?: number | null;
  disk_free_gb: number;
  best_backend: string;
  cuda_available: boolean;
  cuda_version: string | null;
  metal_available: boolean;
  rocm_available: boolean;
  avx2?: boolean;
  avx512?: boolean;
  ollama_available: boolean;
  ollama_version: string | null;
  hf_available: boolean;
  hf_cache_path: string | null;
  in_container: boolean;
  warnings: string[];
}

/** UI-facing verdict from the resource estimator (see resource_estimator.py). */
export type Verdict =
  | "runs_great"
  | "runs_ok"
  | "runs_offload"
  | "runs_cpu"
  | "runs_cpu_tight"
  | "too_big";

export interface ModelMeta {
  model_id: string;
  source: string;
  display_name: string;
  family: string;
  parameter_count_b: number | null;
  context_length: number | null;
  license: string;
  gated: boolean;
  tasks: string[];
  available_quantizations: string[];
  embedding: boolean;
  reranker: boolean;
  supports_adapters: boolean;
  vision: boolean;
  tool_calling: boolean;
  multilingual: boolean;
  ollama_tag: string | null;
  hf_repo: string | null;
  local_path: string | null;
  notes: string[];
}

export interface ResourceEstimate {
  model_id: string;
  quantization: string;
  context_tokens: number;
  estimated_vram_gb: number;
  estimated_ram_gb: number;
  estimated_disk_gb: number;
  fit_level: "comfortable" | "tight" | "not_recommended" | "impossible";
  fits: boolean;
  recommended_context: number;
  peak_vram_at_max_ctx_gb: number;
  verdict?: Verdict;
  fits_in_vram?: boolean;
  requires_cpu_offload?: boolean;
  headroom_gb?: number;
  vram_free_gb?: number | null;
  warnings: string[];
  is_estimate: true;
}

export interface ModelFitScore {
  model_id: string;
  overall_score: number;
  hardware_fit: number;
  speed_fit: number;
  rag_fit: number;
  task_fit: number;
  deployment_fit: number;
  label: string;
  best_quantization: string;
  reason: string;
  resource_estimate: ResourceEstimate | null;
  benchmark: BenchmarkResult | null;
  estimate_used: boolean;
  warnings: string[];
}

export interface BenchmarkPlan {
  model_id: string;
  quantization: string;
  task: string;
  num_examples: number;
  estimated_duration_min: number;
  sample_prompts: string[];
  requires_ollama: boolean;
  requires_model_download: false;
  warnings: string[];
  note: string;
}

export interface BenchmarkResult {
  run_id: string;
  model_id: string;
  quantization: string;
  task: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  hardware: Partial<HardwareProfile>;
  avg_tok_per_sec: number | null;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  time_to_first_token_ms: number | null;
  peak_memory_gb: number | null;
  num_examples: number;
  completed_examples: number;
  rag_metrics: {
    citation_coverage: number | null;
    groundedness: number | null;
    abstention_accuracy: number | null;
  };
  error: string | null;
  started_at: string;
  completed_at: string | null;
  warnings: string[];
  is_measured: boolean;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${path} → ${res.status}: ${body}`);
  }
  return res.json();
}

// Hardware
export async function fetchHardware(): Promise<HardwareProfile> {
  return apiFetch("/api/modelfit/hardware");
}

// Models
export async function fetchModels(params?: {
  source?: string;
  family?: string;
  task?: string;
  embedding_only?: boolean;
  open_license?: boolean;
  q?: string;
  limit?: number;
}): Promise<{ models: ModelMeta[]; total: number }> {
  const qs = new URLSearchParams();
  if (params?.source) qs.set("source", params.source);
  if (params?.family) qs.set("family", params.family);
  if (params?.task) qs.set("task", params.task);
  if (params?.embedding_only) qs.set("embedding_only", "true");
  if (params?.open_license) qs.set("open_license", "true");
  if (params?.q) qs.set("q", params.q);
  if (params?.limit) qs.set("limit", String(params.limit));
  return apiFetch(`/api/modelfit/models?${qs}`);
}

export async function fetchInstalledModels(): Promise<{ models: ModelMeta[]; total: number; warnings: string[] }> {
  return apiFetch("/api/modelfit/models/installed");
}

// Estimate
export async function fetchEstimate(
  model_id: string,
  params_b: number,
  quantization: string,
  context_tokens = 4096,
): Promise<ResourceEstimate> {
  return apiFetch("/api/modelfit/estimate", {
    method: "POST",
    body: JSON.stringify({ model_id, params_b, quantization, context_tokens }),
  });
}

// Score
export async function fetchScore(
  model_id: string,
  quantization?: string,
  requested_tasks?: string[],
): Promise<ModelFitScore> {
  return apiFetch("/api/modelfit/score", {
    method: "POST",
    body: JSON.stringify({ model_id, quantization, requested_tasks: requested_tasks ?? [] }),
  });
}

// Recommendations
export async function fetchRecommendations(task?: string, limit = 5): Promise<{
  recommendations: ModelFitScore[];
  hardware_summary: { ram_gb: number; total_vram_gb: number; best_backend: string };
  task: string | null;
}> {
  const qs = new URLSearchParams();
  if (task) qs.set("task", task);
  qs.set("limit", String(limit));
  return apiFetch(`/api/modelfit/recommendations?${qs}`);
}

// Benchmark
export async function fetchBenchmarkPreview(
  model_id: string,
  quantization: string,
  task: string,
  num_examples: number,
): Promise<BenchmarkPlan> {
  return apiFetch("/api/modelfit/benchmark/preview", {
    method: "POST",
    body: JSON.stringify({ model_id, quantization, task, num_examples, confirmed: false }),
  });
}

export async function runBenchmark(
  model_id: string,
  quantization: string,
  task: string,
  num_examples: number,
): Promise<BenchmarkResult> {
  return apiFetch("/api/modelfit/benchmark/run", {
    method: "POST",
    body: JSON.stringify({ model_id, quantization, task, num_examples, confirmed: true }),
  });
}

export async function fetchBenchmarkRuns(): Promise<{ runs: BenchmarkResult[]; total: number }> {
  return apiFetch("/api/modelfit/benchmark/runs");
}

export async function fetchBenchmarkRun(run_id: string): Promise<BenchmarkResult> {
  return apiFetch(`/api/modelfit/benchmark/${run_id}`);
}

// ── Discover & Setup ──────────────────────────────────────────────────────────

export interface DiscoverHardware {
  os: string;
  cpu: string;
  cpu_cores_physical?: number;
  cpu_cores_logical?: number;
  arch?: string;
  avx2?: boolean;
  avx512?: boolean;
  ram_gb: number;
  total_vram_gb: number;
  total_vram_free_gb?: number | null;
  gpus: GPUInfo[];
  best_backend: string;
  ollama_available: boolean;
  in_container?: boolean;
}

export interface DiscoverEntry {
  model_id: string;
  overall_score: number;
  hardware_fit: number;
  speed_fit: number;
  rag_fit: number;
  task_fit: number;
  deployment_fit: number;
  label: string;
  best_quantization: string;
  reason: string;
  resource_estimate: ResourceEstimate | null;
  benchmark: BenchmarkResult | null;
  estimate_used: boolean;
  warnings: string[];
  model_meta: ModelMeta;
  already_installed: boolean;
  pull_command: string | null;
  source: string;
}

export interface DiscoverResult {
  hardware: DiscoverHardware;
  task: string | null;
  total_candidates: number;
  recommendations: DiscoverEntry[];
  note: string;
}

export interface PullResult {
  status: string;
  model_id: string;
  message: string;
  local_path?: string;
}

export async function discoverModels(
  task: string | null,
  includeHf: boolean,
  refresh: boolean,
  limit = 30,
): Promise<DiscoverResult> {
  return apiFetch("/api/modelfit/discover", {
    method: "POST",
    body: JSON.stringify({ task, include_hf: includeHf, refresh, limit }),
  });
}

export async function pullModel(modelId: string): Promise<PullResult> {
  return apiFetch("/api/modelfit/pull", {
    method: "POST",
    body: JSON.stringify({ model_id: modelId, confirmed: true }),
  });
}
