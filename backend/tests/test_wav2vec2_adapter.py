# test_wav2vec2_adapter.py
# Unit tests for the Wav2Vec2 adapter offline logic (registry integration,
# capability reporting, install hints, audio validation, and CTC timestamp math).

from __future__ import annotations

import numpy as np
import pytest

from app.speech.base import AudioData
from app.speech.exceptions import TranscriptionFailed
from app.speech.registry import build_default_registry
from app.speech.wav2vec2.adapter import Wav2Vec2Engine


def test_wav2vec2_registry_discovery() -> None:
    registry = build_default_registry()
    assert "wav2vec2" in registry.known_engines()
    hint = registry.install_hint("wav2vec2")
    assert "requirements-speech-wav2vec2.txt" in hint


def test_wav2vec2_capabilities_truthful() -> None:
    caps = Wav2Vec2Engine.describe_capabilities()
    assert caps.streaming_mode == "chunked_window"
    assert caps.supports_language_detection is False
    assert caps.supports_timestamps is True
    assert caps.languages == ["en"]


def test_wav2vec2_install_hint_when_missing() -> None:
    hint = Wav2Vec2Engine.install_hint()
    assert "requirements-speech-wav2vec2.txt" in hint
    assert "transformers" in hint


def test_wav2vec2_extract_ctc_timestamps_calculation() -> None:
    """Validate that CTC frame offsets are correctly converted to seconds.
    Stride is 320 samples at 16000 Hz = 0.02 seconds per frame.
    """
    engine = Wav2Vec2Engine()
    fake_offsets = [
        {"word": "HELLO", "start_offset": 10, "end_offset": 25},
        {"word": "VOXLAB", "start_offset": 30, "end_offset": 55},
    ]

    segments = engine._extract_ctc_timestamps(fake_offsets, sample_rate=16000)
    assert len(segments) == 2

    # 10 * 320 / 16000 = 0.200s
    # 25 * 320 / 16000 = 0.500s
    assert pytest.approx(segments[0].start_seconds, 0.001) == 0.200
    assert pytest.approx(segments[0].end_seconds, 0.001) == 0.500
    assert segments[0].text == "HELLO"

    # 30 * 320 / 16000 = 0.600s
    # 55 * 320 / 16000 = 1.100s
    assert pytest.approx(segments[1].start_seconds, 0.001) == 0.600
    assert pytest.approx(segments[1].end_seconds, 0.001) == 1.100
    assert segments[1].text == "VOXLAB"


@pytest.mark.asyncio
async def test_wav2vec2_audio_validation_empty_audio() -> None:
    engine = Wav2Vec2Engine()
    engine._loaded = True
    empty_audio = AudioData(samples=np.array([], dtype=np.float32), sample_rate=16000, duration_seconds=0.0)

    with pytest.raises(TranscriptionFailed, match="zero samples"):
        await engine.transcribe(empty_audio)


@pytest.mark.asyncio
async def test_wav2vec2_audio_validation_sample_rate() -> None:
    engine = Wav2Vec2Engine()
    engine._loaded = True
    samples = np.zeros(16000, dtype=np.float32)
    wrong_sr_audio = AudioData(samples=samples, sample_rate=44100, duration_seconds=1.0)

    with pytest.raises(TranscriptionFailed, match="expects 16000 Hz"):
        await engine.transcribe(wrong_sr_audio)


@pytest.mark.asyncio
async def test_wav2vec2_audio_validation_non_english() -> None:
    engine = Wav2Vec2Engine()
    engine._loaded = True
    samples = np.zeros(16000, dtype=np.float32)
    audio = AudioData(samples=samples, sample_rate=16000, duration_seconds=1.0)

    with pytest.raises(TranscriptionFailed, match="English-only"):
        await engine.transcribe(audio, language="fr")
