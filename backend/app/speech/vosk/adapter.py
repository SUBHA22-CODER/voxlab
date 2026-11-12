# adapter.py
# VoxLab's second speech engine: Vosk (Kaldi-based), chosen because it is
# genuinely streaming-capable, CPU-first, and fully offline once its model
# is present — a meaningful contrast to faster-whisper for benchmarks.
#
# Honesty rules honored:
# - is_available() only reports the *package*; health_check reports whether a
#   model is actually usable. No fake results without a model.
# - Capabilities declare streaming_mode="streaming_decode": Vosk decodes the
#   buffer sequentially with carried acoustic state (true streaming decode of
#   the provided audio). The API surface still accepts a complete buffer, not
#   a live microphone, and we never claim otherwise.
# - Word timestamps come from Vosk's word alignments when enabled and are
#   passed through verbatim; nothing is fabricated.

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any
from collections.abc import Iterator

import numpy as np

from ..base import (
    AudioData,
    EngineCapabilities,
    EngineHealth,
    EngineMetadata,
    PartialTranscription,
    SpeechEngine,
    TranscriptionResult,
    TranscriptionSegment,
)
from ..exceptions import (
    EngineInitializationError,
    EngineTimeout,
    TranscriptionFailed,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL_REPO = (
    "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
)
DEFAULT_MODEL_NAME = "vosk-model-small-en-us-0.15"


def _pcm16_bytes(samples: np.ndarray) -> bytes:
    """float32 [-1,1] mono -> 16-bit PCM little-endian bytes."""
    clipped = np.clip(samples, -1.0, 1.0)
    return (clipped * 32767.0).astype("<i2").tobytes()


def _configured_vosk_languages(model_ref: str) -> set[str]:
    """Accepted language set for the configured vosk model.

    Default small-en-us -> {"en"}; a model dir whose name encodes another
    language (e.g. vosk-model-small-hi-0.22) maps to that language, and the
    speech_vosk_languages setting overrides everything (comma-separated).
    """
    import os

    override = os.environ.get("SPEECH_VOSK_LANGUAGES", "")
    if not override:
        try:
            from ...core.config import get_settings

            override = get_settings().speech_vosk_languages or ""
        except Exception:  # noqa: BLE001 - settings optional in standalone use
            override = ""
    if override:
        return {lang.strip().lower() for lang in override.split(",") if lang.strip()}
    model_id = model_ref.lower()
    for code in ("en-us", "en-gb", "en-in", "hi", "ta", "te", "kn", "mr", "bn",
                 "gu", "ml", "or", "pa", "zh-cn", "zh-hk", "ja", "ru", "de",
                 "fr", "es", "pt", "it", "tr", "vi", "nl", "ca", "cs", "pl",
                 "sv", "fa", "uk", "kz", "uz", "ph"):
        if f"-{code}-" in model_id or model_id.endswith(f"-{code}"):
            return {code.split("-")[0]}
    return {"en"}


class VoskEngine(SpeechEngine):
    """Offline CPU STT via Vosk with real sequential decoding."""

    ATTRIBUTION = (
        "Vosk speech engine (Apache-2.0, https://github.com/alphacep/vosk-api); "
        "Kaldi models from alphacephei.com. Integrated as VoxLab's second "
        "engine for multi-engine benchmarking."
    )

    def __init__(
        self,
        model_dir: str | None = None,
        auto_download: bool = False,
        timeout_seconds: float = 120.0,
        sample_rate: int = 16_000,
        words_with_timestamps: bool = True,
    ) -> None:
        self._model_dir = model_dir
        self._auto_download = auto_download
        self.timeout_seconds = timeout_seconds
        self.sample_rate = sample_rate
        self.words_with_timestamps = words_with_timestamps
        self._model: Any | None = None
        self._lock = asyncio.Lock()
        self.last_error: str | None = None

    # -- availability & description ---------------------------------------

    @classmethod
    def engine_id(cls) -> str:
        return "vosk"

    @classmethod
    def is_available(cls) -> bool:
        try:
            import vosk  # noqa: F401
        except ImportError:
            return False
        return True

    @classmethod
    def describe_capabilities(cls) -> EngineCapabilities:
        return EngineCapabilities(
            languages=["en"],  # default small-en-us model; config-driven below
            supports_timestamps=True,
            supports_language_detection=False,  # fixed-language models
            streaming_mode="streaming_decode",
            max_audio_duration_seconds=None,
        )

    def get_capabilities(self) -> EngineCapabilities:
        caps = self.describe_capabilities()
        # Language set follows the configured model: pointing the engine at a
        # Hindi model dir (SPEECH_VOSK_MODEL_DIR / speech_vosk_model_dir) must
        # not leave the engine claiming English-only (audit fix, VoxLab 2.6).
        configured = _configured_vosk_languages(self._resolved_model_dir())
        caps.languages = sorted(configured)
        return caps

    def get_metadata(self) -> EngineMetadata:
        import vosk

        return EngineMetadata(
            engine_id=self.engine_id(),
            display_name="Vosk (Kaldi)",
            version=getattr(vosk, "VERSION", None) or getattr(vosk, "__version__", None),
            model=Path(self._resolved_model_dir()).name if self._model else None,
            device="cpu",
            compute_type="kaldi-float",
            attribution=self.ATTRIBUTION,
            installed=self.is_available(),
        )

    # -- model resolution ---------------------------------------------------

    def _resolved_model_dir(self) -> str:
        import os

        if self._model_dir:
            return self._model_dir
        env_dir = os.environ.get("SPEECH_VOSK_MODEL_DIR", "")
        if env_dir:
            return env_dir
        default_root = Path("data/models/vosk") / DEFAULT_MODEL_NAME
        return str(default_root)

    def _model_usable(self) -> bool:
        model_path = Path(self._resolved_model_dir())
        return (model_path / "am" / "final.mdl").exists() or (model_path / "conf").exists()

    async def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model
        if not self._model_usable() and self._auto_download:
            await asyncio.to_thread(self._download_model)
        if not self._model_usable():
            raise EngineInitializationError(
                "Vosk model not found. Set SPEECH_VOSK_MODEL_DIR to an "
                "extracted model directory (e.g. vosk-model-small-en-us-0.15) "
                "or enable SPEECH_VOSK_AUTO_DOWNLOAD=true."
            )
        from vosk import Model

        self._model = await asyncio.to_thread(
            Model, self._resolved_model_dir(), self.sample_rate
        )
        logger.info("vosk model ready: %s", self._resolved_model_dir())
        return self._model

    def _download_model(self) -> None:
        """Download + extract the default small model (explicit opt-in)."""
        import zipfile

        import httpx

        target_root = Path(self._resolved_model_dir()).parent
        target_root.mkdir(parents=True, exist_ok=True)
        zip_path = target_root / (DEFAULT_MODEL_NAME + ".zip")
        logger.info("Downloading Vosk model (%s)...", DEFAULT_MODEL_NAME)
        with httpx.Client(follow_redirects=True, timeout=600.0) as client:
            with client.stream("GET", DEFAULT_MODEL_REPO) as response:
                response.raise_for_status()
                with zip_path.open("wb") as fh:
                    for chunk in response.iter_bytes(1 << 20):
                        fh.write(chunk)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(target_root)
        zip_path.unlink(missing_ok=True)

    # -- lifecycle -----------------------------------------------------------

    async def initialize(self) -> None:
        async with self._lock:
            await self._ensure_model()

    async def health_check(self) -> EngineHealth:
        if not self.is_available():
            return EngineHealth(
                status="unavailable",
                detail="vosk package not installed "
                "(pip install -r requirements-speech-vosk.txt)",
                model_loaded=False,
            )
        if self._model is None:
            return EngineHealth(
                status="degraded",
                detail="package installed but no usable model at "
                f"{self._resolved_model_dir()}",
                model_loaded=False,
            )
        return EngineHealth(
            status="healthy",
            detail=f"model {Path(self._resolved_model_dir()).name} loaded on cpu",
            model_loaded=True,
        )

    async def shutdown(self) -> None:
        async with self._lock:
            self._model = None

    # -- transcription ---------------------------------------------------------

    async def transcribe(
        self,
        audio: AudioData,
        language: str | None = None,
    ) -> TranscriptionResult:
        model = await self._ensure_model()
        if audio.samples.size == 0:
            raise TranscriptionFailed("AudioData contains zero samples.")
        if audio.sample_rate != self.sample_rate:
            raise TranscriptionFailed(
                f"vosk expects {self.sample_rate} Hz; got {audio.sample_rate}. "
                "Prepare audio through app.speech.audio.prepare_engine_audio."
            )
        accepted = _configured_vosk_languages(self._resolved_model_dir())
        base_lang = (language or "en").split("-")[0].lower()
        if base_lang not in accepted and "auto" not in accepted:
            raise TranscriptionFailed(
                f"vosk model '{self._resolved_model_dir()}' "
                f"accepts {sorted(accepted)}; got language={language!r}. Point "
                "SPEECH_VOSK_MODEL_DIR at a matching model or adjust "
                "speech_vosk_languages."
            )

        started = time.perf_counter()
        try:
            payload = await asyncio.wait_for(
                asyncio.to_thread(self._transcribe_blocking, model, audio.samples),
                timeout=self.timeout_seconds,
            )
        except TimeoutError as exc:
            raise EngineTimeout(
                f"vosk transcription exceeded {self.timeout_seconds:.0f}s."
            ) from exc
        except Exception as exc:
            self.last_error = str(exc)
            raise TranscriptionFailed(f"vosk transcription failed: {exc}") from exc

        text, words, duration = payload
        segments = self._words_to_segments(words) if words else []
        return TranscriptionResult(
            engine=self.engine_id(),
            text=text,
            language="en",
            language_probability=None,  # fixed-language model: no detection
            segments=segments,
            duration_seconds=duration or audio.duration_seconds,
            processing_time_seconds=time.perf_counter() - started,
            metadata={
                "model": Path(self._resolved_model_dir()).name,
                "device": "cpu",
                "words_tracked": self.words_with_timestamps,
            },
        )

    def _transcribe_blocking(
        self, model: Any, samples: np.ndarray
    ) -> tuple[str, list[dict[str, Any]], float]:
        from vosk import KaldiRecognizer, SetLogLevel

        SetLogLevel(-1)
        recognizer = KaldiRecognizer(model, self.sample_rate)
        recognizer.SetWords(self.words_with_timestamps)
        pcm = _pcm16_bytes(samples)
        chunk_size = 8000  # bytes (~0.25 s) — real sequential decode
        offset = 0
        words: list[dict[str, Any]] = []
        duration = samples.size / self.sample_rate
        while offset < len(pcm):
            chunk = pcm[offset : offset + chunk_size]
            offset += chunk_size
            if recognizer.AcceptWaveform(chunk):
                words.extend(self._collect_words(recognizer.Result()))
        words.extend(self._collect_words(recognizer.FinalResult()))
        text = " ".join(w["word"] for w in words).strip()
        return text, words, duration

    def _collect_words(self, result_json: str) -> list[dict[str, Any]]:
        try:
            data = json.loads(result_json)
        except json.JSONDecodeError:
            return []
        return list(data.get("result") or [])

    @staticmethod
    def _words_to_segments(words: list[dict[str, Any]]) -> list[TranscriptionSegment]:
        """Group word timings into contiguous sentence-ish segments."""
        segments: list[TranscriptionSegment] = []
        current: list[dict[str, Any]] = []
        gap_limit = 0.8  # seconds of silence closes a segment

        def flush() -> None:
            if not current:
                return
            segments.append(
                TranscriptionSegment(
                    start_seconds=float(current[0]["start"]),
                    end_seconds=float(current[-1]["end"]),
                    text=" ".join(w["word"] for w in current),
                )
            )
            current.clear()

        for word in words:
            if current and float(word["start"]) - float(current[-1]["end"]) > gap_limit:
                flush()
            current.append(word)
        flush()
        return segments

    # -- streaming (real sequential decode with carried state) ------------------

    def transcribe_stream(
        self,
        audio: AudioData,
        chunk_seconds: float = 0.25,
    ) -> Iterator[PartialTranscription]:
        """Progressive partials through ONE recognizer (state carried across
        chunks — a genuine streaming decode of the buffer)."""
        if self._model is None:
            raise TranscriptionFailed(
                "vosk model is not loaded; call initialize() first."
            )
        from vosk import KaldiRecognizer, SetLogLevel

        SetLogLevel(-1)
        recognizer = KaldiRecognizer(self._model, self.sample_rate)
        recognizer.SetWords(self.words_with_timestamps)
        pcm = _pcm16_bytes(audio.samples)
        chunk_bytes = max(2, int(chunk_seconds * self.sample_rate) * 2)
        position_samples = 0
        for chunk_index, offset in enumerate(range(0, len(pcm), chunk_bytes)):
            piece = pcm[offset : offset + chunk_bytes]
            final_of_window = offset + chunk_bytes >= len(pcm)
            if recognizer.AcceptWaveform(piece):
                result = json.loads(recognizer.Result())
                text = str(result.get("text", "")).strip()
            else:
                result = json.loads(recognizer.PartialResult())
                text = str(result.get("partial", "")).strip()
            position_samples += len(piece) // 2
            yield PartialTranscription(
                text=text,
                is_final=final_of_window,
                chunk_index=chunk_index,
                start_seconds=(position_samples - len(piece) // 2) / self.sample_rate,
                end_seconds=position_samples / self.sample_rate,
            )
