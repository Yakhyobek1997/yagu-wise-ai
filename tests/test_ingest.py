from __future__ import annotations

import json
import wave

from auralynq.ingest.chunking import chunk_text
from auralynq.ingest.models import SourceType
from auralynq.ingest.pipeline import ingest_path


def test_chunking_preserves_spans():
    text = "First sentence here. Second sentence follows. Third one closes it out."
    chunks = chunk_text(text, target_chars=30, overlap_sentences=0)
    assert len(chunks) >= 2
    for c in chunks:
        assert text[c.start_char : c.end_char].strip().startswith(c.text[:10].strip()[:5])


def test_ingest_directory_text(corpus_dir):
    result = ingest_path(corpus_dir)
    assert result.n_documents == 2
    assert result.n_chunks >= 2
    types = {d.source_type for d in result.documents}
    assert SourceType.markdown in types
    # spans must be valid
    for doc in result.documents:
        for ch in doc.chunks:
            assert ch.span.end_char >= ch.span.start_char
            assert ch.text


def test_ingest_is_idempotent(corpus_dir):
    first = ingest_path(corpus_dir)
    second = ingest_path(corpus_dir)
    assert first.n_documents == 2
    assert second.n_documents == 0
    assert second.n_skipped == 2


def test_ingest_audio_with_sidecar(tmp_path):
    audio = tmp_path / "talk.wav"
    with wave.open(str(audio), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 16000)
    sidecar = tmp_path / "talk.transcript.json"
    sidecar.write_text(
        json.dumps(
            {
                "language": "en",
                "segments": [
                    {
                        "start_s": 0.0,
                        "end_s": 2.0,
                        "text": "Paris is the capital of France.",
                        "speaker": "SPEAKER_00",
                    },
                    {
                        "start_s": 2.5,
                        "end_s": 4.0,
                        "text": "It sits on the Seine.",
                        "speaker": "SPEAKER_01",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    result = ingest_path(tmp_path)
    assert result.n_documents == 1
    doc = result.documents[0]
    assert doc.source_type is SourceType.audio
    assert doc.chunks[0].audio is not None
    assert doc.chunks[0].audio.speaker == "SPEAKER_00"
    loc = doc.chunks[0].locator()
    assert "SPEAKER_00" in loc and "0:00" in loc
