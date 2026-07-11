"""Tests for Source Workspace backend endpoints and schema."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from auralynq.serving.app import create_app

    return TestClient(create_app())


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


def test_page_layout_block_schema():
    from auralynq.serving.schemas import PageLayoutBlock

    blk = PageLayoutBlock(
        block_id="chunk_001",
        page=1,
        bbox=[10.0, 20.0, 300.0, 80.0],
        normalized_bbox=[0.01, 0.02, 0.30, 0.08],
        text="Hello world this is a test paragraph.",
        block_type="paragraph",
        chunk_id="chunk_001",
        relevance=0.85,
        confidence=0.9,
        is_cited=True,
        citation_ids=["1"],
    )
    assert blk.page == 1
    assert blk.block_type == "paragraph"
    assert len(blk.normalized_bbox) == 4
    assert blk.is_cited is True


def test_page_layout_response_schema():
    from auralynq.serving.schemas import PageLayoutBlock, PageLayoutResponse

    resp = PageLayoutResponse(
        doc_id="abc123",
        page=2,
        blocks=[
            PageLayoutBlock(
                block_id="c1",
                page=2,
                bbox=[0, 0, 100, 50],
                normalized_bbox=[0.0, 0.0, 0.5, 0.1],
                text="Test block",
                block_type="title",
                chunk_id="c1",
            )
        ],
        source_title="My PDF",
        page_width=612.0,
        page_height=792.0,
    )
    assert resp.doc_id == "abc123"
    assert len(resp.blocks) == 1
    assert resp.blocks[0].block_type == "title"
    assert resp.page_width == 612.0


# ---------------------------------------------------------------------------
# Endpoint: document page layout
# ---------------------------------------------------------------------------


def test_page_layout_invalid_doc_id(client):
    """Invalid doc_id format returns 400."""
    r = client.get("/documents/../etc/passwd/pages/1/layout")
    assert r.status_code in (400, 404, 422)


def test_page_layout_invalid_page_number(client):
    """Page number 0 or very large returns 400."""
    r = client.get("/documents/abcdef1234567890abcdef1234567890/pages/0/layout")
    assert r.status_code == 400
    r2 = client.get("/documents/abcdef1234567890abcdef1234567890/pages/10000/layout")
    assert r2.status_code == 400


def test_page_layout_empty_corpus(client):
    """Layout endpoint on unknown doc returns empty blocks (not 500)."""
    r = client.get("/documents/abcdef1234567890abcdef1234567890/pages/1/layout")
    # Should succeed with empty blocks (doc not found → empty meta)
    assert r.status_code == 200
    data = r.json()
    assert "blocks" in data
    assert isinstance(data["blocks"], list)
    assert data["doc_id"] == "abcdef1234567890abcdef1234567890"
    assert data["page"] == 1


def test_page_layout_response_structure(client):
    """Layout response has all required fields."""
    r = client.get("/documents/abcdef1234567890abcdef1234567890/pages/1/layout")
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) >= {
        "doc_id",
        "page",
        "blocks",
        "source_title",
        "page_width",
        "page_height",
    }


# ---------------------------------------------------------------------------
# Endpoint: document pages (existing, smoke test)
# ---------------------------------------------------------------------------


def test_document_pages_unknown_doc(client):
    """Pages endpoint returns a valid response for unknown doc."""
    r = client.get("/documents/abcdef1234567890abcdef1234567890/pages")
    assert r.status_code == 200
    data = r.json()
    assert "pages" in data
    assert data["n_pages"] == 0


# ---------------------------------------------------------------------------
# Endpoint: grounding-status
# ---------------------------------------------------------------------------


def test_grounding_status_unknown_doc(client):
    """Grounding status returns a valid response structure for unknown doc."""
    r = client.get("/documents/abcdef1234567890abcdef1234567890/grounding-status")
    assert r.status_code == 200
    data = r.json()
    assert "grounding_available" in data
    assert "reindex_required" in data
    assert data["reindex_required"] is True


# ---------------------------------------------------------------------------
# Endpoint: corpus grounding summary
# ---------------------------------------------------------------------------


def test_corpus_grounding_summary(client):
    """Grounding summary returns enabled flag and document counts."""
    r = client.get("/corpus/grounding-summary")
    assert r.status_code == 200
    data = r.json()
    assert "enabled" in data
    assert "total_docs" in data
    assert "grounded_docs" in data
    assert "needs_reindex" in data


# ---------------------------------------------------------------------------
# Endpoint: visual grounding settings
# ---------------------------------------------------------------------------


def test_visual_grounding_settings(client):
    """Settings endpoint returns render configuration."""
    r = client.get("/visual-grounding/settings")
    assert r.status_code == 200
    data = r.json()
    assert "enabled" in data
    assert "render_dpi" in data
    assert "max_cached_pages" in data


# ---------------------------------------------------------------------------
# Security: no internal paths in layout response
# ---------------------------------------------------------------------------


def test_layout_no_internal_paths(client):
    """Layout response body must not expose filesystem paths."""
    r = client.get("/documents/abcdef1234567890abcdef1234567890/pages/1/layout")
    assert r.status_code == 200
    body = r.text
    for sensitive in ["/home/", "/var/", "/etc/", "storage_dir", "page_cache"]:
        assert sensitive not in body, f"Found internal path '{sensitive}' in response"


# ---------------------------------------------------------------------------
# Resolver: claim grounding analysis
# ---------------------------------------------------------------------------


def test_resolver_span_level_grounding():
    """Citation with bbox → span-level grounding stage."""
    from auralynq.grounding.resolver import GroundingResolver

    resolver = GroundingResolver()
    citations = [
        {
            "marker": 1,
            "source": "test.pdf",
            "doc_id": "doc_abc",
            "page": 2,
            "visual_grounding": {
                "grounding_version": 1,
                "page": 2,
                "has_bbox": True,
                "bbox": [50.0, 100.0, 400.0, 150.0],
                "normalized_bbox": [0.08, 0.13, 0.65, 0.19],
                "block_type": "paragraph",
            },
            "score": 0.88,
            "_snippet": "This is the cited text.",
        }
    ]
    results = resolver.resolve("ans_1", "The document states [1] this fact.", citations)
    assert len(results) == 1
    assert results[0].grounding_stage == "span"
    assert results[0].visual_grounding_available is True
    assert results[0].highlights[0].support_type == "span"
    assert results[0].highlights[0].normalized_bbox is not None


def test_resolver_page_level_fallback():
    """Citation with page but no bbox → page-level grounding."""
    from auralynq.grounding.resolver import GroundingResolver

    resolver = GroundingResolver()
    citations = [
        {
            "marker": 1,
            "source": "test.pdf",
            "doc_id": "doc_xyz",
            "page": 3,
            "visual_grounding": {
                "grounding_version": 1,
                "page": 3,
                "has_bbox": False,
            },
            "score": 0.75,
        }
    ]
    results = resolver.resolve("ans_2", "The answer is [1] here.", citations)
    assert len(results) == 1
    assert results[0].grounding_stage == "page"
    assert results[0].visual_grounding_available is True
    assert results[0].highlights[0].support_type == "page"


def test_resolver_to_api_response():
    """to_api_response produces the expected dict structure."""
    from auralynq.grounding.resolver import GroundingResolver

    resolver = GroundingResolver()
    citations = [
        {
            "marker": 1,
            "source": "doc.pdf",
            "doc_id": "doc_001",
            "page": 1,
            "visual_grounding": {
                "grounding_version": 1,
                "page": 1,
                "has_bbox": True,
                "bbox": [0, 0, 100, 50],
                "normalized_bbox": [0.0, 0.0, 0.5, 0.1],
                "block_type": "title",
            },
            "score": 0.9,
        }
    ]
    results = resolver.resolve("ans_3", "The title [1] says hello.", citations)
    api_resp = resolver.to_api_response(results)
    assert "highlights" in api_resp
    assert "claim_grounding" in api_resp
    assert "warnings" in api_resp
    assert "visual_grounding_available" in api_resp
    assert "grounding_stage" in api_resp
    assert api_resp["visual_grounding_available"] is True
    assert api_resp["grounding_stage"] == "span"
    assert len(api_resp["highlights"]) == 1
    h = api_resp["highlights"][0]
    assert h["citation_id"] == "1"
    assert h["block_type"] == "title"
    assert h["normalized_bbox"] == [0.0, 0.0, 0.5, 0.1]
