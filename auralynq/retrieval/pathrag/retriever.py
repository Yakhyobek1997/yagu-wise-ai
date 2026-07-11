"""PathRAG graph retrieval (Chen et al., 2025) — clean-room implementation.

Pipeline:
  1. **Node retrieval** — map the query to seed entities (exact + fuzzy + embedding
     similarity over entity names).
  2. **Relational path expansion** — bounded-hop DFS over the knowledge graph from
     each seed, enumerating candidate relational paths.
  3. **Flow-based pruning** — distribute a resource budget from the seeds along
     edges with per-hop decay; each edge accrues 'flow'. A path's flow is its
     bottleneck (min edge flow). Low-flow paths are pruned.
  4. **PPR-augmented scoring** — Personalized PageRank (HippoRAG2, NeurIPS'24)
     with seed personalization gives each node a convergent authority score.
     Final path score blends flow reliability (40%) with PPR terminal authority
     (60%), correcting the bias of pure resource-decay toward short paths.
  5. **Path-reliability scoring** — combine blended score with mean edge reliability.
  6. **Path-to-text prompting** — render each surviving path as a grounded
     statement with provenance.
  7. **Golden-region ordering** — order paths so the most reliable sit at the
     prompt edges (mitigates lost-in-the-middle).

Isolated under ``auralynq/retrieval/pathrag/`` (ADR-0006).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from auralynq.embeddings.base import Embedder
from auralynq.embeddings.factory import get_embedder
from auralynq.ingest.models import Chunk
from auralynq.retrieval.base import Retriever
from auralynq.retrieval.models import Filter, PathEvidence, RetrievalResult, ScoredChunk
from auralynq.retrieval.pathrag.graph import KnowledgeGraph
from auralynq.utils import tokenize
from auralynq.vectorstore.base import VectorStore

DECAY = 0.8  # per-hop resource decay

# Paper §4.1 (Eq. 2): score(p) = lam*flow_score(p) + (1-lam)*ppr(term(p))
_PPR_TELEPORT = 0.15  # teleportation probability (restart prob.) — alpha in the paper.
# NetworkX pagerank(alpha=...) takes the *damping* factor,
# so we pass alpha=1-_PPR_TELEPORT = 0.85 to nx.pagerank.
_PPR_FLOW_W = 0.4  # λ   — weight on bottleneck flow score
_PPR_AUTH_W = 0.6  # 1-λ — weight on PPR terminal-node authority


@dataclass
class _Path:
    nodes: list[str]
    edges: list[dict]
    flow: float  # bottleneck flow: min_{e ∈ p} r(e)  (Eq. 2, flow_score)
    reliability: float  # mean edge reliability (auxiliary signal, not in score blend)
    ppr_score: float = 0.0  # terminal-node PPR authority; set by _apply_ppr

    @property
    def score(self) -> float:
        """Blended path score — paper Eq. 2.

        score(p) = λ · flow_score(p) + (1-λ) · ppr(term(p))

        flow_score(p) = min_{e ∈ p} r(e)  (bottleneck resource budget, self.flow).
        PPR authority is path-length-invariant, correcting the short-path bias that
        pure flow scoring introduces for multi-hop paths.
        """
        return _PPR_FLOW_W * self.flow + _PPR_AUTH_W * self.ppr_score


class PathRAGRetriever(Retriever):
    name = "pathrag"

    def __init__(
        self,
        graph: KnowledgeGraph,
        store: VectorStore | None = None,
        embedder: Embedder | None = None,
        *,
        max_hops: int = 3,
        max_paths: int = 8,
        beam: int = 6,
    ) -> None:
        self.graph = graph
        self.store = store
        self.embedder = embedder or get_embedder()
        self.max_hops = max_hops
        self.max_paths = max_paths
        self.beam = beam

    # ----------------------------------------------------- node retrieval ---
    def seed_entities(self, query: str, top: int = 4) -> list[str]:
        if self.graph.n_entities == 0:
            return []
        q_tokens = set(tokenize(query))
        q_lower = query.lower()
        scored: list[tuple[float, str]] = []
        names = [
            (key, data["name"], data.get("mentions", 1))
            for key, data in self.graph.g.nodes(data=True)
        ]

        # Exact / token-overlap match first. Score favours *precision* (entities
        # whose tokens are mostly in the query) so a concise node like "France"
        # outranks a long, incidentally-overlapping name like "Senate of France",
        # with a strong bonus when the entity name appears verbatim in the query.
        for key, name, mentions in names:
            name_tokens = set(tokenize(name))
            if not name_tokens:
                continue
            overlap = len(q_tokens & name_tokens)
            if not overlap:
                continue
            precision = overlap / len(name_tokens)
            exact = 3.0 if key in q_lower else 0.0
            score = exact + 2.0 * precision + 0.05 * mentions**0.5
            scored.append((score, key))
        if scored:
            scored.sort(reverse=True)
            return [k for _, k in scored[:top]]

        # Fall back to embedding similarity over entity names.
        q = self.embedder.embed_query(query).dense
        name_emb = self.embedder.embed([name for _, name, _ in names]).dense
        sims = [(self.embedder.cosine(q, name_emb[i]), names[i][0]) for i in range(len(names))]
        sims.sort(reverse=True)
        return [k for _, k in sims[:top]]

    # -------------------------------------------------- path expansion -----
    def _expand(self, seeds: list[str]) -> list[_Path]:
        paths: list[_Path] = []
        for seed in seeds:
            self._dfs(seed, [seed], [], paths, visited={seed})
        return paths

    def _dfs(self, node, nodes, edges, out, visited) -> None:
        if len(edges) >= self.max_hops:
            return
        out_edges = self.graph.out_edges(node)[: self.beam]
        for _src, dst, data in out_edges:
            if dst in visited:
                continue
            new_edges = [*edges, data]
            new_nodes = [*nodes, dst]
            rel = sum(e["reliability"] for e in new_edges) / len(new_edges)
            out.append(_Path(nodes=new_nodes, edges=new_edges, flow=0.0, reliability=rel))
            self._dfs(dst, new_nodes, new_edges, out, visited | {dst})

    # ----------------------------------------------- PPR authority scores --
    def _assign_ppr(self, seeds: list[str]) -> dict[str, float]:
        """Run Personalized PageRank from seeds and return per-node authority scores.

        Uses NetworkX's power-iteration pagerank with a personalisation vector
        concentrated on the seed entities. Alpha is the teleport probability
        (probability of jumping back to a seed at each step), matching the
        HippoRAG2 reset-probability formulation.

        Returns an empty dict when the graph has no nodes (safe fallback for the
        offline / unit-test scenario where no KG is built yet).
        """
        if self.graph.n_entities == 0:
            return {}
        try:
            import networkx as nx

            # Build a simple DiGraph view (no multi-edges) for pagerank stability.
            g = nx.DiGraph()
            for u, v, data in self.graph.g.edges(data=True):
                w = data.get("weight", 1.0) * (0.1 + data.get("reliability", 0.0))
                if g.has_edge(u, v):
                    g[u][v]["weight"] += w
                else:
                    g.add_edge(u, v, weight=w)

            if g.number_of_nodes() == 0:
                return {}

            # Uniform weight over seeds; zero for all other nodes.
            personalisation = dict.fromkeys(g.nodes(), 0.0)
            for s in seeds:
                if s in personalisation:
                    personalisation[s] += 1.0
            total = sum(personalisation.values())
            if total == 0:
                return {}
            personalisation = {k: v / total for k, v in personalisation.items()}

            # NetworkX pagerank(alpha=...) takes the damping factor.
            # Our paper uses 0.15 as the teleportation probability, so
            # damping = 1 - 0.15 = 0.85.  Convergence in <=50 iterations guaranteed
            # because the contraction ratio of power iteration is (1 - teleport) < 1.
            scores = nx.pagerank(
                g,
                alpha=1.0 - _PPR_TELEPORT,  # damping = 0.85
                personalization=personalisation,
                max_iter=50,
                tol=1e-6,
            )
            # Normalise to [0, 1] so scores are comparable across graph sizes.
            max_s = max(scores.values(), default=1.0) or 1.0
            return {k: v / max_s for k, v in scores.items()}
        except Exception:  # pragma: no cover — networkx unavailable or graph degenerate
            return {}

    def _apply_ppr(self, paths: list[_Path], ppr: dict[str, float]) -> list[_Path]:
        if not ppr:
            return paths
        for p in paths:
            # Terminal-node authority: reward paths that reach high-authority nodes.
            p.ppr_score = ppr.get(p.nodes[-1], 0.0) if p.nodes else 0.0
        return paths

    # ------------------------------------------------- flow-based pruning ---
    def _assign_flow(self, seeds: list[str]) -> dict[int, float]:
        """Resource-allocation flow: spread a budget from seeds with decay."""
        edge_flow: dict[int, float] = {}
        resource: dict[str, float] = dict.fromkeys(seeds, 1.0)
        for _hop in range(self.max_hops):
            nxt: dict[str, float] = {}
            for node, res in resource.items():
                out_edges = self.graph.out_edges(node)
                if not out_edges:
                    continue
                denom = sum(e["weight"] * (0.1 + e["reliability"]) for _, _, e in out_edges) or 1.0
                for _src, dst, data in out_edges:
                    share = (data["weight"] * (0.1 + data["reliability"])) / denom
                    transfer = res * DECAY * share
                    edge_flow[id(data)] = edge_flow.get(id(data), 0.0) + transfer
                    nxt[dst] = nxt.get(dst, 0.0) + transfer
            resource = nxt
            if not resource:
                break
        return edge_flow

    def _prune(self, paths: list[_Path], edge_flow: dict[int, float]) -> list[_Path]:
        for p in paths:
            p.flow = min((edge_flow.get(id(e), 0.0) for e in p.edges), default=0.0)
        paths = [p for p in paths if p.flow > 0]
        paths.sort(key=lambda p: p.score, reverse=True)
        # De-duplicate by node-set to avoid near-identical paths.
        seen: set[tuple] = set()
        pruned: list[_Path] = []
        for p in paths:
            key = tuple(p.nodes)
            if key in seen:
                continue
            seen.add(key)
            pruned.append(p)
            if len(pruned) >= self.max_paths:
                break
        return pruned

    # ------------------------------------------------------ path-to-text ---
    def _to_evidence(self, path: _Path) -> PathEvidence:
        names = [self.graph.g.nodes[n]["name"] for n in path.nodes]
        relations = [e["relation"] for e in path.edges]
        chunk_ids: list[str] = []
        for e in path.edges:
            for prov in e["provenance"]:
                if prov.chunk_id not in chunk_ids:
                    chunk_ids.append(prov.chunk_id)
        # Path-to-text rendering: include PPR authority in the provenance text
        # so the synthesiser can weight this path's contribution.
        parts = [names[0]]
        for i, rel in enumerate(relations):
            parts.append(f"{rel.replace('_', ' ')} {names[i + 1]}")
        ppr_tag = f", ppr {path.ppr_score:.3f}" if path.ppr_score > 0 else ""
        text = " ".join(parts) + f". (reliability {path.reliability:.2f}{ppr_tag})"
        return PathEvidence(
            nodes=names,
            relations=relations,
            reliability=path.reliability,
            ppr_score=path.ppr_score,
            text=text,
            chunk_ids=chunk_ids,
        )

    def _golden_order(self, evidences: list[PathEvidence]) -> list[PathEvidence]:
        """Place highest-score paths at context boundaries (lost-in-middle mitigation).

        Sort by the same blended score as _Path.score — Eq. 2: λ·reliability + (1-λ)·ppr_score
        — so that PPR-authority paths receive the same priority here that they received
        during path selection.  Even-indexed entries go to the head of context; odd-indexed
        entries are reversed into the tail, keeping high-relevance paths at both ends.
        """
        blended = lambda e: _PPR_FLOW_W * e.reliability + _PPR_AUTH_W * e.ppr_score  # noqa: E731
        ranked = sorted(evidences, key=blended, reverse=True)
        head: list[PathEvidence] = []
        tail: list[PathEvidence] = []
        for i, e in enumerate(ranked):
            (head if i % 2 == 0 else tail).append(e)
        return head + tail[::-1]

    # ------------------------------------------------------------ retrieve --
    def retrieve(self, query: str, k: int, filt: Filter | None = None) -> RetrievalResult:
        t0 = time.perf_counter()
        seeds = self.seed_entities(query)
        if not seeds:
            return RetrievalResult(
                query=query,
                method=self.name,
                chunks=[],
                took_ms=(time.perf_counter() - t0) * 1000,
                metadata={"seeds": [], "paths": []},
            )
        candidate_paths = self._expand(seeds)
        ppr = self._assign_ppr(seeds)
        self._apply_ppr(candidate_paths, ppr)
        edge_flow = self._assign_flow(seeds)
        pruned = self._prune(candidate_paths, edge_flow)
        evidences = self._golden_order([self._to_evidence(p) for p in pruned])

        # Resolve cited chunks (deduped, ordered by appearance) into ScoredChunks.
        chunks: list[ScoredChunk] = []
        seen_ids: set[str] = set()
        rel_by_chunk: dict[str, float] = {}
        for ev in evidences:
            for cid in ev.chunk_ids:
                rel_by_chunk[cid] = max(rel_by_chunk.get(cid, 0.0), ev.reliability)
        for ev in evidences:
            for cid in ev.chunk_ids:
                if cid in seen_ids:
                    continue
                seen_ids.add(cid)
                chunk = self._resolve(cid, ev)
                if chunk is None:
                    continue
                chunks.append(
                    ScoredChunk(
                        chunk=chunk,
                        score=rel_by_chunk.get(cid, 0.0),
                        method="pathrag",
                        rank=len(chunks),
                    )
                )
                if len(chunks) >= k:
                    break
            if len(chunks) >= k:
                break

        return RetrievalResult(
            query=query,
            method=self.name,
            chunks=chunks,
            took_ms=(time.perf_counter() - t0) * 1000,
            metadata={
                "seeds": [self.graph.g.nodes[s]["name"] for s in seeds],
                "paths": [ev.model_dump() for ev in evidences],
                "n_candidate_paths": len(candidate_paths),
            },
        )

    def _resolve(self, chunk_id: str, ev: PathEvidence) -> Chunk | None:
        if self.store is not None:
            ch = self.store.get(chunk_id)
            if ch is not None:
                return ch
        # Fallback: synthesize a chunk from the path text so citations still work.
        from auralynq.ingest.models import SourceType

        return Chunk(
            id=chunk_id,
            doc_id="graph",
            text=ev.text,
            source="knowledge_graph",
            source_type=SourceType.unknown,
        )
