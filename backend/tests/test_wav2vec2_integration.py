# test_wav2vec2_integration.py
# REAL integration tests for the Wav2Vec2 CTC acoustic engine: Hugging Face
# facebook/wav2vec2-base-960h transcribes real speech audio. Marked `speech`;
# skips honestly when transformers/torch or the model weights are not present.

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip(
    "transformers",
    reason="real wav2vec2 tests need requirements-speech-wav2vec2.txt installed",
)
pytest.importorskip(
    "torch",
    reason="real wav2vec2 tests need torch installed",
)

from app.speech.audio import load_audio, prepare_engine_audio
from app.speech.base import AudioData
from app.speech.exceptions import TranscriptionFailed
from app.speech.wav2vec2.adapter import Wav2Vec2Engine

SAPI_PHRASE = (
    "Hello, this is VoxLab testing the new speech recognition engine "
    "with order number forty two."
)


def _generate_sapi_wav(destination: Path) -> Path:
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SetOutputToWaveFile('{destination.as_posix()}'); "
        "$s.Rate = 0; "
        f"$s.Speak('{SAPI_PHRASE}'); "
        "$s.Dispose()"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0 or not destination.exists():
        pytest.skip(f"SAPI fixture generation unavailable: {result.stderr.strip()}")
    return destination


@pytest.fixture(scope="module")
def speech_wav(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if sys.platform != "win32":
        pytest.skip("speech fixture synthesis requires Windows SAPI")
    return _generate_sapi_wav(tmp_path_factory.mktemp("wav2vec2") / "hello_voxlab.wav")


@pytest.fixture(scope="module")
async def engine() -> Wav2Vec2Engine:
    engine = Wav2Vec2Engine(auto_download=False, timeout_seconds=120.0)
    if not engine._model_usable():
        pytest.skip("wav2vec2 model not present on this machine (SPEECH_WAV2VEC2_MODEL_DIR)")
    await engine.initialize()
    return engine


def _audio_of(speech_wav: Path) -> AudioData:
    loaded = load_audio(speech_wav.read_bytes(), filename="hello_voxlab.wav")
    samples, prep = prepare_engine_audio(loaded)
    return AudioData(samples=samples, sample_rate=16000, duration_seconds=prep["duration_seconds"])


@pytest.mark.speech
@pytest.mark.integration
class TestWav2Vec2RealEngine:
    async def test_health_and_metadata(self, engine: Wav2Vec2Engine) -> None:
        health = await engine.health_check()
        assert health.status == "healthy"
        assert health.model_loaded is True
        metadata = engine.get_metadata()
        assert metadata.engine_id == "wav2vec2"
        assert metadata.model and "wav2vec2" in metadata.model.lower()

    async def test_real_transcription(self, engine: Wav2Vec2Engine, speech_wav: Path) -> None:
        result = await engine.transcribe(_audio_of(speech_wav))
        assert result.engine == "wav2vec2"
        assert result.text, "real speech must not transcribe to empty text"
        lowered = result.text.lower()
        assert (
            "voxlab" in lowered or "vox lab" in lowered or "speech" in lowered
        ), f"wav2vec2 output missed key content: {result.text!r}"
        assert result.processing_time_seconds > 0
        assert "wav2vec2" in result.metadata["model"].lower()

    async def test_ctc_timestamps_are_monotonic(
        self, engine: Wav2Vec2Engine, speech_wav: Path
    ) -> None:
        result = await engine.transcribe(_audio_of(speech_wav))
        if result.segments:
            starts = [s.start_seconds for s in result.segments]
            assert starts == sorted(starts), "CTC word offsets must be chronological"
            for segment in result.segments:
                assert segment.end_seconds >= segment.start_seconds

    async def test_streaming_window_partials(
        self, engine: Wav2Vec2Engine, speech_wav: Path
    ) -> None:
        audio = _audio_of(speech_wav)
        partials = list(engine.transcribe_stream(audio, chunk_seconds=1.0))
        assert len(partials) >= 2, "multiple chunked windows expected"
        assert partials[-1].is_final is True

    async def test_capabilities_are_truthful(self, engine: Wav2Vec2Engine) -> None:
        caps = engine.get_capabilities()
        assert caps.streaming_mode == "chunked_window"
        assert caps.supports_language_detection is False
        assert caps.languages == ["en"]  # config-driven (audit fix)
        assert caps.supports_timestamps is True

    async def test_rejects_non_english_language_request(
        self, engine: Wav2Vec2Engine, speech_wav: Path
    ) -> None:
        with pytest.raises(TranscriptionFailed, match="English-only"):
            await engine.transcribe(_audio_of(speech_wav), language="es")
