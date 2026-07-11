"""Document parsers → plain text with page/section structure preserved.

Text/Markdown/HTML parse with zero heavy deps. PDF parsing uses pdfplumber as
the primary extractor (layout blocks + text in one pass, with exact character
offsets so chunk↔bbox matching is precise), falling back to pypdf when
pdfplumber is not installed.

Why one-pass pdfplumber?
  The old approach extracted text via pypdf and layout via pdfplumber separately.
  Because the two extractors produce slightly different character sequences, any
  block↔chunk matching based on text containment becomes unreliable — every
  short line is a substring of a large chunk, so ALL blocks on the page matched,
  and the highlighted bbox covered the whole page.  The fix: use pdfplumber for
  BOTH text and layout so that every layout block carries exact doc_char_start /
  doc_char_end offsets into the same text string that the chunker will split.
  pipeline.py then matches by character-span overlap — precise by construction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from auralynq.ingest.models import SourceType
from auralynq.utils import normalize_text

_EXT_MAP = {
    ".pdf": SourceType.pdf,
    ".docx": SourceType.docx,
    ".html": SourceType.html,
    ".htm": SourceType.html,
    ".md": SourceType.markdown,
    ".markdown": SourceType.markdown,
    ".txt": SourceType.text,
    ".text": SourceType.text,
    ".rst": SourceType.text,
}
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}


@dataclass
class ParsedDoc:
    text: str
    source_type: SourceType
    title: str | None = None
    language: str = "en"
    # (page_number, start_char, end_char) for PDFs; empty otherwise.
    pages: list[tuple[int, int, int]] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def page_for(self, start_char: int) -> int | None:
        for page, lo, hi in self.pages:
            if lo <= start_char < hi:
                return page
        return None


def detect_type(path: Path) -> SourceType:
    if path.suffix.lower() in AUDIO_EXTS:
        return SourceType.audio
    return _EXT_MAP.get(path.suffix.lower(), SourceType.unknown)


def parse_document(path: Path) -> ParsedDoc:
    st = detect_type(path)
    if st is SourceType.pdf:
        return _parse_pdf(path)
    if st is SourceType.docx:
        return _parse_docx(path)
    if st is SourceType.html:
        return _parse_html(path)
    if st in (SourceType.markdown, SourceType.text, SourceType.unknown):
        return _parse_text(path, st if st is not SourceType.unknown else SourceType.text)
    raise ValueError(f"Unsupported document type for parsing: {path}")


def _parse_text(path: Path, st: SourceType) -> ParsedDoc:
    raw = path.read_text(encoding="utf-8", errors="replace")
    title = _first_heading(raw) or path.stem
    return ParsedDoc(text=normalize_text(raw), source_type=st, title=title)


def _parse_html(path: Path) -> ParsedDoc:
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        title = (soup.title.string if soup.title else None) or path.stem
        text = soup.get_text("\n")
    except ImportError:
        title = path.stem
        text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return ParsedDoc(text=normalize_text(text), source_type=SourceType.html, title=title)


# ─── PDF parsing ─────────────────────────────────────────────────────────────


def _cluster_words_to_lines(words: list[dict]) -> list[list[dict]]:
    """Group pdfplumber word dicts into reading-order lines.

    Words with the same rounded `top` value (±5 pt tolerance) are on the same
    line.  Within a line, words are sorted left-to-right by x0.
    """
    lines: list[list[dict]] = []
    cur_line: list[dict] = []
    last_y: int | None = None
    for word in sorted(words, key=lambda w: (round(w["top"] / 5), w["x0"])):
        y_key = round(word["top"] / 5)
        if last_y is not None and y_key != last_y:
            if cur_line:
                lines.append(cur_line)
            cur_line = []
        cur_line.append(word)
        last_y = y_key
    if cur_line:
        lines.append(cur_line)
    return lines


def _parse_pdf(path: Path) -> ParsedDoc:
    """Parse a PDF.

    Primary path: pdfplumber — single pass that produces both the document
    text AND layout blocks (bbox + exact char offsets).  This guarantees that
    the character spans stored on each layout block refer to the same string
    that the chunker will split, so chunk↔block matching in pipeline.py can
    use span overlap instead of unreliable text containment.

    Fallback: pypdf — plain text extraction, no layout blocks.
    """
    result = _parse_pdf_pdfplumber(path)
    if result is not None:
        return result
    return _parse_pdf_pypdf(path)


def _parse_pdf_pdfplumber(path: Path) -> ParsedDoc | None:
    """One-pass PDF parse via pdfplumber with character-offset-tracked layout blocks."""
    try:
        import pdfplumber  # type: ignore[import-untyped]
    except ImportError:
        return None

    try:
        layout_blocks: list[dict] = []
        page_dims: list[dict] = []
        page_ranges: list[tuple[int, int, int]] = []

        # We build the full document text character by character.
        # cursor tracks the write position in the character array.
        # Separators:
        #   between lines on the same page  → 1 "\n"  (cursor += 1)
        #   between pages                   → 2 "\n\n" (cursor += 2)
        # This means layout_block.doc_char_start / doc_char_end are positions
        # in the *final* character array, not in any intermediate string.
        char_buf: list[str] = []  # built incrementally
        cursor = 0

        with pdfplumber.open(str(path)) as pdf:
            meta = pdf.metadata or {}
            raw_title = meta.get("Title") if meta else None
            title = str(raw_title or path.stem)[:120]

            for page_num, page in enumerate(pdf.pages, start=1):
                w = float(page.width or 612)
                h = float(page.height or 792)
                page_dims.append({"page": page_num, "width": w, "height": h})

                words = page.extract_words(x_tolerance=3, y_tolerance=3) or []
                if not words:
                    continue

                lines = _cluster_words_to_lines(words)
                page_start = cursor
                first_on_page = True

                for order, line_words in enumerate(lines):
                    if not line_words:
                        continue
                    raw_text = " ".join(wd["text"] for wd in line_words)
                    text = normalize_text(raw_text)
                    if not text:
                        continue

                    # Insert line separator (not before the first line on the page)
                    if not first_on_page:
                        char_buf.append("\n")
                        cursor += 1
                    first_on_page = False

                    x0 = min(wd["x0"] for wd in line_words)
                    y0 = min(wd["top"] for wd in line_words)
                    x1 = max(wd["x1"] for wd in line_words)
                    y1 = max(wd["bottom"] for wd in line_words)

                    char_start = cursor
                    char_end = cursor + len(text)
                    char_buf.append(text)
                    cursor = char_end

                    layout_blocks.append(
                        {
                            "page": page_num,
                            "bbox": [x0, y0, x1, y1],
                            "normalized_bbox": [x0 / w, y0 / h, x1 / w, y1 / h],
                            "text": text,
                            "block_type": "paragraph",
                            "reading_order": order,
                            "page_width": w,
                            "page_height": h,
                            "confidence": 1.0,
                            "doc_char_start": char_start,
                            "doc_char_end": char_end,
                        }
                    )

                if not first_on_page:
                    # Page had content — record its range and add page separator
                    page_end = cursor
                    # Include the coming "\n\n" separator in this page's range so
                    # page_for() returns the correct page even for chars in the gap.
                    page_ranges.append((page_num, page_start, page_end + 2))
                    char_buf.append("\n\n")
                    cursor += 2

        if not layout_blocks:
            return None

        full_text = "".join(char_buf).strip()
        if not full_text:
            return None

        return ParsedDoc(
            text=full_text,
            source_type=SourceType.pdf,
            title=title,
            pages=page_ranges,
            metadata={
                "n_pages": len(page_dims),
                "page_dimensions": page_dims,
                "layout_blocks": layout_blocks,
                "has_layout_blocks": True,
            },
        )
    except Exception:
        return None


def _parse_pdf_pypdf(path: Path) -> ParsedDoc:
    """Fallback PDF parser using pypdf — plain text, no layout blocks."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts: list[str] = []
    pages: list[tuple[int, int, int]] = []
    page_dims: list[dict] = []
    cursor = 0
    for i, page in enumerate(reader.pages, start=1):
        text = normalize_text(page.extract_text() or "")
        mb = page.mediabox
        w = float(mb.width) if mb else 612.0
        h = float(mb.height) if mb else 792.0
        page_dims.append({"page": i, "width": w, "height": h})
        if not text:
            continue
        parts.append(text)
        start = cursor
        cursor += len(text) + 2  # account for "\n\n" join
        pages.append((i, start, cursor))
    full = "\n\n".join(parts)
    meta: object = reader.metadata or {}
    title = getattr(meta, "title", None) or path.stem

    return ParsedDoc(
        text=full,
        source_type=SourceType.pdf,
        title=str(title),
        pages=pages,
        metadata={
            "n_pages": len(reader.pages),
            "page_dimensions": page_dims,
            "layout_blocks": [],
            "has_layout_blocks": False,
        },
    )


def _parse_docx(path: Path) -> ParsedDoc:
    import docx

    document = docx.Document(str(path))
    paras = [p.text for p in document.paragraphs]
    text = normalize_text("\n\n".join(p for p in paras if p.strip()))
    title = next((p for p in paras if p.strip()), path.stem)
    return ParsedDoc(text=text, source_type=SourceType.docx, title=title[:120])


_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+)$", re.MULTILINE)


def _first_heading(text: str) -> str | None:
    m = _HEADING_RE.search(text)
    return m.group(1).strip() if m else None
