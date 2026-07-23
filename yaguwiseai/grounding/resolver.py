"""Grounding resolver: maps answer citations to source page regions.

Input: answer, citations, retrieved chunks with visual_grounding metadata.
Output: per-citation VisualEvidence records and per-claim grounding status.

The resolver operates in stages:
  1. span-level: if chunk has bbox metadata, use it directly
  2. page-level fallback: no bbox, but page number is known
  3. unavailable: no page info at all

This is deterministic and fast (<5ms typical). No LLM calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class VisualEvidence:
    citation_id: str  # matches citation marker (str of int, e.g. "1")
    chunk_id: str
    doc_id: str
    source_title: str
    page: int | None
    bbox: list[float] | None  # [x0, y0, x1, y1] in PDF space
    normalized_bbox: list[float] | None  # [0..1] relative to page  (Eq. 11)
    color_index: int  # for CSS color-coding by citation number
    snippet: str
    support_type: str  # span | page | segment | unavailable | graph
    # "segment" = audio timestamp grounding (Eq. 1)
    relevance: float  # retrieval score 0-1
    confidence: float  # chunk visual grounding confidence
    block_type: str
    grounding_version: int
    reindex_required: bool  # True if doc was indexed before visual grounding
    # Audio-specific grounding (paper §4.5, Eq. 1: g_c = (t_start, t_end) in R+^2)
    t_start: float | None = None
    t_end: float | None = None
    speaker: str | None = None


@dataclass
class ClaimGrounding:
    claim_id: str
    text: str
    citation_ids: list[str]
    support_status: str  # supported | partial | weak | unsupported
    visual_evidence_ids: list[str]
    confidence: float


@dataclass
class GroundingResult:
    answer_id: str
    doc_id: str
    source_title: str
    page: int | None
    page_image_url: str
    highlights: list[VisualEvidence]
    claim_grounding: list[ClaimGrounding]
    warnings: list[str]
    visual_grounding_available: bool
    grounding_stage: str  # span | page | unavailable


def _split_claims(answer: str) -> list[str]:
    """Split answer into sentence-level claims."""
    sentences = re.split(r"(?<=[.!?])\s+", answer.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 20]


def _citation_ids_for_claim(claim: str, citations: list[dict[str, Any]]) -> list[str]:
    """Find citation markers referenced in a claim (e.g. [1], [2])."""
    ids: list[str] = []
    for c in citations:
        marker = str(c.get("marker", ""))
        if f"[{marker}]" in claim or f"[{marker} " in claim:
            ids.append(marker)
    # If no explicit markers, assign citations whose chunk text overlaps with claim
    if not ids:
        claim_lower = claim.lower()
        for c in citations:
            chunk_text = (c.get("_chunk_text", "") or "").lower()
            if chunk_text and len(chunk_text) > 10:
                words = claim_lower.split()[:8]
                if any(w in chunk_text for w in words if len(w) > 4):
                    ids.append(str(c.get("marker", "")))
    return list(dict.fromkeys(ids))  # deduplicate, preserve order


def _support_status(claim: str, citation_ids: list[str], evidence: list[VisualEvidence]) -> str:
    if not citation_ids:
        return "unsupported"
    matched = [e for e in evidence if e.citation_id in citation_ids]
    if not matched:
        return "unsupported"
    max_relevance = max(e.relevance for e in matched)
    span_count = sum(1 for e in matched if e.support_type == "span")
    if span_count > 0 and max_relevance >= 0.6:
        return "supported"
    if max_relevance >= 0.4:
        return "partial"
    return "weak"


class GroundingResolver:
    """Resolve citation → visual evidence given retrieved chunk metadata."""

    def resolve(
        self,
        answer_id: str,
        answer: str,
        citations: list[dict[str, Any]],
        base_url: str = "/api",
    ) -> list[GroundingResult]:
        """Return one GroundingResult per unique (doc_id, page) pair."""
        if not citations:
            return []

        # Group citations by (doc_id, page)
        groups: dict[tuple[str, int | None], list[dict[str, Any]]] = {}
        for c in citations:
            vg = c.get("visual_grounding") or {}
            doc_id = c.get("doc_id", "")
            page = vg.get("page") or c.get("page")
            key = (doc_id, page)
            groups.setdefault(key, []).append(c)

        claims = _split_claims(answer)
        results: list[GroundingResult] = []

        for (doc_id, page), group_cits in groups.items():
            highlights: list[VisualEvidence] = []
            warnings: list[str] = []
            grounding_stage = "unavailable"
            has_visual_grounding = False

            for c in group_cits:
                vg = c.get("visual_grounding") or {}
                gv = vg.get("grounding_version", 0)
                reindex_required = gv < 1
                has_bbox = vg.get("has_bbox", False)
                normalized_bbox = vg.get("normalized_bbox") if has_bbox else None
                bbox = vg.get("bbox") if has_bbox else None

                # Audio timestamp grounding — paper §4.5, Eq. 1:
                # g_c = (t_start, t_end) in R+^2 for WAV/MP3/M4A chunks.
                is_audio = vg.get("source_modality") == "audio" or (
                    c.get("source_type") == "audio" and c.get("start_s") is not None
                )
                t_start: float | None = vg.get("t_start") or c.get("start_s")
                t_end: float | None = vg.get("t_end") or c.get("end_s")
                speaker: str | None = vg.get("speaker") or c.get("speaker")

                if has_bbox and normalized_bbox:
                    stage = "span"
                    has_visual_grounding = True
                elif is_audio and t_start is not None:
                    # Segment-level audio grounding: timestamp interval is known
                    stage = "segment"
                    has_visual_grounding = True
                elif page is not None:
                    stage = "page"
                    has_visual_grounding = True
                    if not reindex_required:
                        warnings.append("Exact span unavailable; showing supporting page.")
                else:
                    stage = "unavailable"
                    if reindex_required:
                        warnings.append(
                            "This document was indexed before visual grounding metadata "
                            "was available. Reindex to enable source highlights."
                        )
                    else:
                        warnings.append("Visual grounding metadata not available for this chunk.")

                grounding_stage = stage if stage != "unavailable" else grounding_stage

                marker = str(c.get("marker", ""))
                ev = VisualEvidence(
                    citation_id=marker,
                    chunk_id=c.get("chunk_id", ""),
                    doc_id=doc_id,
                    source_title=c.get("source", "") or c.get("title", ""),
                    page=page,
                    bbox=bbox,
                    normalized_bbox=normalized_bbox,
                    color_index=c.get("marker", 1),
                    snippet=c.get("_snippet", "") or c.get("locator", ""),
                    support_type=stage,
                    relevance=float(c.get("score") or 0.0),
                    confidence=float(vg.get("confidence", 1.0)),
                    block_type=vg.get("block_type", "paragraph"),
                    grounding_version=gv,
                    reindex_required=reindex_required,
                    t_start=t_start,
                    t_end=t_end,
                    speaker=speaker,
                )
                highlights.append(ev)

            # Build claim grounding
            claim_groundings: list[ClaimGrounding] = []
            for ci, claim_text in enumerate(claims):
                cit_ids = _citation_ids_for_claim(claim_text, group_cits)
                status = _support_status(claim_text, cit_ids, highlights)
                ev_ids = [e.citation_id for e in highlights if e.citation_id in cit_ids]
                claim_groundings.append(
                    ClaimGrounding(
                        claim_id=f"claim_{ci}",
                        text=claim_text,
                        citation_ids=cit_ids,
                        support_status=status,
                        visual_evidence_ids=ev_ids,
                        confidence=max(
                            (e.relevance for e in highlights if e.citation_id in cit_ids),
                            default=0.0,
                        ),
                    )
                )

            page_image_url = (
                f"{base_url}/documents/{doc_id}/pages/{page}/image"
                if page is not None and doc_id
                else ""
            )
            source_title = group_cits[0].get("source", "") if group_cits else ""

            results.append(
                GroundingResult(
                    answer_id=answer_id,
                    doc_id=doc_id,
                    source_title=source_title,
                    page=page,
                    page_image_url=page_image_url,
                    highlights=highlights,
                    claim_grounding=claim_groundings,
                    warnings=list(dict.fromkeys(warnings)),
                    visual_grounding_available=has_visual_grounding,
                    grounding_stage=grounding_stage,
                )
            )

        return results

    def to_api_response(
        self,
        results: list[GroundingResult],
    ) -> dict:
        """Serialize grounding results for the API response."""
        all_highlights = []
        all_claims = []
        warnings = []

        for r in results:
            for ev in r.highlights:
                all_highlights.append(
                    {
                        "citation_id": ev.citation_id,
                        "chunk_id": ev.chunk_id,
                        "doc_id": ev.doc_id,
                        "source_title": ev.source_title,
                        "page": ev.page,
                        "page_image_url": r.page_image_url,
                        "bbox": ev.bbox,
                        "normalized_bbox": ev.normalized_bbox,
                        "color_index": ev.color_index,
                        "snippet": ev.snippet,
                        "support_type": ev.support_type,
                        "relevance": ev.relevance,
                        "confidence": ev.confidence,
                        "block_type": ev.block_type,
                        "grounding_version": ev.grounding_version,
                        "reindex_required": ev.reindex_required,
                        # audio grounding fields (paper §4.5, Eq. 1)
                        "t_start": ev.t_start,
                        "t_end": ev.t_end,
                        "speaker": ev.speaker,
                    }
                )
            for cg in r.claim_grounding:
                all_claims.append(
                    {
                        "claim_id": cg.claim_id,
                        "text": cg.text,
                        "citation_ids": cg.citation_ids,
                        "support_status": cg.support_status,
                        "visual_evidence_ids": cg.visual_evidence_ids,
                        "confidence": cg.confidence,
                    }
                )
            warnings.extend(r.warnings)

        return {
            "highlights": all_highlights,
            "claim_grounding": all_claims,
            "warnings": list(dict.fromkeys(warnings)),
            "visual_grounding_available": any(r.visual_grounding_available for r in results),
            "grounding_stage": next(
                (r.grounding_stage for r in results if r.grounding_stage != "unavailable"),
                "unavailable",
            ),
        }
