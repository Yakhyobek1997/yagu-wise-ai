"""Relational knowledge graph for PathRAG.

A ``networkx.MultiDiGraph`` of entities and relations carrying full provenance:
the chunk ids, source spans and audio timestamps that support each edge, plus a
reliability score derived from corroboration. Persisted as versioned JSON.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx

GRAPH_VERSION = 1


@dataclass
class Provenance:
    chunk_id: str
    source: str
    locator: str = ""
    speaker: str | None = None
    start_s: float | None = None


@dataclass
class Entity:
    name: str
    type: str = "concept"
    mentions: int = 0
    chunk_ids: set[str] = field(default_factory=set)


class KnowledgeGraph:
    def __init__(self) -> None:
        self.g = nx.MultiDiGraph()

    # ----------------------------------------------------------- build ----
    def add_entity(self, name: str, etype: str = "concept", chunk_id: str | None = None) -> str:
        key = normalize_entity(name)
        if not self.g.has_node(key):
            self.g.add_node(key, name=name, type=etype, mentions=0, chunk_ids=set())
        node = self.g.nodes[key]
        # When variants merge onto one key, show the cleanest display: prefer a
        # form without a possessive, then the shorter one ("Ford" over "Ford's").
        if _better_display(name, node["name"]):
            node["name"] = name
        node["mentions"] += 1
        if chunk_id:
            node["chunk_ids"].add(chunk_id)
        return key

    def add_relation(self, src: str, dst: str, relation: str, prov: Provenance) -> None:
        s = normalize_entity(src)
        d = normalize_entity(dst)
        if not self.g.has_node(s) or not self.g.has_node(d) or s == d:
            return
        # Merge into an existing identical relation edge if present.
        for _, _, data in self.g.edges([s], data=True):
            if data.get("_dst") == d and data.get("relation") == relation:
                data["provenance"].append(prov)
                data["weight"] += 1.0
                return
        self.g.add_edge(
            s, d, relation=relation, _dst=d, weight=1.0, reliability=0.0, provenance=[prov]
        )

    def finalize(self, source_trust: dict[str, float] | None = None) -> None:
        """Compute edge reliability from corroboration and source trust."""
        source_trust = source_trust or {}
        for _, _, data in self.g.edges(data=True):
            provs: list[Provenance] = data["provenance"]
            distinct_sources = {p.source for p in provs}
            corroboration = len(provs)
            trust = (
                sum(source_trust.get(s, 1.0) for s in distinct_sources) / len(distinct_sources)
                if distinct_sources
                else 1.0
            )
            # Diminishing returns: 1 source ~0.5, 2 ~0.67, 3 ~0.75 ... scaled by trust.
            data["reliability"] = round(trust * (corroboration / (corroboration + 1.0)), 4)

    # ---------------------------------------------------------- query -----
    def has(self, name: str) -> bool:
        return self.g.has_node(normalize_entity(name))

    def out_edges(self, node: str) -> list[tuple[str, str, dict[str, Any]]]:
        key = normalize_entity(node)
        if not self.g.has_node(key):
            return []
        return [(key, data["_dst"], data) for _, _, data in self.g.edges([key], data=True)]

    @property
    def n_entities(self) -> int:
        return self.g.number_of_nodes()

    @property
    def n_relations(self) -> int:
        return self.g.number_of_edges()

    # -------------------------------------------------------- persist -----
    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        nodes = []
        for key, data in self.g.nodes(data=True):
            nodes.append(
                {
                    "id": key,
                    "name": data["name"],
                    "type": data["type"],
                    "mentions": data["mentions"],
                    "chunk_ids": sorted(data["chunk_ids"]),
                }
            )
        edges = []
        for s, d, data in self.g.edges(data=True):
            edges.append(
                {
                    "src": s,
                    "dst": d,
                    "relation": data["relation"],
                    "weight": data["weight"],
                    "reliability": data["reliability"],
                    "provenance": [vars(p) for p in data["provenance"]],
                }
            )
        path.write_text(
            json.dumps({"version": GRAPH_VERSION, "nodes": nodes, "edges": edges}), encoding="utf-8"
        )

    @classmethod
    def load(cls, path: Path) -> KnowledgeGraph:
        kg = cls()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for n in data["nodes"]:
            kg.g.add_node(
                n["id"],
                name=n["name"],
                type=n["type"],
                mentions=n["mentions"],
                chunk_ids=set(n["chunk_ids"]),
            )
        for e in data["edges"]:
            provs = [Provenance(**p) for p in e["provenance"]]
            kg.g.add_edge(
                e["src"],
                e["dst"],
                relation=e["relation"],
                _dst=e["dst"],
                weight=e["weight"],
                reliability=e["reliability"],
                provenance=provs,
            )
        return kg


# Entity canonicalization (Phase 4): collapse the near-duplicates rule-based
# extraction produces — possessives and punctuation — so "Ford" / "Ford's" and
# "Ericsson" / "Ericsson's." resolve to one entity node (one wiki page, one KG
# hub). Deterministic and reproducible; semantic aliases (IBM / International
# Business Machines) are out of scope here.
_POSSESSIVE_RE = re.compile(r"[’']s\b|[’']$")
_PUNCT_EDGE = " \t\"'’“”.,;:!?()[]{}<>"


def normalize_entity(name: str) -> str:
    s = " ".join(name.lower().split())
    s = _POSSESSIVE_RE.sub("", s)  # ford's -> ford ; employees' -> employees
    s = " ".join(s.strip(_PUNCT_EDGE).split())
    return s or " ".join(name.lower().split())  # never collapse to empty


def _better_display(candidate: str, current: str) -> bool:
    """Is `candidate` a cleaner display name than `current`?"""
    c_poss = bool(_POSSESSIVE_RE.search(candidate.lower()))
    cur_poss = bool(_POSSESSIVE_RE.search(current.lower()))
    if c_poss != cur_poss:
        return not c_poss  # prefer the non-possessive form
    return len(candidate) < len(current)  # else prefer the shorter form
