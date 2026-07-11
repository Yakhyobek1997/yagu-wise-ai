---
# Hugging Face model-card metadata. Replace every <placeholder>; delete lines
# you can't fill honestly rather than guessing.
license: <spdx-id, e.g. apache-2.0>            # MUST match the base model's license terms
base_model: <org/base-model>                    # e.g. meta-llama/Llama-3.1-8B-Instruct
library_name: peft                              # for a LoRA/QLoRA adapter; omit for a full model
tags:
  - auralynq
  - rag
  - retrieval-augmented-generation
  # - lora   / - qlora   (if an adapter)
language:
  - <en, ...>
---

# <Model / Adapter name>

<One-paragraph description: what this is, whether it's a full fine-tune or a
LoRA/QLoRA adapter, and what it's for within Auralynq.>

- **Type:** <full fine-tune | LoRA adapter | QLoRA adapter>
- **Base model:** `<org/base-model>`
- **Trained by:** <you / org>
- **License:** <spdx-id> — note any inherited restrictions from the base model.

## Intended use

<What the model is meant to do: e.g. citation-faithful RAG answering,
abstention on insufficient evidence, grounding-aware generation. Name the
Auralynq strategy/config it's meant to be used with.>

**Out of scope / not intended for:** <e.g. use without retrieval; standalone
open-domain QA; any high-stakes decision without human review.>

## Training data

- **Source:** <dataset name(s) + link; note license and whether it's
  redistributable>
- **Size:** <n examples / tokens>
- **Preprocessing:** <chunking, grounding metadata, citation/abstention
  labels — whatever applies>

> If any training data is private or non-redistributable, say so explicitly
> and do **not** ship the data with this card.

## Training procedure

- **Method:** <LoRA rank/alpha, QLoRA quant, full FT, etc.>
- **Hardware:** <GPU model(s), VRAM, count>
- **Framework:** <peft / trl / axolotl / … + version>
- **Key hyperparameters:** <lr, epochs, batch size, seq len>

## Evaluation

> Fill this **only** with numbers from a real run. For Auralynq's own
> metrics, generate them with `make bench-rag` (groundedness, citation
> coverage, abstention accuracy) and quote the report's provenance block
> (commit + hardware + dataset). Delete any row you didn't actually measure.

| Metric | Value | How measured | Provenance |
|---|---|---|---|
| Groundedness | <x.xx> | `make bench-rag` | commit `<sha>`, `<hardware>` |
| Citation coverage | <x.xx> | `make bench-rag` | commit `<sha>`, `<hardware>` |
| Abstention accuracy | <x.xx> | `make bench-rag` | commit `<sha>`, `<hardware>` |
| <other> | <...> | <...> | <...> |

**Estimated vs. measured:** state clearly which numbers are measured vs.
estimated. Auralynq never presents an estimate as a measurement.

## Hardware & quantization for inference

- **Recommended quantization:** <e.g. q4_k>
- **Approx. VRAM:** <x.x GB> — mark whether this is estimated or measured.
- Cross-reference: `auralynq-modelfit score --model <...>` for a
  hardware-fit estimate.

## Limitations & risks

<Be specific and honest: known failure modes, domains it wasn't trained on,
hallucination/abstention behavior, any bias in the training data.>

## Ethical & privacy notes

<Data provenance/consent, any PII handling, redistribution constraints,
intended-vs-foreseeable-misuse notes.>

## Citation

```bibtex
@misc{<key>,
  title  = {<Model name>},
  author = {<you>},
  year   = {<year>},
  howpublished = {\url{https://huggingface.co/<org>/<model>}}
}
```
