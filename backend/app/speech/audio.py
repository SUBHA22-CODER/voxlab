# audio.py
# Audio ingestion and validation: decode uploaded bytes into engine-ready
# AudioData (mono float32 @ 16 kHz) with explicit, typed failure modes.
#
# Decoders:
# - WAV  -> stdlib `wave` (always available, zero extra dependencies)
# - MP3 / FLAC / OGG / WebM -> PyAV (`av`), which is already a dependency of
#   faster-whisper, so no additional package is introduced. When `av` is not
#   importable (speech extra not installed) those formats fail with a clear
#   UnsupportedAudioFormat instead of a silent fallback.
#
# Product rules honored here:
# - The original audio is never silently modified; peak normalization happens
#   only when the caller asks for it and is recorded in the result metadata.
# - Corrupted / empty / oversized inputs raise typed exceptions, never a
#   "transcribed to empty string" success.

from __future__ import annotations

import io
import logging
import struct
import wave
from dataclasses import dataclass
from typing import Any

import numpy as np

from .exceptions import (
    AudioCorrupt,
    AudioTooLarge,
    UnsupportedAudioFormat,
)

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 16_000

# Container formats we accept, keyed by canonical name.
WAV_FORMATS = {"wav", "wave", "x-wav", "vnd.wave", "wav audio"}
AV_FORMATS = {"mp3", "flac", "ogg", "webm", "m4a", "aac", "opus"}

DEFAULT_MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
DEFAULT_MAX_DURATION_SECONDS = 600.0  # 10 minutes


@dataclass
class LoadedAudio:
    """Decoded audio as it was found in the file (before engine resampling)."""

    samples: np.ndarray  # mono float32 in [-1, 1] at the source rate
    sample_rate: int
    channels: int
    container_format: str
    duration_seconds: float
    metadata: dict[str, Any]


def sniff_format(filename: str | None, declared_format: str | None) -> str | None:
    """Best-effort container detection from the filename / declared type."""
    candidates = []
    if filename and "." in filename:
        candidates.append(filename.rsplit(".", 1)[-1].lower())
    if declared_format:
        candidates.append(declared_format.lower().split("/")[-1].replace("mpeg", "mp3"))
    for cand in candidates:
        if cand in WAV_FORMATS:
            return "wav"
        if cand in AV_FORMATS:
            return cand
    return None


def _check_size(blob: bytes, max_bytes: int) -> None:
    if not blob:
        raise AudioCorrupt("Audio upload is empty (0 bytes).")
    if len(blob) > max_bytes:
        raise AudioTooLarge(
            f"Audio upload is {len(blob)} bytes; the configured maximum is "
            f"{max_bytes} bytes."
        )


def _samples_to_float32(raw: np.ndarray) -> np.ndarray:
    """Convert integer PCM samples to float32 in [-1, 1]."""
    if raw.dtype == np.float32 or raw.dtype == np.float64:
        out = raw.astype(np.float32)
    elif raw.dtype == np.uint8:  # 8-bit WAV is unsigned with 128 as silence
        out = (raw.astype(np.float32) - 128.0) / 128.0
    elif raw.dtype == np.int16:
        out = raw.astype(np.float32) / 32768.0
    elif raw.dtype == np.int32:
        out = raw.astype(np.float32) / 2147483648.0
    else:
        raise UnsupportedAudioFormat(
            f"Unsupported PCM sample dtype: {raw.dtype}."
        )
    return np.clip(out, -1.0, 1.0)


def _to_mono(samples: np.ndarray) -> np.ndarray:
    """Downmix multi-channel audio to mono by averaging channels."""
    if samples.ndim == 1:
        return samples
    if samples.ndim == 2:
        # Either (channels, frames) or (frames, channels); the smaller axis is
        # the channel axis for every format we decode.
        if samples.shape[0] <= samples.shape[1]:
            return samples.mean(axis=0)
        return samples.mean(axis=1)
    raise AudioCorrupt(f"Unexpected audio array rank: {samples.ndim}.")


def _decode_wav(blob: bytes) -> LoadedAudio:
    try:
        with wave.open(io.BytesIO(blob), "rb") as wav:
            channels = wav.getnchannels()
            sample_rate = wav.getframerate()
            sample_width = wav.getsampwidth()
            frame_count = wav.getnframes()
            if frame_count == 0 or channels == 0 or sample_rate == 0:
                raise AudioCorrupt("WAV file contains no audio frames.")
            raw_bytes = wav.readframes(frame_count)
    except wave.Error as exc:
        raise AudioCorrupt(f"Invalid WAV file: {exc}") from exc
    except EOFError as exc:
        raise AudioCorrupt("WAV file is truncated.") from exc

    if sample_width == 1:
        raw = np.frombuffer(raw_bytes, dtype=np.uint8)
    elif sample_width == 2:
        raw = np.frombuffer(raw_bytes, dtype="<i2")
    elif sample_width == 4:
        raw = np.frombuffer(raw_bytes, dtype="<i4")
    elif sample_width == 3:
        raise UnsupportedAudioFormat(
            "24-bit PCM WAV is not supported; re-encode as 16-bit or 32-bit WAV."
        )
    else:
        raise UnsupportedAudioFormat(
            f"Unsupported WAV sample width: {sample_width} bytes."
        )

    # Reshape to (frames, channels) so downmixing averages real channels.
    if channels > 1:
        if raw.size % channels != 0:
            raise AudioCorrupt("WAV frame data is not aligned to its channel count.")
        raw = raw.reshape(-1, channels)
    samples = _to_mono(_samples_to_float32(raw))
    return LoadedAudio(
        samples=samples.astype(np.float32),
        sample_rate=sample_rate,
        channels=channels,
        container_format="wav",
        duration_seconds=round(frame_count / sample_rate, 6),
        metadata={"sample_width_bytes": sample_width},
    )


def _decode_with_av(blob: bytes, container_format: str) -> LoadedAudio:
    try:
        import av  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - depends on extras
        raise UnsupportedAudioFormat(
            f"Decoding {container_format} requires the PyAV package "
            "(installed with the speech extra: pip install -r "
            "requirements-speech.txt)."
        ) from exc

    try:
        container = av.open(io.BytesIO(blob))
        resampler = av.AudioResampler(format="s16", layout="mono", rate=TARGET_SAMPLE_RATE)
        chunks: list[bytes] = []
        decoded_any = False
        for packet in container.demux(audio=0):
            for frame in packet.decode():
                decoded_any = True
                resampled = resampler.resample(frame)
                for out_frame in resampled:
                    chunks.append(bytes(out_frame.planes[0]))
        if not decoded_any:
            raise AudioCorrupt(
                f"{container_format.upper()} container has no decodable audio stream."
            )
    except AudioCorrupt:
        raise
    except av.error.InvalidDataError as exc:  # type: ignore[attr-defined]
        raise AudioCorrupt(f"Corrupt {container_format} audio: {exc}") from exc
    except Exception as exc:
        raise AudioCorrupt(
            f"Failed to decode {container_format} audio: {exc}"
        ) from exc

    pcm = b"".join(chunks)
    if not pcm:
        raise AudioCorrupt(f"{container_format.upper()} decoded to zero samples.")
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
    return LoadedAudio(
        samples=samples,
        sample_rate=TARGET_SAMPLE_RATE,
        channels=1,
        container_format=container_format,
        duration_seconds=round(samples.size / TARGET_SAMPLE_RATE, 6),
        metadata={"decoder": "pyav"},
    )


def load_audio(
    blob: bytes,
    filename: str | None = None,
    declared_format: str | None = None,
    max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
) -> LoadedAudio:
    """Decode an uploaded audio file into mono float32 at its native rate.

    Raises AudioCorrupt / UnsupportedAudioFormat / AudioTooLarge — every
    rejection is explicit.
    """
    _check_size(blob, max_bytes)

    fmt = sniff_format(filename, declared_format)
    if fmt == "wav":
        return _decode_wav(blob)
    if fmt in AV_FORMATS:
        return _decode_with_av(blob, fmt)

    # Unknown/missing extension: try WAV header sniff, then PyAV as fallback.
    if blob[:4] == b"RIFF" and blob[8:12] == b"WAVE":
        return _decode_wav(blob)
    try:
        import av  # noqa: F401  (probe only)

        return _decode_with_av(blob, declared_format or "unknown")
    except ImportError:
        pass
    raise UnsupportedAudioFormat(
        "Could not determine the audio format. Supported: WAV (built-in), "
        "MP3, FLAC, OGG, WebM (with the speech extra installed). Provide a "
        "recognizable file extension to help detection."
    )


def validate_duration(audio: LoadedAudio, max_duration: float) -> None:
    if audio.duration_seconds > max_duration:
        raise AudioTooLarge(
            f"Audio is {audio.duration_seconds:.1f}s long; the configured "
            f"maximum is {max_duration:.0f}s."
        )


def resample_to_target(audio: LoadedAudio, target_rate: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    """Resample mono float32 audio to the target rate using soxr.

    soxr ships with the speech extra (the same resampler whisper-local uses).
    Resampling is only ever *needed* when the source rate differs from the
    target; the original samples are returned untouched otherwise.
    """
    samples = audio.samples
    if audio.sample_rate == target_rate:
        return samples
    try:
        import soxr  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - depends on extras
        raise UnsupportedAudioFormat(
            f"Resampling from {audio.sample_rate} Hz to {target_rate} Hz "
            "requires the soxr package (pip install -r requirements-speech.txt)."
        ) from exc
    resampled = soxr.resample(samples, audio.sample_rate, target_rate)
    return np.asarray(resampled, dtype=np.float32)


def detect_silence(
    samples: np.ndarray,
    rms_threshold: float = 0.0015,  # ≈ -56 dBFS
    peak_threshold: float = 0.01,
) -> bool:
    """True when the clip is effectively silent (no usable speech energy).

    Pure numpy RMS/peak check — deterministic and cheap; engines may add their
    own model-based VAD on top.
    """
    if samples.size == 0:
        return True
    rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
    peak = float(np.max(np.abs(samples)))
    return rms < rms_threshold and peak < peak_threshold


def peak_normalize(samples: np.ndarray, target_peak: float = 0.99) -> np.ndarray:
    """Explicit, opt-in peak normalization (never applied silently)."""
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    if peak <= 1e-9:
        return samples
    gain = target_peak / peak
    if abs(gain - 1.0) < 1e-6:
        return samples
    return np.clip(samples * gain, -1.0, 1.0).astype(np.float32)


def prepare_engine_audio(
    audio: LoadedAudio,
    normalize: bool = False,
    target_rate: int = TARGET_SAMPLE_RATE,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Full pipeline: validate → (optionally normalize) → resample → mono float32.

    Returns (samples @ target_rate, preparation_metadata). Metadata records what
    was done so callers can disclose every transformation.
    """
    samples = audio.samples
    prep: dict[str, Any] = {
        "source_sample_rate": audio.sample_rate,
        "source_channels": audio.channels,
        "resampled": False,
        "peak_normalized": False,
    }

    if samples.size and not np.all(np.isfinite(samples)):
        raise AudioCorrupt("Audio contains non-finite samples (NaN/inf).")

    if normalize:
        samples = peak_normalize(samples)
        prep["peak_normalized"] = True

    if audio.sample_rate != target_rate:
        samples = resample_to_target(audio, target_rate)
        prep["resampled"] = True
        prep["target_sample_rate"] = target_rate

    duration = samples.size / target_rate
    prep["duration_seconds"] = round(float(duration), 6)
    prep["silent"] = detect_silence(samples)
    return samples.astype(np.float32), prep


# Kept for structured error reporting in API responses.
def wav_header_summary(blob: bytes) -> dict[str, Any]:  # pragma: no cover
    """Best-effort header fields for diagnostics (never raises)."""
    try:
        with wave.open(io.BytesIO(blob), "rb") as wav:
            return {
                "channels": wav.getnchannels(),
                "sample_rate": wav.getframerate(),
                "sample_width_bytes": wav.getsampwidth(),
                "frames": wav.getnframes(),
            }
    except Exception:
        return {"struct_probe": struct.unpack("<4s", blob[:4])[0].decode("ascii", "replace") if len(blob) >= 4 else None}
