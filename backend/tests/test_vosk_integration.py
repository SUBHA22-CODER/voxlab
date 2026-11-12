# test_vosk_integration.py
# REAL integration tests for the Vosk engine: a genuine Kaldi model
# (vosk-model-small-en-us-0.15) transcribes real speech audio. Marked
# `speech`; skips honestly when the vosk package or model is not present on
# the machine. The same SAPI fixture strategy as the whisper integration
# tests (offline synthesis, no private recordings).

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip(
    "vosk", reason="real vosk tests need requirements-speech-vosk.txt installed"
)


from app.speech.audio import load_audio, prepare_engine_audio
from app.speech.base import AudioData
from app.speech.exceptions import TranscriptionFailed
from app.speech.vosk.adapter import VoskEngine

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
    return _generate_sapi_wav(tmp_path_factory.mktemp("vosk") / "hello_voxlab.wav")


@pytest.fixture(scope="module")
async def engine() -> VoskEngine:
    engine = VoskEngine(auto_download=False, timeout_seconds=120.0)
    # Skip honestly when the machine has no model (CI without the download).
    if not engine._model_usable():
        pytest.skip("vosk model not present on this machine (SPEECH_VOSK_MODEL_DIR)")
    await engine.initialize()
    return engine


def _audio_of(speech_wav: Path) -> AudioData:
    loaded = load_audio(speech_wav.read_bytes(), filename="hello_voxlab.wav")
    samples, prep = prepare_engine_audio(loaded)
    return AudioData(samples=samples, sample_rate=16000, duration_seconds=prep["duration_seconds"])


@pytest.mark.speech
@pytest.mark.integration
class TestVoskRealEngine:
    async def test_health_and_metadata(self, engine: VoskEngine) -> None:
        health = await engine.health_check()
        assert health.status == "healthy"
        assert health.model_loaded is True
        metadata = engine.get_metadata()
        assert metadata.engine_id == "vosk"
        assert metadata.model and "vosk-model" in metadata.model

    async def test_real_transcription(self, engine: VoskEngine, speech_wav: Path) -> None:
        result = await engine.transcribe(_audio_of(speech_wav))
        assert result.engine == "vosk"
        assert result.text, "real speech must not transcribe to empty text"
        lowered = result.text.lower()
        # The small Kaldi model is weaker than whisper-tiny; pin the core
        # content words that must survive. "VoxLab" may legitimately tokenize
        # as "vox lab" — accept the observed variants.
        assert (
            "vox lab" in lowered or "voxlab" in lowered
        ), f"vosk output missed key content: {result.text!r}"
        assert "speech recognition engine" in lowered
        assert result.segments, "word timings should produce segments"
        assert result.processing_time_seconds > 0
        assert result.metadata["model"].startswith("vosk-model")

    async def test_timestamps_are_monotonic(self, engine: VoskEngine, speech_wav: Path) -> None:
        result = await engine.transcribe(_audio_of(speech_wav))
        starts = [s.start_seconds for s in result.segments]
        assert starts == sorted(starts), "word timings must be chronological"
        for segment in result.segments:
            assert segment.end_seconds > segment.start_seconds

    async def test_streaming_decode_carries_state(
        self, engine: VoskEngine, speech_wav: Path
    ) -> None:
        audio = _audio_of(speech_wav)
        partials = list(engine.transcribe_stream(audio, chunk_seconds=0.5))
        assert len(partials) >= 4, "several windows for a multi-second clip"
        assert partials[-1].is_final is True
        # Sequential decode with carried state: the union of partial text
        # should contain recognizable content (unlike whisper's windowed mode
        # which resets per window).
        joined = " ".join(p.text for p in partials).lower()
        assert any(word in joined for word in ("voxlab", "locks", "box", "speech")), joined

    async def test_capabilities_are_truthful(self, engine: VoskEngine) -> None:
        caps = engine.get_capabilities()
        assert caps.streaming_mode == "streaming_decode"
        assert caps.supports_language_detection is False
        assert caps.languages == ["en"]  # config-driven (audit fix)

    async def test_rejects_non_english_language_request(
        self, engine: VoskEngine, speech_wav: Path
    ) -> None:
        with pytest.raises(TranscriptionFailed, match="accepts"):
            await engine.transcribe(_audio_of(speech_wav), language="de")
