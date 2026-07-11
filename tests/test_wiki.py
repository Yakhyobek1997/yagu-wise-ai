from __future__ import annotations

from auralynq.config.settings import Settings
from auralynq.ingest.models import Chunk, SourceType
from auralynq.retrieval.pathrag.builder import build_from_chunks
from auralynq.wiki.generator import synthesize_wiki
from auralynq.wiki.store import WikiStore, slug


class _StubLLM:
    """Deterministic stand-in for a provider — no network, no model."""

    name = "stub"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate(self, prompt: str, *, system=None, temperature=None, max_tokens=None) -> str:
        self.calls.append(prompt)
        return "One-sentence definition.\n\n## Summary\nThe sources describe it [1].\n"


def _chunks() -> list[Chunk]:
    return [
        Chunk(id="c0", doc_id="d", ordinal=0, source="geo.txt", source_type=SourceType.text,
              text="Paris is the capital of France. France is in Europe."),
        Chunk(id="c1", doc_id="d", ordinal=1, source="geo2.txt", source_type=SourceType.text,
              text="Paris is the capital of France and a large city."),
    ]


def test_slug_is_filesystem_safe_and_stable():
    assert slug("GPT-4 / Turbo!") == "gpt_4_turbo"
    assert slug("  Hello World  ") == "hello_world"
    long = "x" * 200
    assert len(slug(long)) <= 64 and slug(long) == slug(long)


def test_wiki_store_roundtrip(tmp_path):
    store = WikiStore(tmp_path / "wiki_pages")
    meta = store.write_page(
        "paris", title="Paris", body="Capital of France [1].",
        sources=["geo.txt", "geo2.txt"], mentions=3,
    )
    assert meta.path == "entity_paris.md"
    page = store.read_page("paris")
    assert page is not None
    assert "title: \"Paris\"" in page["markdown"]
    assert "Capital of France [1]." in page["markdown"]
    assert page["mentions"] == 3
    listed = store.list_pages()
    assert any(p["id"] == "paris" for p in listed)
    assert store.count() == 1
    store.append_log("test", n=1)
    assert (tmp_path / "wiki_pages" / "_log.jsonl").exists()


def test_read_missing_page_returns_none(tmp_path):
    assert WikiStore(tmp_path / "w").read_page("nope") is None


def test_synthesize_wiki_from_kg(tmp_path):
    s = Settings(data_dir=tmp_path)
    s.wiki.enabled = True
    s.wiki.min_mentions = 1
    kg = build_from_chunks(_chunks())
    llm = _StubLLM()

    written = synthesize_wiki(kg, _chunks(), llm=llm, settings=s)

    assert written >= 1
    assert llm.calls, "LLM was invoked for synthesis"
    store = WikiStore(s.wiki_dir)
    assert store.count() == written
    paris = store.read_page("paris")
    assert paris is not None
    # Frontmatter carries the source provenance from the entity's chunks.
    assert "geo.txt" in paris["markdown"]
    assert "## Summary" in paris["markdown"]


def test_wiki_disabled_by_default():
    # Assert the declared code default (immune to a local .env that enables it).
    from auralynq.config.settings import WikiSettings

    assert WikiSettings.model_fields["enabled"].default is False


def test_min_mentions_gate(tmp_path):
    s = Settings(data_dir=tmp_path)
    s.wiki.enabled = True
    s.wiki.min_mentions = 999  # gate everything out
    kg = build_from_chunks(_chunks())
    assert synthesize_wiki(kg, _chunks(), llm=_StubLLM(), settings=s) == 0


def test_wiki_retriever_matches_entity(tmp_path):
    from auralynq.wiki.retriever import WikiRetriever

    store = WikiStore(tmp_path / "w")
    store.write_page("auralynq", title="Auralynq",
                     body="## Summary\nAuralynq fuses dense and sparse vectors [1][2].",
                     sources=["a.md"], mentions=3)
    store.write_page("france", title="France", body="Country in Europe [1].", mentions=2)

    res = WikiRetriever(tmp_path / "w").retrieve("Tell me about Auralynq", k=2)
    assert res.chunks, "matched the Auralynq page"
    top = res.chunks[0]
    assert top.method == "wiki"
    assert top.chunk.source == "Auralynq (wiki)"
    # Internal [n] markers are stripped so they don't clash with answer citations.
    assert "[1]" not in top.chunk.text and "[2]" not in top.chunk.text
    assert "fuses dense and sparse" in top.chunk.text


def test_wiki_retriever_no_match_is_empty(tmp_path):
    from auralynq.wiki.retriever import WikiRetriever

    store = WikiStore(tmp_path / "w")
    store.write_page("france", title="France", body="A country.", mentions=2)
    res = WikiRetriever(tmp_path / "w").retrieve("quantum chromodynamics gluons", k=2)
    assert res.chunks == []


# ---------------------------------------------------------- Phase 3 --------
def test_detect_contradictions_parses_json():
    from auralynq.wiki.contradiction import detect_contradictions

    class J:
        def generate(self, p, *, system=None, temperature=None, max_tokens=None):
            return 'noise [{"old_claim":"X is blue","new_claim":"X is red","why":"color"}] trailing'

    out = detect_contradictions("X", "X is blue.", "X is red.", J())
    assert len(out) == 1
    assert out[0].old_claim == "X is blue" and out[0].new_claim == "X is red"
    assert out[0].entity == "X"


def test_detect_contradictions_none_and_missing_side():
    from auralynq.wiki.contradiction import detect_contradictions

    class E:
        def generate(self, p, *, system=None, temperature=None, max_tokens=None):
            return "[]"

    assert detect_contradictions("X", "a", "b", E()) == []
    assert detect_contradictions("X", "", "b", E()) == []  # missing side → skip


class _DualStub:
    """Returns markdown for synthesis prompts, a JSON contradiction for the
    contradiction-detection prompt (distinguished by its system prompt)."""

    def generate(self, p, *, system=None, temperature=None, max_tokens=None):
        if system and "CONTRADICTIONS" in system:
            return '[{"old_claim":"Paris is small","new_claim":"Paris is large","why":"size"}]'
        return "Paris is a city [1]."


def test_contradiction_flagged_on_page_update(tmp_path):
    s = Settings(data_dir=tmp_path)
    s.wiki.enabled = True
    s.wiki.min_mentions = 1
    llm = _DualStub()
    synthesize_wiki(build_from_chunks(_chunks()), _chunks(), llm=llm, settings=s)  # first pass
    # Second pass adds a NEW source about Paris → contradiction check fires only
    # when new evidence appears (re-synthesizing the same sources must NOT flag).
    extra = _chunks() + [
        Chunk(id="c9", doc_id="d2", ordinal=0, source="new.txt", source_type=SourceType.text,
              text="Paris is a major capital city in France."),
    ]
    synthesize_wiki(build_from_chunks(extra), extra, llm=llm, settings=s)

    store = WikiStore(s.wiki_dir)
    paris = store.read_page("paris")
    assert "Contradictions flagged" in paris["markdown"]
    report = store.lint()
    assert report["contradiction_count"] >= 1
    assert any(c["entity"] == "paris" for c in report["contradictions"])
    assert (tmp_path / "storage" / "wiki_pages" / "_log.jsonl").exists()


def test_no_contradiction_when_sources_unchanged(tmp_path):
    # Re-synthesizing the exact same sources must NOT flag contradictions (only
    # new evidence can contradict) — guards against reword false-positives.
    s = Settings(data_dir=tmp_path)
    s.wiki.enabled = True
    s.wiki.min_mentions = 1
    llm = _DualStub()
    synthesize_wiki(build_from_chunks(_chunks()), _chunks(), llm=llm, settings=s)
    synthesize_wiki(build_from_chunks(_chunks()), _chunks(), llm=llm, settings=s)  # same sources
    report = WikiStore(s.wiki_dir).lint()
    assert report["contradiction_count"] == 0


def test_lint_orphans(tmp_path):
    store = WikiStore(tmp_path / "w")
    store.write_page("a", title="A", body="Links to [[B]].", mentions=1)
    store.write_page("b", title="B", body="No links here.", mentions=1)
    report = store.lint()
    assert "a" in report["orphan_pages"]  # nobody links to A
    assert "b" not in report["orphan_pages"]  # A links to B


# --------------------------------------------------------- Phase 3b -------
def test_file_answer_creates_answer_page(tmp_path):
    from auralynq.wiki.generator import file_answer

    s = Settings(data_dir=tmp_path)
    s.wiki.enabled = True
    ok = file_answer(
        "What is Auralynq?",
        "Auralynq is a local-first RAG platform [1].",
        [{"source": "a.md", "locator": "p.1"}],
        0.8,
        settings=s,
    )
    assert ok
    store = WikiStore(s.wiki_dir)
    answers = [p for p in store.list_pages() if p["type"] == "answer"]
    assert len(answers) == 1
    page = store.read_page(answers[0]["id"])
    assert "Auralynq is a local-first RAG platform" in page["markdown"]
    assert "## Sources" in page["markdown"]
    assert "a.md" in page["markdown"]


def test_file_answer_gates(tmp_path):
    from auralynq.wiki.generator import file_answer

    s = Settings(data_dir=tmp_path)
    s.wiki.enabled = True
    assert file_answer("q", "ans", [{"source": "a"}], 0.1, settings=s) is False  # low conf
    assert file_answer("q", "ans", [], 0.9, settings=s) is False  # no citations
    assert file_answer("q", "", [{"source": "a"}], 0.9, settings=s) is False  # empty answer
    s.wiki.file_answers = False
    assert file_answer("q", "ans", [{"source": "a"}], 0.9, settings=s) is False  # disabled


def test_file_answer_is_idempotent_by_question(tmp_path):
    from auralynq.wiki.generator import file_answer

    s = Settings(data_dir=tmp_path)
    s.wiki.enabled = True
    file_answer("Same question?", "First answer [1].", [{"source": "a"}], 0.9, settings=s)
    file_answer("Same question?", "Updated answer [1].", [{"source": "a"}], 0.9, settings=s)
    store = WikiStore(s.wiki_dir)
    answers = [p for p in store.list_pages() if p["type"] == "answer"]
    assert len(answers) == 1  # same question → same page, updated in place


def test_contradiction_has_flagged_at():
    from auralynq.wiki.contradiction import Contradiction

    c = Contradiction("e", "old", "new")
    assert len(c.flagged_at) >= 10  # ISO timestamp
    assert "flagged_at" in c.to_dict()
