# adapter.py
# VoxLab's first real speech recognition engine, adapted from the whisper-local
# project's WhisperEngine (https://github.com/drajb/whisper-local, MIT).
#
# Attribution (per the MIT license of whisper-local):
#   Copyright (c) 2025 Pin Wang (original whisper-key-local)
#   Copyright (c) 2026 Rohit Burani (whisper-local fork and modifications)
#
# Patterns carried over from whisper-local's whisper_engine.py:
#   - mono float32 @ 16 kHz input contract
#   - load model once + warmup with a silent buffer so the first real request
#     does not pay lazy-init cost
#   - explicit last-error reporting: "no speech" is a valid empty result, a
#     CUDA/runtime fault is a hard failure — never conflated
#   - model size hints so a first-run download is never a mystery
#
# Differences (server context, not a desktop app):
#   - async facade: blocking CTranslate2 inference runs in a worker thread so
#     the FastAPI event loop never stalls
#   - constructor never loads the model; initialize() does (registry safety)
#   - streaming is honest chunked-window (faster-whisper has no true streaming;
#     whisper-local itself uses a separate sherpa-onnx engine for that)

from __future__ import annotations

import asyncio
import gc
import logging
import time
from collections.abc import Iterator
from typing import Any

import numpy as np

from ..audio import TARGET_SAMPLE_RATE
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
from .config import WhisperLocalConfig, is_english_only, model_size_hint

logger = logging.getLogger(__name__)

ATTRIBUTION = (
    "Speech engine adapted from whisper-local (MIT): "
    "Copyright (c) 2025 Pin Wang (original whisper-key-local); "
    "Copyright (c) 2026 Rohit Burani (whisper-local fork and modifications). "
    "Powered by faster-whisper / CTranslate2."
)


def _import_faster_whisper() -> Any:
    try:
        from faster_whisper import WhisperModel  # type: ignore[import-not-found]

        return WhisperModel
    except ImportError as exc:
        raise EngineInitializationError(
            "faster-whisper is not installed. "
            "Run: pip install -r requirements-speech.txt"
        ) from exc


class WhisperLocalEngine(SpeechEngine):
    """faster-whisper (CTranslate2) engine, CPU-first, fully offline."""

    ATTRIBUTION = ATTRIBUTION

    def __init__(self, config: WhisperLocalConfig | None = None) -> None:
        self.config = config or WhisperLocalConfig()
        self.config.validate()
        self._model: Any | None = None
        self._lock = asyncio.Lock()
        self.last_error: str | None = None

    # -- availability & description ---------------------------------------

    @classmethod
    def engine_id(cls) -> str:
        return "whisper_local"

    @classmethod
    def is_available(cls) -> bool:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            return False
        return True

    @classmethod
    def describe_capabilities(cls) -> EngineCapabilities:
        return EngineCapabilities(
            languages=None,  # multilingual, auto-detect
            supports_timestamps=True,
            supports_language_detection=True,
            streaming_mode="chunked_window",
            max_audio_duration_seconds=None,
        )

    def get_capabilities(self) -> EngineCapabilities:
        caps = self.describe_capabilities()
        if is_english_only(self.config.model_key):
            caps.languages = ["en"]
            caps.supports_language_detection = False
        return caps

    def get_metadata(self) -> EngineMetadata:
        version: str | None = None
        try:
            import faster_whisper

            version = getattr(faster_whisper, "__version__", None)
        except ImportError:
            pass
        return EngineMetadata(
            engine_id=self.engine_id(),
            display_name="Whisper Local (faster-whisper)",
            version=version,
            model=self.config.model_key,
            device=self.config.device,
            compute_type=self.config.compute_type,
            attribution=ATTRIBUTION,
            installed=self.is_available(),
        )

    # -- lifecycle ---------------------------------------------------------

    async def initialize(self) -> None:
        async with self._lock:
            if self._model is not None:
                return
            started = time.perf_counter()
            hint = model_size_hint(self.config.model_key)
            if hint:
                logger.info(
                    "Loading whisper_local model '%s' (%s on first use)...",
                    self.config.model_key,
                    hint,
                )
            else:
                logger.info("Loading whisper_local model '%s'...", self.config.model_key)
            try:
                whisper_cls = _import_faster_whisper()
                self._model = await asyncio.to_thread(
                    whisper_cls,
                    self.config.model_key,
                    device=self.config.device,
                    compute_type=self.config.compute_type,
                    cpu_threads=self.config.cpu_threads,
                    num_workers=self.config.num_workers,
                )
                await asyncio.to_thread(self._warmup)
            except EngineInitializationError:
                raise
            except Exception as exc:
                self._model = None
                self.last_error = str(exc)
                raise EngineInitializationError(
                    f"whisper_local failed to load model "
                    f"'{self.config.model_key}': {exc}"
                ) from exc
            logger.info(
                "whisper_local ready in %.2fs (device=%s compute=%s)",
                time.perf_counter() - started,
                self.config.device,
                self.config.compute_type,
            )

    def _warmup(self) -> None:
        """One silent decode so CUDA kernels/allocator warm up (pattern from
        whisper-local; harmless and fast on CPU)."""
        if self._model is None:
            return
        try:
            silent = np.zeros(TARGET_SAMPLE_RATE, dtype=np.float32)
            segments, _info = self._model.transcribe(
                silent, language="en", beam_size=1, vad_filter=False
            )
            for _segment in segments:
                pass
        except Exception as exc:  # noqa: BLE001 - warmup is best-effort, never fatal
            logger.debug("whisper_local warmup skipped: %s", exc)

    async def health_check(self) -> EngineHealth:
        if not self.is_available():
            return EngineHealth(
                status="unavailable",
                detail="faster-whisper is not installed",
                model_loaded=False,
            )
        if self._model is None:
            return EngineHealth(
                status="degraded",
                detail="engine constructed but model not loaded yet "
                "(call initialize)",
                model_loaded=False,
            )
        return EngineHealth(
            status="healthy",
            detail=f"model '{self.config.model_key}' loaded on "
            f"{self.config.device} ({self.config.compute_type})",
            model_loaded=True,
        )

    async def shutdown(self) -> None:
        async with self._lock:
            self._model = None
            gc.collect()

    # -- transcription -------------------------------------------------------

    async def transcribe(
        self,
        audio: AudioData,
        language: str | None = None,
    ) -> TranscriptionResult:
        if self._model is None:
            raise TranscriptionFailed(
                "whisper_local model is not loaded; call initialize() first."
            )
        if audio.samples.size == 0:
            raise TranscriptionFailed("AudioData contains zero samples.")

        effective_language = language or self.config.resolved_language
        started = time.perf_counter()
        try:
            payload = await asyncio.wait_for(
                asyncio.to_thread(
                    self._transcribe_blocking,
                    audio.samples,
                    audio.sample_rate,
                    effective_language,
                ),
                timeout=self.config.timeout_seconds,
            )
        except TimeoutError as exc:
            raise EngineTimeout(
                f"whisper_local transcription exceeded "
                f"{self.config.timeout_seconds:.0f}s."
            ) from exc
        except Exception as exc:
            self.last_error = str(exc) or exc.__class__.__name__
            raise TranscriptionFailed(
                f"whisper_local transcription failed: {exc}"
            ) from exc

        text, lang, lang_prob, segments, engine_duration = payload
        return TranscriptionResult(
            engine=self.engine_id(),
            text=text,
            language=lang,
            language_probability=lang_prob,
            segments=segments,
            duration_seconds=engine_duration or audio.duration_seconds,
            processing_time_seconds=time.perf_counter() - started,
            metadata={
                "model": self.config.model_key,
                "device": self.config.device,
                "compute_type": self.config.compute_type,
                "beam_size": self.config.beam_size,
                "vad_filter": self.config.vad_filter,
            },
        )

    def _transcribe_blocking(
        self,
        samples: np.ndarray,
        sample_rate: int,
        language: str | None,
    ) -> tuple[str, str | None, float | None, list[TranscriptionSegment], float]:
        """Runs in a worker thread. Returns the standardized pieces."""
        if self._model is None:  # pragma: no cover - guarded by caller
            raise TranscriptionFailed("model went away mid-flight")
        audio = samples
        if sample_rate != TARGET_SAMPLE_RATE:
            # The engine contract is 16 kHz; AudioData built outside the audio
            # pipeline may still carry another rate. faster-whisper accepts the
            # array as-is and assumes 16 kHz, so resampling is required.
            from ..audio import LoadedAudio, resample_to_target

            audio = resample_to_target(
                LoadedAudio(
                    samples=samples,
                    sample_rate=sample_rate,
                    channels=1,
                    container_format="raw",
                    duration_seconds=samples.size / sample_rate,
                    metadata={},
                ),
                TARGET_SAMPLE_RATE,
            )

        segments_iter, info = self._model.transcribe(
            audio,
            language=language,
            beam_size=self.config.beam_size,
            vad_filter=self.config.vad_filter,
            condition_on_previous_text=False,
        )

        texts: list[str] = []
        segments: list[TranscriptionSegment] = []
        for segment in segments_iter:
            texts.append(segment.text)
            segments.append(
                TranscriptionSegment(
                    start_seconds=float(segment.start),
                    end_seconds=float(segment.end),
                    text=segment.text.strip(),
                )
            )
        text = "".join(texts).strip()
        lang = getattr(info, "language", None)
        lang_prob = getattr(info, "language_probability", None)
        engine_duration = getattr(info, "duration", None)
        self.last_error = None
        return text, lang, lang_prob, segments, float(engine_duration or 0.0)

    # -- streaming (honest chunked-window) ------------------------------------

    def transcribe_stream(
        self,
        audio: AudioData,
        chunk_seconds: float = 3.0,
    ) -> Iterator[PartialTranscription]:
        """Progressive partials over a sliding window.

        This is REAL progressive output but NOT sub-word realtime streaming:
        each window is transcribed independently. Capabilities report
        streaming_mode="chunked_window" so callers can disclose this.
        """
        if self._model is None:
            raise TranscriptionFailed(
                "whisper_local model is not loaded; call initialize() first."
            )
        sr = audio.sample_rate
        window = max(1, int(chunk_seconds * sr))
        overlap = int(window * 0.25)  # overlap avoids word cuts at boundaries
        step = max(1, window - overlap)
        total = audio.samples.size
        chunk_index = 0
        position = 0
        while position < total:
            stop = min(position + window, total)
            piece = audio.samples[position:stop]
            try:
                segments_iter, _info = self._model.transcribe(
                    piece,
                    language=self.config.resolved_language,
                    beam_size=1,  # low latency over accuracy for partials
                    vad_filter=False,
                    condition_on_previous_text=False,
                )
                piece_text = "".join(s.text for s in segments_iter).strip()
            except Exception as exc:
                raise TranscriptionFailed(
                    f"whisper_local streaming window failed: {exc}"
                ) from exc
            yield PartialTranscription(
                text=piece_text,
                is_final=stop >= total,
                chunk_index=chunk_index,
                start_seconds=position / sr,
                end_seconds=stop / sr,
            )
            chunk_index += 1
            position += step
