# ModelFit Index — Competitor Audit

## Audit Methodology

This audit compares tools across seven dimensions relevant to Auralynq ModelFit Index:

| Dimension | What we check |
|---|---|
| H | Hardware profiling (CPU/GPU/VRAM auto-detection) |
| V | VRAM/RAM estimation before model load |
| Q | Quantization recommendation |
| R | RAG-specific quality metrics |
| S | Speed measurement (tok/s, latency) |
| A | Adapter/fine-tune compatibility tracking |
| C | Community benchmark contributions |

Rating: ✓ full support · ◑ partial · ✗ absent

---

## Tool-by-Tool Audit

### LM Studio
| H | V | Q | R | S | A | C |
|---|---|---|---|---|---|---|
| ◑ | ◑ | ◑ | ✗ | ✗ | ✗ | ✗ |

LM Studio shows a hardware summary and colour-codes models by fit (green/yellow/red) based on VRAM. It does not estimate KV cache overhead, does not evaluate RAG quality, has no benchmark runner, and does not track adapter compatibility. It is closed-source and limited to Mac/Windows.

**ModelFit advantage**: Open-source; RAG quality metrics; benchmark runner; adapter metadata; community index; Linux support; integrated with Auralynq-RAG strategy selection.

---

### Ollama CLI
| H | V | Q | R | S | A | C |
|---|---|---|---|---|---|---|
| ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

Ollama provides a model list and pull/run commands. No hardware profiling, no VRAM estimation, no benchmark runner, no RAG quality. It is the deployment runtime, not the selection tool.

**ModelFit advantage**: Everything above — ModelFit uses Ollama as the inference backend while adding the selection and benchmarking layer on top.

---

### Open WebUI
| H | V | Q | R | S | A | C |
|---|---|---|---|---|---|---|
| ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

Open WebUI is a chat interface for Ollama. Model management is limited to selecting installed models. No hardware profiling, no benchmarks, no RAG evaluation.

**ModelFit advantage**: Full hardware profiling; VRAM estimation; benchmark runner; RAG quality signals.

---

### text-generation-webui (oobabooga)
| H | V | Q | R | S | A | C |
|---|---|---|---|---|---|---|
| ◑ | ◑ | ✗ | ✗ | ◑ | ◑ | ✗ |

Supports LoRA adapter loading, GPTQ/AWQ/llama.cpp backends, and shows GPU memory usage. No VRAM pre-estimation, no RAG quality benchmarks, no community benchmark index.

**ModelFit advantage**: Pre-estimation (before load); RAG quality metrics; community index; integration with RAG pipeline.

---

### LocalAI
| H | V | Q | R | S | A | C |
|---|---|---|---|---|---|---|
| ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

LocalAI is an inference server. Excellent backend compatibility but no model selection guidance.

**ModelFit advantage**: Adds all selection, estimation, and evaluation capability on top.

---

### Hugging Face Hub Model Cards
| H | V | Q | R | S | A | C |
|---|---|---|---|---|---|---|
| ✗ | ◑ | ✗ | ◑ | ◑ | ◑ | ◑ |

Model cards sometimes include VRAM requirements and benchmark tables. Coverage is inconsistent: many cards omit quantization VRAM; benchmark numbers are self-reported and not reproduced; RAG metrics are rare; hardware context is usually missing.

**ModelFit advantage**: Automated; reproducible; hardware-attached; RAG-specific; community schema enforced.

---

### Open LLM Leaderboard
| H | V | Q | R | S | A | C |
|---|---|---|---|---|---|---|
| ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |

Standardised academic benchmarks with community model submissions. Strong for comparing raw reasoning ability. No hardware fit, no RAG quality, no speed data, no local deployment info.

**ModelFit advantage**: Hardware fit; quantization; RAG quality; local deployment; speed (measured not estimated).

---

### MTEB (Embedding Benchmark)
| H | V | Q | R | S | A | C |
|---|---|---|---|---|---|---|
| ✗ | ✗ | ✗ | ◑ | ✗ | ✗ | ✓ |

Gold standard for embedding quality comparison. No hardware fit, no local deployment info, no reranker integration with RAG pipeline.

**ModelFit advantage**: Local hardware fit for embedding models; RAG pipeline integration; reranker support.

---

### RAGAS Evaluation Framework
| H | V | Q | R | S | A | C |
|---|---|---|---|---|---|---|
| ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ |

Excellent RAG evaluation metrics. Requires cloud LLM judge by default. Not integrated with model selection or hardware profiling.

**ModelFit advantage**: Local evaluation (no cloud judge required); hardware profiling; model selection; benchmark runner.

---

### TheBloke GGUF VRAM Tables (Community)
| H | V | Q | R | S | A | C |
|---|---|---|---|---|---|---|
| ✗ | ◑ | ◑ | ✗ | ✗ | ✗ | ◑ |

Valuable community resource with per-quantization VRAM estimates for many models. Manual lookup, not machine-readable, not integrated with any platform, not updated for all new models.

**ModelFit advantage**: Automated; hardware-attached; platform-integrated; always current.

---

## Competitive Summary

| Tool | Best at | Missing vs. ModelFit |
|---|---|---|
| LM Studio | Consumer UX, model filtering | RAG quality, benchmark runner, open source |
| Ollama | Inference runtime | Everything selection/evaluation related |
| Open WebUI | Chat interface | Everything |
| text-generation-webui | Adapter loading, backend variety | Pre-estimation, RAG quality, community index |
| LocalAI | Backend compatibility | Everything selection/evaluation |
| HF Hub | Model catalog, community | Automation, RAG quality, hardware fit |
| Open LLM Leaderboard | Academic benchmarks | Hardware fit, RAG quality, local deployment |
| MTEB | Embedding quality | Hardware fit, RAG pipeline, local deployment |
| RAGAS | RAG evaluation framework | Local execution, hardware profiling, model selection |
| TheBloke VRAM tables | VRAM estimates | Automation, RAG quality, platform integration |

**Auralynq ModelFit Index occupies a unique position**: it is the only tool that integrates hardware profiling, quantization recommendation, RAG quality benchmarking, adapter compatibility, visual grounding detection, and community benchmark contributions in a single open-source platform component.
