"""RAG strategies: implemented approximations + planned stubs.

Implemented here (as approximations using existing components):
- KeywordBM25Strategy: route_hint="keyword"
- SelfRAGStrategy: critique-revise loop approximation
- CRAGStrategy: retrieval quality check with query rewriting fallback
- AdaptiveRAGStrategy: LLM-based query complexity classifier

Planned (require separate index builds):
- LightRAGLocalStrategy, LightRAGGlobalStrategy, LightRAGHybridStrategy
- RAPTORStrategy
"""

from __future__ import annotations

from typing import Any

from auralynq.rag.strategies.base import RAGStrategy, StrategyResult


def _not_implemented(strategy_id: str, strategy_name: str, query: str) -> StrategyResult:
    return StrategyResult(
        answer=(
            f"The **{strategy_name}** strategy is planned but not yet implemented. "
            "Falling back to Auralynq-RAG."
        ),
        status="answered",
        citations=[],
        route=strategy_id,
        confidence=0.0,
        evidence_coverage=0.0,
        trace_steps=[],
        trace=[],
        path_evidence=[],
        seeds=[],
        warnings=[f"Strategy {strategy_id} is planned — returned stub answer"],
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        fallback_strategy="auralynq_rag",
        fallback_reason="strategy_not_implemented",
    )


def _run_base(query: str, route_hint: str = "", final_k: int = 6, use_cache: bool = True) -> dict:
    """Call answer_question and return the dict."""
    from auralynq.agent.runner import answer_question

    res = answer_question(query, final_k=final_k, use_cache=use_cache, route_hint=route_hint)
    return res.to_dict()


def _llm_call(prompt: str, max_tokens: int = 256) -> str:
    """Best-effort LLM call for classifier/critic steps. Returns '' on failure."""
    try:
        from auralynq.llm.factory import get_llm

        llm = get_llm()
        return llm.generate(prompt, max_tokens=max_tokens).strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# KeywordBM25Strategy
# ---------------------------------------------------------------------------


class KeywordBM25Strategy(RAGStrategy):
    id = "keyword_bm25"
    name = "Keyword / BM25"
    description = "Pure lexical retrieval using BM25 scoring. Best for exact-match queries."
    status = "available"
    required_features = []
    supports_graph = False
    supports_rerank = False
    expected_latency = "fast"
    best_for = "Exact phrase matching, technical terms, named entities"
    limitations = "No semantic understanding; misses paraphrase variants"

    def run(
        self,
        query: str,
        final_k: int = 6,
        use_cache: bool = True,
        route_hint: str = "",
        **kwargs: Any,
    ) -> StrategyResult:
        d = _run_base(query, route_hint="keyword", final_k=final_k, use_cache=use_cache)
        return StrategyResult(
            answer=d.get("answer", ""),
            status=d.get("status", "answered"),
            citations=d.get("citations", []),
            route="keyword_bm25",
            confidence=d.get("confidence", 0.0),
            evidence_coverage=d.get("evidence_coverage", 0.0),
            trace_steps=d.get("trace_steps", []),
            trace=d.get("trace", []),
            path_evidence=[],
            seeds=d.get("seeds", []),
            warnings=["Strategy: keyword only — no semantic matching"],
            strategy_id=self.id,
            strategy_name=self.name,
            elapsed_ms=d.get("elapsed_ms", 0.0),
            iterations=d.get("iterations", 0),
            detected_entities=d.get("detected_entities", []),
            suggested_questions=d.get("suggested_questions", []),
            cached=d.get("cached", False),
        )


# ---------------------------------------------------------------------------
# SelfRAGStrategy (approximation)
# ---------------------------------------------------------------------------

_SELF_RAG_CRITIQUE_PROMPT = """\
You are a retrieval critic. An answer draft was produced from retrieved evidence.

Question: {question}

Retrieved snippets:
{snippets}

Draft answer: {draft}

Evaluate:
1. Is the draft answer fully supported by the retrieved snippets? (yes/partial/no)
2. Is retrieval relevant to the question? (yes/partial/no)
3. Is the draft useful/complete? (yes/partial/no)

Reply in this exact format:
SUPPORT: yes|partial|no
RELEVANCE: yes|partial|no
USEFUL: yes|partial|no
CRITIQUE: <one sentence>
"""

_SELF_RAG_REVISE_PROMPT = """\
You are a careful assistant. The draft answer below has weak support from retrieved evidence.

Question: {question}
Draft: {draft}
Critique: {critique}

Rewrite the answer to be faithful only to what the evidence supports. If evidence is insufficient, say so clearly.
Keep the answer concise.
"""


class SelfRAGStrategy(RAGStrategy):
    id = "self_rag"
    name = "Self-RAG-style Reflective"
    description = (
        "Retrieve, draft, critique support, revise if needed. "
        "Approximation of Self-RAG (Asai et al. 2023) without fine-tuned reflection tokens."
    )
    status = "experimental"
    required_features = []
    supports_abstention = True
    expected_latency = "slow"
    best_for = "Questions where answer faithfulness to sources is critical"
    limitations = "Full Self-RAG requires fine-tuned model; this uses critique-revise approximation"

    def is_available(self) -> tuple[bool, str]:
        return True, ""

    def run(
        self, query: str, final_k: int = 6, use_cache: bool = True, **kwargs: Any
    ) -> StrategyResult:
        import time

        t0 = time.perf_counter()

        # Step 1: initial retrieval + answer
        d = _run_base(query, route_hint="fast", final_k=final_k, use_cache=False)
        draft = d.get("answer", "")
        citations = d.get("citations", [])
        trace = d.get("trace", [])
        trace_steps = d.get("trace_steps", [])
        warnings: list[str] = ["Self-RAG: experimental approximation — critique-revise loop"]

        critique_text = ""
        revised = False

        # Step 2: build snippet list for critique
        snippets_str = "\n".join(
            f"[{c.get('marker', i + 1)}] {c.get('source', '')} — {c.get('locator', '')}"
            for i, c in enumerate(citations[:4])
        )

        # Step 3: critique
        critique_raw = _llm_call(
            _SELF_RAG_CRITIQUE_PROMPT.format(
                question=query, snippets=snippets_str or "(none)", draft=draft
            ),
            max_tokens=200,
        )

        # Parse critique
        support = "yes"
        relevance = "yes"
        useful = "yes"
        for line in critique_raw.splitlines():
            line = line.strip()
            if line.startswith("SUPPORT:"):
                support = line.split(":", 1)[-1].strip().lower()
            elif line.startswith("RELEVANCE:"):
                relevance = line.split(":", 1)[-1].strip().lower()
            elif line.startswith("USEFUL:"):
                useful = line.split(":", 1)[-1].strip().lower()
            elif line.startswith("CRITIQUE:"):
                critique_text = line.split(":", 1)[-1].strip()

        trace_steps.append(
            {
                "step": "self_rag_critique",
                "status": "success",
                "label": "Self-RAG Critique",
                "detail": f"Support={support} Relevance={relevance} Useful={useful}",
            }
        )

        # Step 4: revise if support is weak
        if support in ("no", "partial") and draft:
            revised_answer = _llm_call(
                _SELF_RAG_REVISE_PROMPT.format(
                    question=query, draft=draft, critique=critique_text or "Support is weak."
                ),
                max_tokens=512,
            )
            if revised_answer and len(revised_answer) > 20:
                draft = revised_answer
                revised = True
                warnings.append(
                    f"Self-RAG: answer revised due to weak support. Critique: {critique_text}"
                )
                trace_steps.append(
                    {
                        "step": "self_rag_revise",
                        "status": "success",
                        "label": "Self-RAG Revision",
                        "detail": "Answer revised for faithfulness",
                    }
                )

        # Confidence penalty for weak support
        conf = d.get("confidence", 0.0)
        if support == "no":
            conf = min(conf, 0.3)
        elif support == "partial":
            conf = min(conf, 0.6)

        elapsed_ms = (time.perf_counter() - t0) * 1000

        return StrategyResult(
            answer=draft,
            status=d.get("status", "answered"),
            citations=citations,
            route="self_rag",
            confidence=conf,
            evidence_coverage=d.get("evidence_coverage", 0.0),
            trace_steps=trace_steps,
            trace=trace,
            path_evidence=[],
            seeds=d.get("seeds", []),
            warnings=warnings,
            strategy_id=self.id,
            strategy_name=self.name,
            elapsed_ms=elapsed_ms,
            iterations=2 if revised else 1,
            detected_entities=d.get("detected_entities", []),
            suggested_questions=d.get("suggested_questions", []),
            cached=False,
        )


# ---------------------------------------------------------------------------
# CRAGStrategy (approximation)
# ---------------------------------------------------------------------------

_RELEVANCE_CHECK_PROMPT = """\
Assess whether these retrieved passages are relevant to the question.

Question: {question}

Passages:
{passages}

Rate relevance: high / medium / low / none
Reply with exactly one word: high, medium, low, or none.
"""

_QUERY_REWRITE_PROMPT = """\
The original query did not retrieve sufficient evidence.
Rewrite the query to be more specific, using different vocabulary that may appear in the source documents.
Original query: {query}
Rewritten query (one line only):"""


class CRAGStrategy(RAGStrategy):
    id = "crag"
    name = "CRAG-style Corrective"
    description = (
        "Evaluates retrieval quality; rewrites query and corrects retrieval if insufficient. "
        "Approximation of CRAG (Yan et al. 2024) without web fallback."
    )
    status = "experimental"
    required_features = []
    supports_web = False
    supports_abstention = True
    expected_latency = "slow"
    best_for = "Questions where corpus coverage may be sparse or retrieval is uncertain"
    limitations = "No web search fallback in this implementation; abstains if rewrite also fails"

    def is_available(self) -> tuple[bool, str]:
        return True, ""

    def run(
        self, query: str, final_k: int = 6, use_cache: bool = True, **kwargs: Any
    ) -> StrategyResult:
        import time

        t0 = time.perf_counter()
        warnings: list[str] = []
        trace_steps: list[dict] = []

        # Step 1: initial retrieval
        d = _run_base(query, route_hint="fast", final_k=final_k, use_cache=False)
        citations = d.get("citations", [])
        coverage = d.get("evidence_coverage", 0.0)
        trace = d.get("trace", [])
        trace_steps = list(d.get("trace_steps", []))

        trace_steps.append(
            {
                "step": "crag_quality_check",
                "status": "success",
                "label": "CRAG: Retrieval Quality Check",
                "detail": f"Initial coverage={coverage:.2f} citations={len(citations)}",
            }
        )

        # Step 2: check relevance using LLM
        passages_str = "\n".join(
            f"[{c.get('marker', i + 1)}] {c.get('source', '')}" for i, c in enumerate(citations[:4])
        )
        relevance_raw = (
            _llm_call(
                _RELEVANCE_CHECK_PROMPT.format(question=query, passages=passages_str or "(none)"),
                max_tokens=10,
            )
            .strip()
            .lower()
        )

        relevance_score = {"high": 1.0, "medium": 0.6, "low": 0.3, "none": 0.0}.get(
            relevance_raw, 0.5
        )

        trace_steps.append(
            {
                "step": "crag_relevance_score",
                "status": "success" if relevance_score >= 0.5 else "warning",
                "label": "CRAG: Relevance Assessment",
                "detail": f"Relevance={relevance_raw} score={relevance_score:.2f}",
            }
        )

        # Step 3: if retrieval weak, rewrite query and retry
        corrected = False
        if relevance_score < 0.5 or coverage < 0.2:
            rewritten = _llm_call(
                _QUERY_REWRITE_PROMPT.format(query=query),
                max_tokens=80,
            ).strip()
            # Clean up LLM output — take first non-empty line
            rewritten = next(
                (line.strip() for line in rewritten.splitlines() if len(line.strip()) > 5),
                "",
            )
            if rewritten and rewritten.lower() != query.lower():
                trace_steps.append(
                    {
                        "step": "crag_query_rewrite",
                        "status": "success",
                        "label": "CRAG: Query Rewritten",
                        "detail": f"Rewritten: {rewritten[:80]}",
                    }
                )
                d2 = _run_base(rewritten, route_hint="hybrid", final_k=final_k, use_cache=False)
                if d2.get("evidence_coverage", 0.0) > coverage:
                    d = d2
                    citations = d.get("citations", [])
                    coverage = d.get("evidence_coverage", 0.0)
                    trace.extend(d.get("trace", []))
                    trace_steps.extend(d.get("trace_steps", []))
                    warnings.append(
                        f"CRAG: original retrieval weak; corrected with rewritten query: '{rewritten}'"
                    )
                    corrected = True
                else:
                    warnings.append("CRAG: query rewrite did not improve retrieval coverage.")
            else:
                warnings.append("CRAG: could not generate a useful query rewrite.")

        if relevance_score == 0.0 and not corrected:
            warnings.append(
                "CRAG: retrieval returned no relevant passages. Consider reindexing or using a different query."
            )

        trace_steps.append(
            {
                "step": "crag_corrective_complete",
                "status": "success",
                "label": "CRAG: Corrective Complete",
                "detail": f"corrected={corrected} final_coverage={coverage:.2f}",
            }
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        warnings.insert(0, "CRAG: experimental approximation (no web fallback)")

        return StrategyResult(
            answer=d.get("answer", ""),
            status=d.get("status", "answered"),
            citations=citations,
            route="crag",
            confidence=d.get("confidence", 0.0) * max(relevance_score, 0.1),
            evidence_coverage=coverage,
            trace_steps=trace_steps,
            trace=trace,
            path_evidence=[],
            seeds=d.get("seeds", []),
            warnings=warnings,
            strategy_id=self.id,
            strategy_name=self.name,
            elapsed_ms=elapsed_ms,
            iterations=2 if corrected else 1,
            detected_entities=d.get("detected_entities", []),
            suggested_questions=d.get("suggested_questions", []),
            cached=False,
        )


# ---------------------------------------------------------------------------
# AdaptiveRAGStrategy
# ---------------------------------------------------------------------------

_COMPLEXITY_PROMPT = """\
Classify this question's complexity for retrieval-augmented generation.

Question: {question}

Categories:
- simple_fact: single factual lookup, one document
- exact_lookup: exact term, ID, name, code search
- summary: broad summarisation across many docs
- comparison: comparing two or more entities
- multi_hop: requires chaining multiple evidence pieces
- inventory: counts/lists of indexed documents (corpus metadata)
- general_knowledge: not document-specific, LLM can answer directly
- visual_grounding_needed: requires seeing a figure, table, chart, or image

Reply with exactly one category name from the list above.
"""

_COMPLEXITY_TO_ROUTE: dict[str, str] = {
    "simple_fact": "fast",
    "exact_lookup": "keyword",
    "summary": "fast",
    "comparison": "hybrid",
    "multi_hop": "graph",
    "inventory": "fast",
    "general_knowledge": "fast",
    "visual_grounding_needed": "fast",
}

_KNOWN_CATEGORIES = set(_COMPLEXITY_TO_ROUTE.keys())


class AdaptiveRAGStrategy(RAGStrategy):
    id = "adaptive"
    name = "Adaptive-RAG"
    description = (
        "Classifies query complexity and routes to the cheapest sufficient strategy. "
        "Approximation of Adaptive-RAG (Jeong et al. 2024) using an LLM classifier."
    )
    status = "experimental"
    required_features = []
    supports_abstention = True
    expected_latency = "fast"
    best_for = "Mixed workloads — auto-selects simple/complex path"
    limitations = (
        "Classifier accuracy depends on LLM quality; adds one round-trip for classification"
    )

    def is_available(self) -> tuple[bool, str]:
        return True, ""

    def run(
        self, query: str, final_k: int = 6, use_cache: bool = True, **kwargs: Any
    ) -> StrategyResult:
        import time

        t0 = time.perf_counter()
        trace_steps: list[dict] = []
        warnings: list[str] = ["Adaptive-RAG: experimental approximation"]

        # Step 1: classify complexity
        complexity_raw = (
            _llm_call(_COMPLEXITY_PROMPT.format(question=query), max_tokens=20).strip().lower()
        )

        # Clean up — take first word that matches a known category
        complexity = next(
            (cat for cat in _KNOWN_CATEGORIES if cat in complexity_raw),
            "simple_fact",
        )
        route_hint = _COMPLEXITY_TO_ROUTE.get(complexity, "fast")

        trace_steps.append(
            {
                "step": "adaptive_classify",
                "status": "success",
                "label": "Adaptive-RAG: Complexity Classification",
                "detail": f"complexity={complexity} → route={route_hint}",
            }
        )

        # Step 2: route to appropriate retrieval
        d = _run_base(query, route_hint=route_hint, final_k=final_k, use_cache=use_cache)
        trace_steps.extend(d.get("trace_steps", []))

        trace_steps.append(
            {
                "step": "adaptive_complete",
                "status": "success",
                "label": "Adaptive-RAG: Complete",
                "detail": f"complexity={complexity} route={route_hint} coverage={d.get('evidence_coverage', 0):.2f}",
            }
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000

        return StrategyResult(
            answer=d.get("answer", ""),
            status=d.get("status", "answered"),
            citations=d.get("citations", []),
            route=f"adaptive/{route_hint}",
            confidence=d.get("confidence", 0.0),
            evidence_coverage=d.get("evidence_coverage", 0.0),
            trace_steps=trace_steps,
            trace=d.get("trace", []),
            path_evidence=[],
            seeds=d.get("seeds", []),
            warnings=warnings,
            strategy_id=self.id,
            strategy_name=self.name,
            elapsed_ms=elapsed_ms,
            iterations=d.get("iterations", 0) + 1,
            detected_entities=d.get("detected_entities", []),
            suggested_questions=d.get("suggested_questions", []),
            cached=d.get("cached", False),
            route_rationale=f"Adaptive-RAG classified query as '{complexity}' → using {route_hint} retrieval",
        )


# ---------------------------------------------------------------------------
# Planned stubs (require separate index builds)
# ---------------------------------------------------------------------------


class LightRAGLocalStrategy(RAGStrategy):
    id = "lightrag_local"
    name = "LightRAG-style Local"
    description = (
        "Entity-centric retrieval using local entity neighborhoods. (LightRAG, Guo et al. 2024)"
    )
    status = "planned"
    required_features = ["graph_index"]
    supports_graph = True
    expected_latency = "medium"
    best_for = "Entity-specific questions requiring neighborhood context"
    limitations = "Not yet implemented — requires dedicated graph index build"

    def is_available(self) -> tuple[bool, str]:
        return False, "LightRAG-style local retrieval is planned. Not yet implemented."

    def run(self, query: str, **kwargs: Any) -> StrategyResult:
        return _not_implemented(self.id, self.name, query)


class LightRAGGlobalStrategy(RAGStrategy):
    id = "lightrag_global"
    name = "LightRAG-style Global"
    description = (
        "Community-level summary retrieval for broad synthesis. (LightRAG, Guo et al. 2024)"
    )
    status = "planned"
    required_features = ["graph_index", "community_summaries"]
    supports_graph = True
    expected_latency = "slow"
    best_for = "High-level synthesis and theme discovery questions"
    limitations = "Not yet implemented — requires community summary build step"

    def is_available(self) -> tuple[bool, str]:
        return False, "LightRAG-style global retrieval is planned. Not yet implemented."

    def run(self, query: str, **kwargs: Any) -> StrategyResult:
        return _not_implemented(self.id, self.name, query)


class LightRAGHybridStrategy(RAGStrategy):
    id = "lightrag_hybrid"
    name = "LightRAG-style Hybrid/Mix"
    description = "Combines local entity + global community retrieval. (LightRAG, Guo et al. 2024)"
    status = "planned"
    required_features = ["graph_index", "community_summaries"]
    supports_graph = True
    expected_latency = "slow"
    best_for = "Complex questions requiring both entity detail and global context"
    limitations = "Not yet implemented"

    def is_available(self) -> tuple[bool, str]:
        return False, "LightRAG-style hybrid retrieval is planned. Not yet implemented."

    def run(self, query: str, **kwargs: Any) -> StrategyResult:
        return _not_implemented(self.id, self.name, query)


class RAPTORStrategy(RAGStrategy):
    id = "raptor"
    name = "RAPTOR-style Hierarchical"
    description = "Hierarchical summary tree retrieval. (Sarthi et al. 2024)"
    status = "planned"
    required_features = ["hierarchical_index"]
    supports_graph = False
    expected_latency = "medium"
    best_for = "Multi-document synthesis and broad coverage questions"
    limitations = "Requires hierarchical index build — not yet implemented"

    def is_available(self) -> tuple[bool, str]:
        return (
            False,
            "RAPTOR-style hierarchical retrieval is planned. Requires hierarchical index build.",
        )

    def run(self, query: str, **kwargs: Any) -> StrategyResult:
        return _not_implemented(self.id, self.name, query)
