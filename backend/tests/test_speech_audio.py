# test_speech_audio.py
# Unit tests for the speech engine abstraction, audio validation, and registry.
# Fully offline: synthetic WAV bytes are generated in-memory; no model or
# network is involved. Tests that need optional extras (soxr) skip honestly.

from __future__ import annotations

import io
import wave

import pytest

pytest.importorskip("numpy", reason="speech audio tests need numpy (requirements-speech.txt)")

import numpy as np

from app.speech.audio import (
    detect_silence,
    load_audio,
    peak_normalize,
    prepare_engine_audio,
    validate_duration,
    LoadedAudio,
)
from app.speech.base import AudioData, EngineCapabilities, SpeechEngine
from app.speech.exceptions import (
    AudioCorrupt,
    AudioTooLarge,
    EngineNotInstalled,
    UnsupportedAudioFormat,
)
from app.speech.registry import EngineRegistry

SR = 16000


def _wav_bytes(
    samples: np.ndarray,
    sample_rate: int = SR,
    channels: int = 1,
    sampwidth: int = 2,
) -> bytes:
    """Encode float samples in [-1, 1] as a PCM WAV container.

    Multi-channel output repeats each sample across channels (identical
    channels), which is all the downmix test needs.
    """
    data = np.clip(samples, -1.0, 1.0)
    if channels > 1:
        data = np.repeat(data, channels)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sampwidth)
        wav.setframerate(sample_rate)
        if sampwidth == 2:
            wav.writeframes((data * 32767.0).astype("<i2").tobytes())
        elif sampwidth == 1:
            wav.writeframes(((data * 127.0) + 128).astype(np.uint8).tobytes())
        elif sampwidth == 4:
            wav.writeframes((data * 2147483647.0).astype("<i4").tobytes())
        else:
            raise ValueError(f"unsupported test width {sampwidth}")
    return buf.getvalue()


def _tone(seconds: float, freq: float = 440.0, sr: int = SR) -> np.ndarray:
    t = np.arange(int(seconds * sr), dtype=np.float64) / sr
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


# --- WAV decoding -------------------------------------------------------------


def test_load_mono_16bit_wav():
    tone = _tone(0.5)
    audio = load_audio(_wav_bytes(tone), filename="clip.wav")
    assert audio.container_format == "wav"
    assert audio.sample_rate == SR
    assert audio.channels == 1
    assert audio.duration_seconds == pytest.approx(0.5, abs=1e-3)
    assert audio.samples.dtype == np.float32
    assert float(np.max(np.abs(audio.samples))) > 0.1


def test_load_stereo_wav_downmixes_to_mono():
    tone = _tone(0.25)
    audio = load_audio(_wav_bytes(tone, channels=2), filename="stereo.wav")
    assert audio.channels == 2
    assert audio.samples.ndim == 1
    assert audio.samples.size == int(0.25 * SR)


def test_load_8bit_and_32bit_wav():
    tone = _tone(0.1)
    for width in (1, 4):
        audio = load_audio(_wav_bytes(tone, sampwidth=width), filename=f"c{width}.wav")
        assert float(np.max(np.abs(audio.samples))) > 0.1


def test_24bit_wav_rejected_with_clear_error():
    # Build a real 24-bit header by hand (wave module cannot write it).
    frames = b"\x00\x00\x00" * int(0.05 * SR)
    byte_rate = SR * 1 * 3
    header = (
        b"RIFF" + (36 + len(frames)).to_bytes(4, "little") + b"WAVE"
        b"fmt " + (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
        + (1).to_bytes(2, "little") + SR.to_bytes(4, "little")
        + byte_rate.to_bytes(4, "little") + (3).to_bytes(2, "little")
        + (24).to_bytes(2, "little") + b"data" + len(frames).to_bytes(4, "little")
    )
    with pytest.raises(UnsupportedAudioFormat, match="24-bit"):
        load_audio(header + frames, filename="clip24.wav")


def test_corrupt_wav_raises_audio_corrupt():
    blob = b"RIFF" + (100).to_bytes(4, "little") + b"WAVEfmt" + b"\x00" * 20
    with pytest.raises(AudioCorrupt):
        load_audio(blob, filename="broken.wav")


def test_empty_upload_raises():
    with pytest.raises(AudioCorrupt, match="empty"):
        load_audio(b"", filename="empty.wav")


def test_oversize_upload_raises_audio_too_large():
    tone = _tone(0.05)
    with pytest.raises(AudioTooLarge):
        load_audio(_wav_bytes(tone), filename="big.wav", max_bytes=10)


def test_unknown_format_falls_back_to_probe_or_clear_error():
    garbage = b"\x00\x01\x02\x03" * 256
    with pytest.raises((UnsupportedAudioFormat, AudioCorrupt)):
        load_audio(garbage, filename="mystery.bin")


# --- validation helpers ---------------------------------------------------------


def test_detect_silence_true_for_zeros_and_false_for_tone():
    assert detect_silence(np.zeros(SR, dtype=np.float32)) is True
    assert detect_silence(_tone(0.2)) is False
    assert detect_silence(np.array([], dtype=np.float32)) is True


def test_peak_normalize_scales_and_is_stable():
    quiet = (_tone(0.1) * 0.1).astype(np.float32)
    normalized = peak_normalize(quiet)
    assert float(np.max(np.abs(normalized))) == pytest.approx(0.99, abs=1e-3)
    # Already-normalized audio comes back unchanged.
    assert peak_normalize(normalized) is normalized or np.array_equal(
        peak_normalize(normalized), normalized
    )


def test_validate_duration_rejects_long_audio():
    long_audio = LoadedAudio(
        samples=np.zeros(10 * SR, dtype=np.float32),
        sample_rate=SR,
        channels=1,
        container_format="wav",
        duration_seconds=10.0,
        metadata={},
    )
    validate_duration(long_audio, max_duration=30.0)  # ok
    with pytest.raises(AudioTooLarge):
        validate_duration(long_audio, max_duration=5.0)


def test_prepare_engine_audio_reports_transformations():
    audio = LoadedAudio(
        samples=(_tone(0.2, sr=8000)),
        sample_rate=8000,
        channels=1,
        container_format="wav",
        duration_seconds=0.2,
        metadata={},
    )
    pytest.importorskip("soxr", reason="resampling needs soxr (requirements-speech.txt)")
    samples, prep = prepare_engine_audio(audio, normalize=True)
    assert samples.dtype == np.float32
    assert prep["resampled"] is True
    assert prep["peak_normalized"] is True
    assert prep["silent"] is False
    assert prep["duration_seconds"] == pytest.approx(0.2, abs=0.01)


# --- engine ABC + registry --------------------------------------------------------


class DummyEngine(SpeechEngine):
    calls: list[str] = []

    @classmethod
    def engine_id(cls) -> str:
        return "dummy"

    @classmethod
    def is_available(cls) -> bool:
        return True

    async def initialize(self) -> None:
        self.calls.append("init")

    async def health_check(self):
        from app.speech.base import EngineHealth

        return EngineHealth(status="healthy", detail="dummy", model_loaded=True)

    async def transcribe(self, audio: AudioData, language: str | None = None):
        from app.speech.base import TranscriptionResult

        return TranscriptionResult(engine="dummy", text="hello")

    def transcribe_stream(self, audio: AudioData, chunk_seconds: float = 3.0):
        raise AudioCorrupt("dummy has no streaming")

    def get_capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(streaming_mode="none", supports_timestamps=False)

    def get_metadata(self):
        from app.speech.base import EngineMetadata

        return EngineMetadata(engine_id="dummy", display_name="Dummy")

    async def shutdown(self) -> None:
        self.calls.append("shutdown")


class UnavailableEngine(DummyEngine):
    @classmethod
    def engine_id(cls) -> str:
        return "unavailable"

    @classmethod
    def is_available(cls) -> bool:
        return False


def test_registry_reports_known_engines_honestly():
    registry = EngineRegistry()
    registry.register(DummyEngine)
    registry.register(UnavailableEngine)
    assert registry.known_engines() == ["dummy", "unavailable"]
    assert registry.is_installed("dummy") is True
    assert registry.is_installed("unavailable") is False
    described = {d["engine_id"]: d for d in registry.describe_all()}
    assert described["dummy"]["installed"] is True
    assert described["unavailable"]["installed"] is False
    assert "install_hint" in described["unavailable"]


def test_registry_get_engine_initializes_shared_instance():
    registry = EngineRegistry()
    registry.register(DummyEngine)
    engine = registry.get_engine("dummy")
    assert engine is registry.get_engine("dummy")
    assert engine.get_metadata().engine_id == "dummy"


def test_registry_unknown_engine_raises_not_installed():
    registry = EngineRegistry()
    registry.register(UnavailableEngine)
    with pytest.raises(EngineNotInstalled, match="not installed"):
        registry.get_engine("unavailable")
    with pytest.raises(EngineNotInstalled, match="Unknown"):
        registry.get_engine("nope")


def test_transcription_result_to_dict_shape():
    from app.speech.base import TranscriptionResult

    result = TranscriptionResult(engine="dummy", text="hi", duration_seconds=1.5)
    payload = result.to_dict()
    assert payload["engine"] == "dummy"
    assert payload["segments"] == []
    assert payload["duration_seconds"] == 1.5
