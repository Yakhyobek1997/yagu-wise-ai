"""Semantic + late chunking with preserved character spans.

Strategy:
* Split into sentences, then greedily pack sentences into chunks up to a target
  size with a sentence overlap (semantic chunking — never split mid-sentence).
* Track exact ``start_char``/``end_char`` offsets into the *original* text so
  citations point at real source spans.
* "Late chunking" (Günther et al., 2024): when enabled and the embedder supports
  long context, boundaries are aligned to section/paragraph breaks so that
  per-chunk embeddings benefit from surrounding context. Here we realise the
  span-alignment half of late chunking deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass

from auralynq.utils import sentence_split


@dataclass
class TextChunk:
    text: str
    start_char: int
    end_char: int
    section: str | None = None


def _locate(haystack: str, needle: str, start: int) -> int:
    idx = haystack.find(needle, start)
    return idx if idx >= 0 else start


def chunk_text(
    text: str,
    *,
    target_chars: int = 900,
    overlap_sentences: int = 1,
    section: str | None = None,
    late: bool = True,
) -> list[TextChunk]:
    """Pack sentences into span-tracked chunks."""
    if not text.strip():
        return []
    sentences = sentence_split(text)
    if not sentences:
        return [TextChunk(text=text.strip(), start_char=0, end_char=len(text), section=section)]

    # Resolve each sentence's offset in the original text (monotonic scan).
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for sent in sentences:
        start = _locate(text, sent, cursor)
        end = start + len(sent)
        offsets.append((start, end))
        cursor = end

    chunks: list[TextChunk] = []
    i = 0
    n = len(sentences)
    while i < n:
        buf: list[str] = []
        start_char = offsets[i][0]
        end_char = offsets[i][1]
        j = i
        while j < n:
            cand_len = offsets[j][1] - start_char
            if buf and cand_len > target_chars:
                break
            buf.append(sentences[j])
            end_char = offsets[j][1]
            j += 1
        chunk_text_str = text[start_char:end_char].strip()
        if late:
            # Late-chunking alignment: extend to the end of the current paragraph
            # if it is close, so the chunk is a coherent semantic unit.
            nl = text.find("\n\n", end_char)
            if 0 <= nl - end_char <= 80:
                end_char = nl
                chunk_text_str = text[start_char:end_char].strip()
        chunks.append(TextChunk(chunk_text_str, start_char, end_char, section))
        if j >= n:
            break
        i = max(j - overlap_sentences, i + 1)
    return chunks
