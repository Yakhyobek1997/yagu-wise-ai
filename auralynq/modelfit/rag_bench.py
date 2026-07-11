"""RAG quality benchmark metrics for Auralynq ModelFit Index.

Measures groundedness, citation coverage, and abstention accuracy using
the local corpus. All evaluation is done locally — no cloud judge required.

Groundedness: fraction of answer sentences that can be traced to a retrieved passage.
Citation coverage: fraction of citations that reference actually-retrieved passages.
Abstention accuracy: fraction of unanswerable questions correctly refused.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from auralynq.telemetry import get_logger

_log = get_logger("auralynq.modelfit.rag_bench")

# Prompts used to test RAG groundedness
_RAG_TEST_PROMPTS = [
    "What are the main topics covered in the indexed documents?",
    "Summarize the key points from the available documents.",
    "What entities are mentioned most frequently in the corpus?",
    "Who or what is the primary subject of the indexed content?",
    "What conclusions can be drawn from the documents?",
]

_ABSTENTION_PROMPTS = [
    "What will the stock price of ACME Corp be tomorrow?",
    "Tell me the personal phone number of the CEO mentioned in the documents.",
    "What happened in the news today?",
    "Predict the next election result based on the documents.",
]

_ABSTENTION_MARKERS = (
    "don't have enough evidence",
    "do not have enough evidence",
    "not enough evidence",
    "no relevant evidence",
    "cannot answer",
    "i don't know",
    "i don't have information",
    "not found in",
    "unable to find",
)


@dataclass
class RAGBenchMetrics:
    groundedness: float | None = None
    citation_coverage: float | None = None
    abstention_accuracy: float | None = None
    num_rag_examples: int = 0
    num_abstention_examples: int = 0
    warnings: list[str] = field(default_factory=list)
    is_measured: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation_coverage": self.citation_coverage,
            "groundedness": self.groundedness,
            "abstention_accuracy": self.abstention_accuracy,
            "num_rag_examples": self.num_rag_examples,
            "num_abstention_examples": self.num_abstention_examples,
            "warnings": self.warnings,
            "is_measured": self.is_measured,
        }


def _simple_groundedness(answer: str, contexts: list[str]) -> float:
    """Estimate what fraction of answer content overlaps with retrieved context.

    Uses token-level overlap (not LLM judge) — fast, local, reproducible.
    Returns 0.0 when contexts is empty (signal that RAG had no retrieval).
    """
    if not contexts or not answer:
        return 0.0

    # Tokenize to word stems (very lightweight; no NLP deps required)
    def tokens(text: str) -> set[str]:
        return {w.lower().strip(".,;:!?\"'()[]") for w in text.split() if len(w) > 3}

    answer_toks = tokens(answer)
    if not answer_toks:
        return 0.0

    context_toks: set[str] = set()
    for c in contexts:
        context_toks |= tokens(c)

    overlap = answer_toks & context_toks
    return round(len(overlap) / len(answer_toks), 3)


def _citation_coverage_score(citations: list[dict[str, Any]], contexts: list[str]) -> float:
    """Fraction of citations referencing actually-retrieved sources."""
    if not citations:
        return 0.0
    if not contexts:
        return 0.0

    context_sources = {c.split("\n")[0][:80].lower() for c in contexts if c}
    covered = 0
    for cit in citations:
        src = str(cit.get("source", "")).lower()[:80]
        if any(src in cs or cs in src for cs in context_sources):
            covered += 1
    return round(covered / len(citations), 3) if citations else 0.0


def _is_abstention(answer: str) -> bool:
    low = answer.lower()
    return any(m in low for m in _ABSTENTION_MARKERS)


async def run_rag_benchmark(
    model_id: str,
    quantization: str = "q4_k",
    num_rag: int = 5,
    num_abstention: int = 4,
) -> RAGBenchMetrics:
    """Run RAG quality benchmark against local Ollama model using local corpus.

    Never downloads models. Requires Ollama to be running with the model installed.
    Uses the local corpus in the Auralynq vector store for retrieval.
    """
    warnings: list[str] = []
    metrics = RAGBenchMetrics(warnings=warnings)

    tag = model_id.removeprefix("ollama:")

    # Check Ollama availability
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get("http://localhost:11434/api/tags")
            if r.status_code != 200:
                warnings.append("Ollama not reachable — skipping RAG benchmark.")
                return metrics
    except Exception as e:
        warnings.append(f"Ollama not reachable: {e}")
        return metrics

    # Get retrieval results for test prompts using Auralynq's retriever
    groundedness_scores: list[float] = []
    citation_scores: list[float] = []

    rag_prompts = _RAG_TEST_PROMPTS[:num_rag]
    metrics.num_rag_examples = len(rag_prompts)

    try:
        from auralynq.retrieval.hybrid.retriever import HybridRetriever

        retriever = HybridRetriever()
    except Exception as e:
        warnings.append(f"Could not init retriever for RAG benchmark: {e}")
        retriever = None

    async with httpx.AsyncClient(timeout=60.0) as client:
        for prompt in rag_prompts:
            # Retrieve local context
            contexts: list[str] = []
            citations: list[dict[str, Any]] = []
            if retriever:
                try:
                    rr = retriever.retrieve(prompt, k=5)
                    contexts = [sc.chunk.text for sc in rr.chunks]
                    citations = [
                        {"source": sc.chunk.citation().get("source", "")} for sc in rr.chunks
                    ]
                except Exception:
                    pass

            ctx_block = "\n\n".join(f"[{i + 1}] {c[:400]}" for i, c in enumerate(contexts))
            system_prompt = (
                "You are a helpful assistant. Answer using only the provided context. "
                "If the context does not contain enough information, say so clearly."
            )
            user_msg = f"Context:\n{ctx_block}\n\nQuestion: {prompt}"

            try:
                resp = await client.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": tag,
                        "prompt": f"{system_prompt}\n\n{user_msg}",
                        "stream": False,
                        "options": {"num_predict": 300},
                    },
                    timeout=90.0,
                )
                if resp.status_code == 404:
                    warnings.append(f"Model '{tag}' not found in Ollama. Pull it first.")
                    return metrics
                data = resp.json()
                answer = data.get("response", "")
            except Exception as e:
                warnings.append(f"RAG prompt failed: {e}")
                continue

            g = _simple_groundedness(answer, contexts)
            groundedness_scores.append(g)
            cit_cov = _citation_coverage_score(citations, contexts)
            citation_scores.append(cit_cov)

    if groundedness_scores:
        metrics.groundedness = round(sum(groundedness_scores) / len(groundedness_scores), 3)
    if citation_scores:
        metrics.citation_coverage = round(sum(citation_scores) / len(citation_scores), 3)

    # Abstention test
    abstention_correct = 0
    abstention_prompts = _ABSTENTION_PROMPTS[:num_abstention]
    metrics.num_abstention_examples = len(abstention_prompts)

    async with httpx.AsyncClient(timeout=60.0) as client:
        for prompt in abstention_prompts:
            try:
                resp = await client.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": tag,
                        "prompt": (
                            "You only have access to the documents indexed in this system. "
                            "If you cannot find the answer in those documents, say clearly "
                            "that you don't have enough evidence to answer.\n\n"
                            f"Question: {prompt}"
                        ),
                        "stream": False,
                        "options": {"num_predict": 150},
                    },
                    timeout=60.0,
                )
                data = resp.json()
                answer = data.get("response", "")
                if _is_abstention(answer):
                    abstention_correct += 1
            except Exception:
                pass

    if abstention_prompts:
        metrics.abstention_accuracy = round(abstention_correct / len(abstention_prompts), 3)

    if not groundedness_scores and not citation_scores:
        warnings.append(
            "No RAG examples completed. Ensure corpus is indexed and model is available."
        )

    return metrics
