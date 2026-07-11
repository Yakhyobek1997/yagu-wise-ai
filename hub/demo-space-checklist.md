# Demo Space launch checklist

Run through this before making a public Hugging Face Space live. See
[`deploy/huggingface/`](https://github.com/MHHamdan/Auralynq/tree/main/deploy/huggingface)
for the image, entrypoint, and env reference this assumes.

## Build & smoke test locally first

- [ ] `podman build -f deploy/huggingface/Dockerfile -t auralynq-space .` succeeds
- [ ] `podman run --rm -p 7860:7860 auralynq-space` starts and stays up
- [ ] `curl -sf http://localhost:7860/api/health` → 200
- [ ] `curl -sf http://localhost:7860/api/status` shows `demo_mode: true`
- [ ] Landing page loads at `http://localhost:7860`
- [ ] A demo question returns a grounded, cited answer
- [ ] Clicking a citation opens the Source Workspace with a real highlight

## Safety & privacy defaults

- [ ] `AURALYNQ_ALLOW_UPLOADS=false` (unless you've read the persistence/privacy
      note and *intend* public uploads)
- [ ] No secrets baked into the image or set as **Variables** — keys go in
      **Secrets** only
- [ ] `AURALYNQ_SERVE__API_KEY` is a Secret if the API is reachable directly
- [ ] Only the safe offline defaults are on by default
      (`memory` vector store, `hash` embeddings, `extractive` LLM)
- [ ] No private/copyrighted documents in the seeded corpus — the shipped
      demo corpus is original + CC0 (`examples/demo_corpus/`)

## Storage expectations

- [ ] Persistent storage attached? If **no**, the Space README says storage is
      ephemeral and resets on restart
- [ ] If persistent storage **is** attached, confirmed the non-root container
      user (uid 10001) can write to the mount (see the ownership caveat in
      `deploy/huggingface/README.md`)

## Space metadata & docs

- [ ] README front-matter copied from `space-config.example.yaml` /
      `README_SPACE_TEMPLATE.md` (correct `sdk: docker`, `app_port: 7860`)
- [ ] README states: what the demo does, what data is stored, how to
      duplicate, Variables vs. Secrets, hardware, limitations
- [ ] No placeholder text or invented numbers left in the README
- [ ] License stated (Apache-2.0 code; demo-data license separately)

## Post-launch

- [ ] Duplicated the Space once and confirmed Variables carried over but
      Secrets did not (as expected)
- [ ] Confirmed CPU-basic hardware is enough (no GPU required for the demo)
- [ ] Nothing was auto-published — this was a deliberate manual launch
