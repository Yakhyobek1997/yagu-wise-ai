# ModelFit Index — Related Work

## 1. Model Distribution and Discovery

### Ollama Model Library
- **What it does**: Lists available models with tag, size, and pull command.
- **Strengths**: Clean UX; one-command model pull; supports quantized GGUF.
- **Gaps**: No VRAM estimation before pull; no RAG-specific quality signal; no task-fit scoring; no hardware profiler; no benchmark data per model.

### Hugging Face Model Hub
- **What it does**: Hosts model cards, weights, and community benchmarks; model cards include some hardware requirements.
- **Strengths**: Huge catalog; community evaluation results; Open LLM Leaderboard.
- **Gaps**: Hardware requirements are self-reported and often missing; no VRAM estimator; leaderboard benchmarks are academic, not RAG-specific; no local hardware profiler; quantization metadata inconsistent across cards.

### LM Studio
- **What it does**: Desktop app for local model management with hardware-aware model recommendations.
- **Strengths**: Hardware detection; VRAM-aware model filtering; GGUF quantization selection.
- **Gaps**: Closed-source; no RAG evaluation; no adapter support; no citation-level quality metrics; no community benchmark index; Windows/Mac only.

### Open WebUI
- **What it does**: Web interface for Ollama/OpenAI-compatible APIs with model management.
- **Strengths**: Usable model switcher; integrates with Ollama; supports multiple backends.
- **Gaps**: No hardware profiler; no VRAM estimation; no RAG quality metrics; no benchmark runner.

### LocalAI
- **What it does**: Local OpenAI-compatible API server for various model backends.
- **Strengths**: Wide backend support (llama.cpp, whisper, stable diffusion); configurable.
- **Gaps**: No model selection guidance; no VRAM estimator; no RAG quality scores; no hardware profiler.

---

## 2. Inference Engines and Quantization Ecosystems

### llama.cpp / GGUF
- **What it does**: Efficient CPU/GPU inference with multiple quantization levels (q2–fp16).
- **Strengths**: Fastest local CPU inference; broad quantization support; widely deployed.
- **Gaps**: No automatic quantization recommendation; no hardware profiler integration; no RAG evaluation.

### ExLlamaV2 / GPTQ
- **What it does**: GPU-optimised quantized inference (GPTQ, EXL2 formats).
- **Strengths**: Very fast on NVIDIA GPUs; high quality at lower bit widths.
- **Gaps**: NVIDIA-only; no hardware-aware recommendation; no RAG quality metrics.

### AWQ (Activation-aware Weight Quantization)
- **What it does**: Quantization that preserves activations for better quality at low bits.
- **Strengths**: High quality at 4-bit; widely available on HF Hub.
- **Gaps**: No hardware fit estimation; no RAG evaluation framework.

### Unsloth
- **What it does**: Efficient fine-tuning and GGUF export for local models.
- **Strengths**: Fast LoRA/QLoRA training; GGUF export; very low VRAM requirements for training.
- **Gaps**: Training-focused, not inference-selection-focused; no RAG quality signals.

### Hugging Face Optimum
- **What it does**: Model optimisation for inference (ONNX, TensorRT, GPTQ).
- **Strengths**: Wide framework support; hardware-targeted optimisation.
- **Gaps**: No end-user hardware profiler; no RAG evaluation; no local model recommendation UI.

---

## 3. Benchmark Leaderboards

### Open LLM Leaderboard (HF)
- **What it does**: Ranks models on academic benchmarks (MMLU, ARC, HellaSwag, TruthfulQA, GSM8k, BBH).
- **Strengths**: Standardised; community-contributed; broad model coverage.
- **Gaps**: Academic benchmarks ≠ RAG performance; no hardware fit; no VRAM/RAM info; no citation faithfulness; no abstention test; no local deployment guide.

### MTEB (Massive Text Embedding Benchmark)
- **What it does**: Ranks embedding models on retrieval, classification, clustering, STS tasks.
- **Strengths**: Gold standard for embedding quality; multilingual coverage.
- **Gaps**: No local hardware fit; no VRAM requirements; no RAG pipeline integration; no reranker comparison.

### RAGAS
- **What it does**: Framework for RAG evaluation (faithfulness, answer relevance, context recall).
- **Strengths**: RAG-specific metrics; integrates with LangChain/LlamaIndex.
- **Gaps**: Requires cloud LLM judge by default; no local hardware profiler; no model recommendation; no quantization support.

### LMSys Chatbot Arena
- **What it does**: Human preference ranking of LLM responses.
- **Strengths**: Real-user feedback; broad model coverage.
- **Gaps**: Cloud-only; no local deployment info; no RAG metrics; no hardware fit.

---

## 4. PEFT / QLoRA / Adapter Ecosystems

### PEFT (Hugging Face)
- **What it does**: Library for parameter-efficient fine-tuning (LoRA, QLoRA, prefix tuning).
- **Strengths**: Wide model support; memory-efficient; actively maintained.
- **Gaps**: No hardware-aware recommendation for inference after adaptation; no RAG quality evaluation of adapted models.

### QLoRA
- **What it does**: 4-bit quantized LoRA fine-tuning.
- **Strengths**: Fine-tunes 70B models on consumer GPUs; base for many local adapters.
- **Gaps**: Fine-tuning focused; no inference-time hardware guidance; no RAG quality metrics post-adaptation.

---

## 5. Local Model Hardware Guides

### Tom's Hardware / Reddit r/LocalLLaMA
- **What they do**: Community guides for running models on consumer hardware.
- **Strengths**: Real-world VRAM measurements; GPU comparison tables; community knowledge.
- **Gaps**: Not integrated into any platform; not reproducible; not RAG-specific; not searchable by hardware profile.

### TheBloke GGUF Collection (HF)
- **What it does**: Pre-quantized GGUF files with per-quantization VRAM estimates.
- **Strengths**: Practical VRAM tables; widely used; trusted community source.
- **Gaps**: Manual lookup required; not integrated with any RAG platform; no RAG quality metrics; not updated for all new models.

---

## 6. Visual Document QA Tools

### LLaVA / Llama 3.2 Vision
- **What they do**: Multimodal LLMs that accept image input.
- **Strengths**: Document image understanding; chart/table reading.
- **Gaps**: No hardware fit index for visual models; no RAG integration guide; no quality comparison for visual grounding.

---

## Key Observation

No existing tool jointly evaluates:
1. User hardware fit (VRAM/RAM feasibility)
2. Quantization recommendation
3. RAG quality (groundedness, citation faithfulness, abstention)
4. Latency and tok/s (measured, not fabricated)
5. Visual grounding support
6. Adapter compatibility
7. Local deployment ease (Ollama, GGUF, HF)

This gap is what **Auralynq ModelFit Index** fills.
