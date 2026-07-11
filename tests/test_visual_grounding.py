"""Tests for visual grounding infrastructure: resolver, ingest metadata, endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from auralynq.serving.app import create_app

    return TestClient(create_app())


# ---------------------------------------------------------------------------
# Grounding resolver unit tests
# ---------------------------------------------------------------------------


def test_resolver_returns_empty_for_no_citations():
    from auralynq.grounding.resolver import GroundingResolver

    resolver = GroundingResolver()
    results = resolver.resolve(answer_id="test", answer="Hello", citations=[])
    assert results == []


def test_resolver_page_level_grounding():
    """Citation with page number but no bbox → page-level grounding."""
    from auralynq.grounding.resolver import GroundingResolver

    resolver = GroundingResolver()
    citations = [
        {
            "marker": 1,
            "chunk_id": "chunk_001",
            "doc_id": "doc_001",
            "source": "test.pdf",
            "page": 3,
            "score": 0.8,
            "visual_grounding": {
                "grounding_version": 1,
                "page": 3,
                "has_bbox": False,
                "bbox": None,
                "normalized_bbox": None,
            },
        }
    ]
    results = resolver.resolve("test_id", "Some answer [1].", citations)
    assert len(results) == 1
    r = results[0]
    assert r.page == 3
    assert r.doc_id == "doc_001"
    assert r.visual_grounding_available is True
    assert r.grounding_stage == "page"
    assert len(r.highlights) == 1
    ev = r.highlights[0]
    assert ev.support_type == "page"
    assert ev.normalized_bbox is None
    assert ev.reindex_required is False


def test_resolver_span_level_grounding():
    """Citation with bbox → span-level grounding."""
    from auralynq.grounding.resolver import GroundingResolver

    resolver = GroundingResolver()
    citations = [
        {
            "marker": 1,
            "chunk_id": "chunk_002",
            "doc_id": "doc_002",
            "source": "paper.pdf",
            "page": 1,
            "score": 0.9,
            "visual_grounding": {
                "grounding_version": 1,
                "page": 1,
                "has_bbox": True,
                "bbox": [72.0, 100.0, 400.0, 120.0],
                "normalized_bbox": [0.1, 0.13, 0.55, 0.16],
                "block_type": "paragraph",
            },
        }
    ]
    results = resolver.resolve("span_test", "Answer with span [1].", citations)
    assert len(results) == 1
    r = results[0]
    assert r.grounding_stage == "span"
    ev = r.highlights[0]
    assert ev.support_type == "span"
    assert ev.normalized_bbox == [0.1, 0.13, 0.55, 0.16]
    assert ev.bbox == [72.0, 100.0, 400.0, 120.0]


def test_resolver_reindex_required_for_old_doc():
    """Citation with grounding_version=0 → reindex_required=True."""
    from auralynq.grounding.resolver import GroundingResolver

    resolver = GroundingResolver()
    citations = [
        {
            "marker": 1,
            "chunk_id": "old_chunk",
            "doc_id": "old_doc",
            "source": "legacy.pdf",
            "page": None,
            "score": 0.5,
            "visual_grounding": {
                "grounding_version": 0,
                "page": None,
                "has_bbox": False,
            },
        }
    ]
    results = resolver.resolve("old_test", "Answer.", citations)
    assert len(results) == 1
    ev = results[0].highlights[0]
    assert ev.reindex_required is True
    assert ev.support_type == "unavailable"


def test_resolver_to_api_response():
    """to_api_response produces correct structure."""
    from auralynq.grounding.resolver import GroundingResolver

    resolver = GroundingResolver()
    citations = [
        {
            "marker": 1,
            "chunk_id": "c1",
            "doc_id": "d1",
            "source": "doc.pdf",
            "page": 2,
            "score": 0.7,
            "visual_grounding": {
                "grounding_version": 1,
                "page": 2,
                "has_bbox": True,
                "bbox": [0, 0, 100, 20],
                "normalized_bbox": [0.0, 0.0, 0.14, 0.025],
            },
        }
    ]
    results = resolver.resolve("api_test", "The answer is X [1].", citations)
    api_resp = resolver.to_api_response(results)
    assert "highlights" in api_resp
    assert "claim_grounding" in api_resp
    assert "warnings" in api_resp
    assert isinstance(api_resp["visual_grounding_available"], bool)
    assert api_resp["visual_grounding_available"] is True
    assert api_resp["grounding_stage"] == "span"
    assert len(api_resp["highlights"]) == 1
    h = api_resp["highlights"][0]
    assert h["page_image_url"] == "/api/documents/d1/pages/2/image"


def test_resolver_page_image_url_format():
    from auralynq.grounding.resolver import GroundingResolver

    resolver = GroundingResolver()
    citations = [
        {
            "marker": 2,
            "chunk_id": "c2",
            "doc_id": "abc123",
            "source": "file.pdf",
            "page": 5,
            "score": 0.6,
            "visual_grounding": {"grounding_version": 1, "page": 5, "has_bbox": False},
        }
    ]
    results = resolver.resolve("url_test", "Answer.", citations)
    assert results[0].page_image_url == "/api/documents/abc123/pages/5/image"


def test_resolver_claim_grounding_unsupported_without_citations():
    from auralynq.grounding.resolver import GroundingResolver

    resolver = GroundingResolver()
    # Long answer sentences with no citations matching
    citations = [
        {
            "marker": 1,
            "chunk_id": "c3",
            "doc_id": "d3",
            "source": "x.pdf",
            "page": 1,
            "score": 0.5,
            "visual_grounding": {"grounding_version": 1, "page": 1, "has_bbox": False},
        }
    ]
    results = resolver.resolve(
        "claim_test", "This is a long answer sentence. [1] Another unrelated claim here.", citations
    )
    # Claim grounding should exist
    all_claims = [cg for r in results for cg in r.claim_grounding]
    assert len(all_claims) >= 1


# ---------------------------------------------------------------------------
# Ingest model tests
# ---------------------------------------------------------------------------


def test_visual_grounding_version_constant():
    from auralynq.ingest.models import VISUAL_GROUNDING_VERSION

    assert VISUAL_GROUNDING_VERSION == 1


def test_document_has_visual_grounding_property():
    from auralynq.ingest.models import Document, SourceType

    doc = Document(
        id="d1",
        source="test.pdf",
        source_type=SourceType.pdf,
        visual_grounding_version=1,
    )
    assert doc.has_visual_grounding is True

    doc_old = Document(
        id="d2",
        source="old.pdf",
        source_type=SourceType.pdf,
        visual_grounding_version=0,
    )
    assert doc_old.has_visual_grounding is False


def test_layout_block_model():
    from auralynq.ingest.models import LayoutBlock

    blk = LayoutBlock(
        page=1,
        bbox=[72.0, 100.0, 400.0, 120.0],
        normalized_bbox=[0.1, 0.13, 0.55, 0.16],
        text="Sample text",
        block_type="paragraph",
        reading_order=3,
        page_width=720.0,
        page_height=960.0,
    )
    assert blk.page == 1
    assert blk.block_type == "paragraph"
    assert blk.normalized_bbox[0] == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# Settings tests
# ---------------------------------------------------------------------------


def test_visual_grounding_settings_defaults():
    from auralynq.config.settings import VisualGroundingSettings

    vgs = VisualGroundingSettings()
    assert vgs.enabled is True
    assert vgs.page_rendering_enabled is True
    assert vgs.render_dpi == 144
    assert vgs.max_cached_pages == 500
    assert vgs.visual_retrieval_enabled is False
    assert vgs.metadata_version == 1


def test_settings_has_visual():
    import os

    os.environ["AURALYNQ_DOTENV_DISABLED"] = "1"
    from auralynq.config.settings import Settings

    s = Settings(_env_file=None)  # type: ignore
    assert hasattr(s, "visual")
    assert s.visual.enabled is True


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


def test_visual_grounding_settings_endpoint(client):
    resp = client.get("/visual-grounding/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data
    assert "page_rendering_enabled" in data
    assert "render_dpi" in data
    assert "metadata_version" in data


def test_document_pages_invalid_doc_id_returns_result(client):
    """Valid request format but unknown doc_id → empty result (not error)."""
    resp = client.get("/documents/abc123def456/pages")
    # Should return 200 with empty page list (doc not found = empty metadata)
    assert resp.status_code == 200
    data = resp.json()
    assert "doc_id" in data
    assert "pages" in data


def test_document_page_image_invalid_doc_id_rejected(client):
    """Path traversal attempt should be rejected."""
    resp = client.get("/documents/../etc/passwd/pages/1/image")
    # Either 400, 404, or the path is blocked by FastAPI routing
    assert resp.status_code in (400, 404, 422)


def test_document_page_image_bad_doc_id_rejected(client):
    """Doc ID with invalid chars should return 400."""
    resp = client.get("/documents/../../etc/pages/1/image")
    assert resp.status_code in (400, 404, 422)


def test_document_grounding_status_endpoint(client):
    resp = client.get("/documents/abc123def456/grounding-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "doc_id" in data
    assert "reindex_required" in data
    assert "grounding_available" in data


# ---------------------------------------------------------------------------
# Strategy registry: new experimental strategies
# ---------------------------------------------------------------------------


def test_self_rag_strategy_available():
    from auralynq.rag import get_registry

    registry = get_registry()
    strategies = registry.list_all()
    sr = next(s for s in strategies if s["id"] == "self_rag")
    assert sr["available"] is True
    assert sr["status"] == "experimental"


def test_crag_strategy_available():
    from auralynq.rag import get_registry

    registry = get_registry()
    strategies = registry.list_all()
    crag = next(s for s in strategies if s["id"] == "crag")
    assert crag["available"] is True
    assert crag["status"] == "experimental"


def test_adaptive_strategy_available():
    from auralynq.rag import get_registry

    registry = get_registry()
    strategies = registry.list_all()
    adaptive = next(s for s in strategies if s["id"] == "adaptive")
    assert adaptive["available"] is True
    assert adaptive["status"] == "experimental"


def test_lightrag_local_unavailable():
    from auralynq.rag import get_registry

    registry = get_registry()
    strategies = registry.list_all()
    lr = next(s for s in strategies if s["id"] == "lightrag_local")
    assert lr["available"] is False
    assert lr["unavailable_reason"] is not None


def test_raptor_unavailable():
    from auralynq.rag import get_registry

    registry = get_registry()
    strategies = registry.list_all()
    raptor = next(s for s in strategies if s["id"] == "raptor")
    assert raptor["available"] is False
    assert "hierarchical" in raptor["unavailable_reason"].lower()


def test_all_strategies_have_status_field():
    from auralynq.rag import get_registry

    registry = get_registry()
    for s in registry.list_all():
        assert s["status"] in ("available", "experimental", "planned"), f"{s['id']} has bad status"
