# test_whisper_local_integration.py
# REAL integration tests for the whisper_local engine: a genuine faster-whisper
# model runs against real speech audio. These are marked `speech` and are
# skipped (honestly) whenever the faster-whisper runtime is not installed.
#
# Speech fixture strategy (no private recordings, no license problems):
#   Windows: a short utterance is synthesized at test time with the built-in
#            SAPI voice (offline, deterministic enough) into tmp_path.
#   Elsewhere: tests skip with an explicit reason.
#
# The model used here is `tiny` (smallest) so CI/dev runs stay cheap; it is
# downloaded from HuggingFace on first use and cached afterwards.

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip(
    "faster_whisper",
    reason="real engine tests need the speech extra (requirements-speech.txt)",
)

import numpy as np

from app.speech.audio import load_audio, prepare_engine_audio
from app.speech.base import AudioData
from app.speech.exceptions import TranscriptionFailed
from app.speech.whisper_local.adapter import WhisperLocalEngine
from app.speech.whisper_local.config import WhisperLocalConfig

REFERENCE_TEXT = (
    "Hello, this is VoxLab testing the new speech recognition engine "
    "with order number forty two."
)

SAPI_PHRASE = (
    "Hello, this is VoxLab testing the new speech recognition engine "
    "with order number forty two."
)


def _generate_sapi_wav(destination: Path) -> Path:
    """Synthesize the reference utterance with Windows SAPI (offline)."""
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
    path = tmp_path_factory.mktemp("speech") / "hello_voxlab.wav"
    return _generate_sapi_wav(path)


@pytest.fixture(scope="module")
def engine() -> WhisperLocalEngine:
    cfg = WhisperLocalConfig(
        model_key="tiny",  # smallest model: keeps the real-engine run cheap
        device="cpu",
        compute_type="int8",
        beam_size=1,
        vad_filter=False,
        timeout_seconds=180.0,
    )
    engine = WhisperLocalEngine(config=cfg)
    return engine


@pytest.mark.speech
@pytest.mark.integration
class TestWhisperLocalRealEngine:
    async def test_initialize_and_health(self, engine: WhisperLocalEngine) -> None:
        await engine.initialize()
        health = await engine.health_check()
        assert health.status == "healthy"
        assert health.model_loaded is True

    async def test_real_transcription(self, engine: WhisperLocalEngine, speech_wav: Path) -> None:
        await engine.initialize()
        loaded = load_audio(speech_wav.read_bytes(), filename="hello_voxlab.wav")
        samples, prep = prepare_engine_audio(loaded)
        audio = AudioData(samples=samples, sample_rate=16000, duration_seconds=prep["duration_seconds"])

        result = await engine.transcribe(audio, language="en")

        assert result.engine == "whisper_local"
        assert result.text, "real speech must not transcribe to empty text"
        assert result.language == "en"
        assert result.language_probability is not None and result.language_probability > 0
        assert result.processing_time_seconds > 0
        assert result.duration_seconds == pytest.approx(prep["duration_seconds"], rel=0.2)
        # tiny model on clean SAPI speech: content words must survive
        lowered = result.text.lower()
        assert "voxlab" in lowered, f"engine output missed key content: {result.text!r}"
        assert "engine" in lowered
        # segments carry real timestamps
        assert result.segments, "timestamped segments expected for real speech"
        first = result.segments[0]
        assert first.start_seconds >= 0.0
        assert first.end_seconds > first.start_seconds
        payload = result.to_dict()
        assert payload["metadata"]["model"] == "tiny"

    async def test_number_recognition(self, engine: WhisperLocalEngine, speech_wav: Path) -> None:
        await engine.initialize()
        loaded = load_audio(speech_wav.read_bytes(), filename="hello_voxlab.wav")
        samples, _prep = prepare_engine_audio(loaded)
        result = await engine.transcribe(AudioData(samples=samples), language="en")
        # "forty two" should surface as words or digits — both are legitimate
        normalized = result.text.lower().replace("-", " ")
        assert "forty two" in normalized or "42" in normalized, (
            f"number transcription failed: {result.text!r}"
        )

    async def test_silence_yields_empty_result_not_error(self, engine: WhisperLocalEngine) -> None:
        await engine.initialize()
        silent = AudioData(samples=np.zeros(16000, dtype=np.float32))
        result = await engine.transcribe(silent, language="en")
        assert result.text == ""

    async def test_streaming_partials(self, engine: WhisperLocalEngine, speech_wav: Path) -> None:
        await engine.initialize()
        loaded = load_audio(speech_wav.read_bytes(), filename="hello_voxlab.wav")
        samples, _prep = prepare_engine_audio(loaded)
        audio = AudioData(samples=samples)

        partials = list(engine.transcribe_stream(audio, chunk_seconds=2.5))
        assert len(partials) >= 2, "multi-window audio should produce several partials"
        assert partials[-1].is_final is True
        assert [p.chunk_index for p in partials] == list(range(len(partials)))
        assert any(p.text for p in partials), "at least one window must contain speech"

    async def test_capabilities_are_truthful(self, engine: WhisperLocalEngine) -> None:
        caps = engine.get_capabilities()
        assert caps.streaming_mode == "chunked_window"
        assert caps.supports_timestamps is True
        assert caps.supports_language_detection is True
        metadata = engine.get_metadata()
        assert metadata.engine_id == "whisper_local"
        assert "whisper-local" in (metadata.attribution or "")

    async def test_transcribe_before_initialize_fails_cleanly(self, speech_wav: Path) -> None:
        fresh = WhisperLocalEngine(config=WhisperLocalConfig(model_key="tiny"))
        loaded = load_audio(speech_wav.read_bytes(), filename="hello_voxlab.wav")
        samples, _prep = prepare_engine_audio(loaded)
        with pytest.raises(TranscriptionFailed, match="not loaded"):
            await fresh.transcribe(AudioData(samples=samples))
