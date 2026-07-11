from __future__ import annotations

import json
import wave

import numpy as np
import pytest
from auralynq.pipeline import build_index
from auralynq.voice.tts import NullTTS
from auralynq.voice.vad import detect_speech


def _write_wav(path, seconds=1.0, sr=16000):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(b"\x00\x00" * int(sr * seconds))


def test_null_tts_writes_real_wav(tmp_path):
    out = tmp_path / "out.wav"
    res = NullTTS().synthesize("hello world this is auralynq", out)
    assert out.exists()
    with wave.open(str(out), "rb") as wf:
        assert wf.getnframes() > 0
    assert res.provider == "null"


def test_energy_vad_detects_active_region():
    sr = 16000
    silence = np.zeros(sr, dtype=np.float32)
    speech = (np.random.RandomState(0).randn(sr) * 0.3).astype(np.float32)
    samples = np.concatenate([silence, speech, silence])
    regions = detect_speech(samples, sr)
    assert regions
    # the active region should be roughly in the middle second
    assert any(0.5 < r.start_s < 2.5 for r in regions)


@pytest.fixture
def indexed_audio(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    audio = corpus / "lecture.wav"
    _write_wav(audio, seconds=4.0)
    (corpus / "lecture.transcript.json").write_text(
        json.dumps(
            {
                "language": "en",
                "segments": [
                    {
                        "start_s": 0.0,
                        "end_s": 3.0,
                        "text": "PathRAG performs flow based pruning "
                        "of relational paths in the knowledge graph.",
                        "speaker": "SPEAKER_00",
                    },
                    {
                        "start_s": 3.5,
                        "end_s": 6.0,
                        "text": "Paris is the capital of France.",
                        "speaker": "SPEAKER_01",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    build_index(corpus)
    from auralynq.agent import runner

    runner._CACHE.clear()
    return audio


def test_voice_turn_end_to_end_with_speaker_timestamp_citation(indexed_audio):
    from auralynq.voice.loop import run_voice_turn

    # Ask via text (the question audio is independent of the indexed corpus).
    res = run_voice_turn(text="What does PathRAG do?", speak=True)
    assert res.answer
    assert res.audio_out_path
    # at least one citation should carry an audio locator (speaker @ mm:ss)
    has_audio_cite = any(c.get("start_s") is not None or c.get("speaker") for c in res.citations)
    assert has_audio_cite


def test_voice_turn_transcribes_sidecar(indexed_audio):
    from auralynq.voice.loop import transcribe

    t = transcribe(indexed_audio)
    assert "pathrag" in t.text.lower()
    assert t.segments[0].speaker == "SPEAKER_00"
