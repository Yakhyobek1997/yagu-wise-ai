from __future__ import annotations

from auralynq.ingest.models import AudioSegment, Chunk, SourceType
from auralynq.pipeline import build_index, load_graph
from auralynq.retrieval.pathrag.builder import build_from_chunks
from auralynq.retrieval.pathrag.graph import KnowledgeGraph


def _chunks():
    return [
        Chunk(
            id="c0",
            doc_id="d",
            ordinal=0,
            source="geo.txt",
            source_type=SourceType.text,
            text="Paris is the capital of France. France is in Europe.",
        ),
        Chunk(
            id="c1",
            doc_id="d",
            ordinal=1,
            source="geo2.txt",
            source_type=SourceType.text,
            text="Paris is the capital of France and a large city.",
        ),
        Chunk(
            id="c2",
            doc_id="d",
            ordinal=2,
            source="talk.wav",
            source_type=SourceType.audio,
            text="PathRAG uses Qdrant for hybrid retrieval.",
            audio=AudioSegment(start_s=1.0, end_s=4.0, speaker="SPEAKER_00"),
        ),
    ]


def test_build_graph_entities_relations():
    kg = build_from_chunks(_chunks())
    assert kg.has("Paris")
    assert kg.has("France")
    assert kg.n_relations >= 1


def test_reliability_increases_with_corroboration():
    kg = build_from_chunks(_chunks())
    edges = kg.out_edges("Paris")
    assert edges
    # Paris->France corroborated by two sources should have reliability > 0.5
    rels = [d["reliability"] for _, dst, d in edges if dst == "france"]
    assert rels and max(rels) > 0.5


def test_graph_persistence_roundtrip(tmp_path):
    kg = build_from_chunks(_chunks())
    p = tmp_path / "graph.json"
    kg.save(p)
    loaded = KnowledgeGraph.load(p)
    assert loaded.n_entities == kg.n_entities
    assert loaded.n_relations == kg.n_relations


def test_provenance_carries_audio_timestamp():
    kg = build_from_chunks(_chunks())
    found = False
    for _, _, data in kg.g.edges(data=True):
        for prov in data["provenance"]:
            if prov.speaker == "SPEAKER_00":
                found = True
                assert prov.start_s == 1.0
    assert found


def test_build_index_end_to_end(corpus_dir):
    stats = build_index(corpus_dir)
    assert stats["documents"] == 2
    assert stats["chunks_indexed"] >= 2
    assert stats["entities"] >= 1
    kg = load_graph()
    assert kg.n_entities == stats["entities"]


# ---- Phase 4: entity canonicalization ------------------------------------
def test_normalize_entity_canonicalizes_possessives():
    from auralynq.retrieval.pathrag.graph import normalize_entity

    assert normalize_entity("Ford") == "ford"
    assert normalize_entity("Ford's") == "ford"
    assert normalize_entity("Ford’s") == "ford"  # curly apostrophe
    assert normalize_entity("Ericsson.") == "ericsson"
    assert normalize_entity("employees'") == "employees"
    assert normalize_entity("'s") == "'s"  # never collapses to empty (fallback)


def test_add_entity_merges_variants_and_prefers_clean_display():
    from auralynq.retrieval.pathrag.graph import KnowledgeGraph, normalize_entity

    kg = KnowledgeGraph()
    kg.add_entity("Ford's")
    kg.add_entity("Ford")
    assert kg.n_entities == 1  # variants merged onto one node
    node = kg.g.nodes[normalize_entity("Ford")]
    assert node["name"] == "Ford"  # non-possessive display preferred
    assert node["mentions"] == 2
