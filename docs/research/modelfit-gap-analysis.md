# ModelFit Index — Gap Analysis

## Framing the Gap

Existing tools for local model selection fail RAG practitioners in five ways:

### Gap 1: Hardware Fit Is Not Automated

Most tools require the user to manually look up VRAM requirements, compare to their GPU spec, and guess whether a model will fit. This:
- Wastes time (download a model → OOM → try again).
- Is error-prone (VRAM estimates online are often for different quantizations or outdated).
- Is impossible without knowing quantization overhead, KV cache cost, and framework overhead.

**ModelFit solution**: Hardware profiler probes CPU/GPU/VRAM/RAM locally. VRAM estimator computes fit before any download. Quantization recommender selects the best level for available hardware.

---

### Gap 2: Quantization Selection Is Unexplained

Users face an alphabet soup of quantizations: q4_0, q4_k, q5_k_m, q8_0, gguf, gptq, awq, exl2. No existing tool explains:
- What quality difference each level produces.
- Which level fits a given GPU.
- Whether KV cache overhead at long contexts will push them over the limit.

**ModelFit solution**: Explicit quantization estimator with fit levels (comfortable / tight / not_recommended / impossible). All estimates clearly labelled. Benchmark runner measures actual quality at each level.

---

### Gap 3: RAG Quality Is Not Measured for Local Models

Leaderboards (Open LLM, MTEB, Chatbot Arena) measure:
- Academic reasoning (MMLU, ARC, GSM8k)
- Embedding retrieval (MTEB)
- Human preference (Arena)

None measure:
- Citation faithfulness (does the model cite the actual retrieved passage?)
- Groundedness (is the answer supported by retrieved context?)
- Abstention accuracy (does the model correctly say "I don't know"?)
- Evidence coverage (are all relevant retrieved passages used?)

**ModelFit solution**: RAG-specific benchmark tasks (citation, groundedness, abstention). These use local documents and local models — no cloud judge required.

---

### Gap 4: Speed Data Is Unreliable or Fabricated

Online tok/s reports suffer from:
- Different hardware (A100 vs. RTX 3090 vs. M2 Pro).
- Different quantizations.
- Different prompt/generation lengths.
- Batch vs. single-request.
- Framework differences (llama.cpp vs. vLLM vs. Ollama).

**ModelFit solution**: Benchmarks run locally and produce hardware-attached results. Estimates are clearly labelled `is_estimate: true`. Measured results from benchmark runner are labelled `is_measured: true`. Community results are labelled with `verified_status`.

---

### Gap 5: Adapter Compatibility Is Undocumented for Inference

PEFT/QLoRA documentation focuses on training setup. For inference:
- Which quantized models accept LoRA adapters?
- Can a GGUF model load a LoRA adapter?
- Does an Ollama model support adapter merging?

No tool answers these in the context of RAG deployment.

**ModelFit solution**: `supports_adapters` flag in model metadata. Notes field captures adapter compatibility caveats.

---

## Summary Table

| Gap | Existing coverage | ModelFit coverage |
|---|---|---|
| Automated hardware profiling | None (LM Studio partial) | ✓ Full local probe |
| VRAM estimation before download | None (manual TheBloke tables) | ✓ Formula-based estimator |
| Quantization recommendation | None | ✓ Fit-aware recommender |
| KV cache overhead estimation | None | ✓ Context-length-aware |
| RAG groundedness measurement | None locally | ✓ Local benchmark |
| Citation faithfulness | None locally | ✓ Local benchmark |
| Abstention accuracy | None | ✓ Local benchmark |
| Measured tok/s (not fabricated) | Community posts, unreproducible | ✓ Local benchmark with hardware metadata |
| Adapter compatibility info | HF cards (inconsistent) | ✓ Registry metadata field |
| Visual grounding model support | None indexed | ✓ Vision model detection |
| Community benchmark index | None structured | ✓ Validated JSON schema |
| RAG strategy ↔ model integration | None | ✓ ModelFit in query response |

---

## Who Benefits

| User type | Pain point addressed |
|---|---|
| Consumer GPU user (8–16 GB VRAM) | Knows which models actually fit before pulling |
| RAG practitioner | Knows which model produces grounded citations |
| Research contributor | Can reproduce and share benchmark results |
| Adapter fine-tuner | Knows which base models accept their adapter |
| Visual document QA user | Knows which models support image grounding |
| Multilingual RAG user | Knows which models handle non-English documents |
