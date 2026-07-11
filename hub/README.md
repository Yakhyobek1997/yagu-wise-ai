# Hub artifact templates

Templates for optional Hugging Face Hub artifacts you *might* publish
alongside Auralynq — a model/adapter card, a dataset card, a Space README, a
paper card, and a checklist for launching a demo Space.

**Nothing here is uploaded automatically.** These are fill-in-the-blank
templates. Publishing anything to the Hub is a manual, explicit action you
take in your own account, and every template has placeholders (`<...>`) you
must replace with real values — do not publish a card with placeholders or
invented numbers still in it.

| File | Use when you're publishing… |
|---|---|
| [`model-card-template.md`](model-card-template.md) | a fine-tuned model or a LoRA/QLoRA adapter trained with/for Auralynq |
| [`dataset-card-template.md`](dataset-card-template.md) | a dataset (e.g. a RAG eval set, or a grounded-document corpus) |
| [`space-readme-template.md`](space-readme-template.md) | a Hugging Face Space running Auralynq (see also `deploy/huggingface/`) |
| [`paper-card-template.md`](paper-card-template.md) | a paper page / "Papers with Code"-style summary of an Auralynq contribution |
| [`demo-space-checklist.md`](demo-space-checklist.md) | pre-launch checks before making a public demo Space live |

## Ground rules for every card

- **No fabricated numbers.** Every metric must come from a real run
  (`make eval` / `make bench` / `make bench-*`, or an actual training run),
  with the report's provenance (commit + hardware + dataset) available. See
  `docs/benchmarks.md`.
- **No unsupported novelty claims.** "State of the art" requires a benchmark
  against a published baseline on a shared dataset; if you don't have that,
  don't write it (see `docs/research/research-contributions.md` for the
  wording Auralynq uses).
- **Honest limitations.** Every card has a limitations section — fill it in
  truthfully, don't leave it as boilerplate.
- **Privacy.** Don't publish a dataset or Space that includes private,
  personal, or copyrighted third-party material without a license that
  allows redistribution.
