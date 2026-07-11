# Auralynq ModelFit Index

## Contribution Name

**Auralynq ModelFit Index**

Alternative names evaluated:
| Name | Evaluation |
|---|---|
| Auralynq Local Model Index | Descriptive but generic — does not capture the scoring/fit concept |
| Auralynq Hardware-Aware Model Router | Accurate for the routing component but too narrow |
| Auralynq Model Fitness Score | Good but "Fitness" sounds biological |
| Auralynq LocalFit | Too terse; may imply fitness/exercise |
| Auralynq RAGFit | Clear for RAG users but omits embedding/adapter dimension |
| Auralynq ModelFit-RAG | Redundant with project name |
| Auralynq HardwareFit | Emphasises hardware too much; ignores task/quality dimension |
| Auralynq Deployment-Aware RAG | Verbose; deployment is a consequence, not the primary concept |

**Selected name: Auralynq ModelFit Index**

Rationale: "ModelFit" is compact, memorable, and accurately names the core idea — fitting a model to hardware, task, and quality constraints. "Index" signals that this is a reproducible, comparable, structured metric, not a subjective review.

---

## What Is the Auralynq ModelFit Index?

The **Auralynq ModelFit Index** is a hardware-aware model selection and benchmarking system for local-first RAG. It estimates and measures whether a given local model, quantization level, adapter, embedding model, reranker, and RAG strategy can run efficiently on the user's actual hardware.

Unlike static leaderboards that rank models by benchmark accuracy alone, ModelFit jointly evaluates:

- **Hardware feasibility** — does the model fit in available VRAM or RAM?
- **Quantization selection** — which quantization level gives the best quality/size tradeoff on this machine?
- **Speed** — estimated and measured tok/s and latency
- **RAG quality** — citation coverage, groundedness, hallucination risk, abstention behaviour
- **Task alignment** — coding, summarization, document QA, agents, vision, multilingual
- **Deployment ease** — license, local availability, adapter compatibility

---

## Why It Matters

When users explore local LLMs for RAG, they face a fragmented research process:

1. They find a model on Hugging Face or Ollama.
2. They check parameter count and guess VRAM needs.
3. They load the model, run out of VRAM, try a lower quantization, reload.
4. They test quality manually with no reproducible RAG metrics.
5. They repeat for every model they want to compare.

Auralynq ModelFit Index solves this inside the platform:

- **Automated hardware detection** — no manual GPU/RAM lookup required.
- **Instant fit estimation** — see whether a model fits before pulling it.
- **Explicit benchmark runner** — reproducible, user-triggered benchmarks.
- **Clear separation of estimates vs. measurements** — no fabricated numbers.
- **RAG-specific quality signals** — not just perplexity or generic benchmarks.
- **Community-contributed data** — share and compare benchmark results with full hardware metadata.

---

## Scope

ModelFit covers:

| Component | Support |
|---|---|
| Local LLM selection | ✓ Ollama, HF GGUF, llama.cpp |
| Embedding model selection | ✓ nomic-embed, BGE, mxbai |
| Reranker selection | ✓ BGE reranker, Jina reranker |
| Quantization recommendation | ✓ q2–fp16, GGUF ecosystem |
| VRAM/RAM estimation | ✓ Formula-based, clearly labelled as estimates |
| tok/s measurement | ✓ Explicit benchmark only — never fabricated |
| Latency measurement | ✓ p50/p95/TTFT from benchmark runner |
| RAG quality comparison | ✓ Groundedness, citation, abstention |
| Adapter compatibility | ✓ PEFT/QLoRA/LoRA model notes |
| Visual grounding support | ✓ Vision model detection |
| Auralynq-RAG strategy recommendation | ✓ Integrated into query response |

---

## Principles

1. **Never fabricate benchmark numbers.** Estimates are labelled `is_estimate: true`. Only benchmark runner output sets `is_measured: true`.
2. **Never download models automatically.** ModelFit reads installed models; pulling requires explicit user action.
3. **Never claim performance without measurement.** Speed estimates are clearly heuristic.
4. **No paid APIs required.** Everything runs locally.
5. **No private hardware telemetry.** Hardware profiler collects only what is needed for fit estimation.
6. **Reproducible.** Every benchmark includes full hardware metadata and benchmark version.
7. **Community-contributed results are marked unverified** until validated.

---

## Research Connection

Auralynq ModelFit Index extends the Auralynq-RAG research contribution by adding a third dimension to local-first RAG evaluation:

- **Auralynq-RAG** answers: which RAG strategy + retrieval method produces the best answer?
- **Auralynq-CALoRA-RAG** answers: which adapter configuration improves domain performance?
- **Auralynq ModelFit Index** answers: which model + quantization + hardware combination makes both of the above feasible?

This forms a complete local-first RAG system: *strategy selection → model selection → adapter selection → hardware fit*.

---

## Citation Draft

> We introduce **Auralynq ModelFit Index**, a hardware-aware benchmarking and recommendation layer for local-first RAG systems. Unlike static leaderboards, ModelFit jointly considers hardware feasibility, quantization, latency, RAG groundedness, citation faithfulness, abstention behaviour, and adapter compatibility in a single reproducible workflow. ModelFit enables users to select the optimal local model stack for their specific hardware and task without fabricating benchmark numbers or requiring cloud inference.
