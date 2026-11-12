# adapter.py
# VoxLab's third speech engine: Wav2Vec 2.0 (Meta AI / Hugging Face Transformers).
# Chosen as the representative of self-supervised acoustic representations with
# a non-autoregressive CTC linear head.
#
# Together with Whisper (encoder-decoder autoregressive transformer) and Vosk
# (Kaldi HMM-DNN hybrid with WFST decoding), this completes VoxLab's coverage
# of three fundamentally different speech recognition architectures:
#   1. WhisperLocal: Encoder-decoder autoregressive sequence-to-sequence
#   2. VoskEngine: HMM-DNN hybrid with sequential streaming WFST decode
#   3. Wav2Vec2Engine: Self-supervised acoustic encoder with non-autoregressive CTC
#
# Honesty rules:
# - is_available() only reports the package presence (torch + transformers).
#   health_check reports whether the model is actually loaded in memory.
# - Capabilities declare streaming_mode="chunked_window" (Wav2Vec2 CTC evaluates
#   whole utterances non-autoregressively; progressive streaming is windowed).
# - Word timestamps are extracted via CTC token offset frames when supported and
#   configured; never interpolated or fabricated.
# - Model version tracks the exact Hugging Face revision commit hash.

from __future__ import annotations

import asyncio
import gc
import logging
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np

from ...core.config import get_settings

from ..alignment import WordTiming
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

DEFAULT_MODEL_NAME = "facebook/wav2vec2-base-960h"
DEFAULT_REVISION = "main"

ATTRIBUTION = (
    "Wav2Vec 2.0 speech engine (Apache-2.0, Meta AI / Hugging Face Transformers); "
    "Model: facebook/wav2vec2-base-960h. Integrated as VoxLab's third engine "
    "for multi-architecture speech benchmarking."
)


class Wav2Vec2Engine(SpeechEngine):
    """Self-supervised acoustic representation with non-autoregressive CTC head."""

    ATTRIBUTION = ATTRIBUTION

    def __init__(
        self,
        model_name: str | None = None,
        revision: str | None = None,
        device: str | None = None,
        model_dir: str | None = None,
        timeout_seconds: float = 120.0,
        sample_rate: int = 16_000,
        word_timestamps: bool = True,
        auto_download: bool = False,
    ) -> None:
        from ...core.config import get_settings

        settings = get_settings()

        self.model_name = model_name or settings.speech_wav2vec2_model or DEFAULT_MODEL_NAME
        self.revision = revision or settings.speech_wav2vec2_revision or DEFAULT_REVISION
        self.device = device or settings.speech_wav2vec2_device or "cpu"
        self._model_dir = model_dir or settings.speech_wav2vec2_model_dir
        self.timeout_seconds = timeout_seconds
        self.sample_rate = sample_rate
        self.word_timestamps = word_timestamps and settings.speech_wav2vec2_word_timestamps
        self.auto_download = auto_download or settings.speech_wav2vec2_auto_download

        self._processor: Any | None = None
        self._model: Any | None = None
        self._resolved_revision: str | None = None
        self._lock = asyncio.Lock()
        self.last_error: str | None = None

    # -- availability & description ---------------------------------------

    @classmethod
    def engine_id(cls) -> str:
        return "wav2vec2"

    @classmethod
    def is_available(cls) -> bool:
        """True when both torch and transformers are importable."""
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401

            return True
        except ImportError:
            return False

    @classmethod
    def install_hint(cls) -> str:
        return (
            "Wav2Vec2 runtime is not installed. "
            "Install: pip install -r requirements-speech-wav2vec2.txt (requires torch and transformers)"
        )

    @staticmethod
    def _extract_ctc_timestamps(
        word_offsets: list[Any],
        sample_rate: int = 16_000,
        stride_samples: int = 320,
    ) -> list[TranscriptionSegment]:
        """Convert CTC token offsets to chronological TranscriptionSegment instances."""
        time_offset = float(stride_samples / sample_rate)
        segments: list[TranscriptionSegment] = []
        for item in word_offsets:
            w_text = item.get("word", "") if isinstance(item, dict) else getattr(item, "word", "")
            s_off = item.get("start_offset", 0) if isinstance(item, dict) else getattr(item, "start_offset", 0)
            e_off = item.get("end_offset", 0) if isinstance(item, dict) else getattr(item, "end_offset", 0)

            start_sec = round(float(s_off * time_offset), 3)
            end_sec = round(float(e_off * time_offset), 3)
            if end_sec <= start_sec:
                end_sec = round(start_sec + time_offset, 3)

            segments.append(
                TranscriptionSegment(
                    start_seconds=start_sec,
                    end_seconds=end_sec,
                    text=w_text,
                )
            )
        return segments

    @classmethod
    def describe_capabilities(cls) -> EngineCapabilities:
        """Static default (base-960h is English-only). Instance-level
        get_capabilities() reports the configured model's language set."""
        return EngineCapabilities(
            languages=["en"],
            supports_timestamps=True,
            supports_language_detection=False,
            streaming_mode="chunked_window",
            max_audio_duration_seconds=None,
        )

    def _accepted_languages(self) -> set[str]:
        """Accepted language set, driven by the configured model (audit fix:
        swapping to a multilingual CTC checkpoint must update capabilities)."""
        import os

        override = os.environ.get("SPEECH_WAV2VEC2_LANGUAGES", "")
        if not override:
            override = get_settings().speech_wav2vec2_languages or "en"
        return {lang.strip().lower() for lang in override.split(",") if lang.strip()}

    def get_capabilities(self) -> EngineCapabilities:
        """Instance capabilities from the configured model (audit fix)."""
        caps = self.describe_capabilities()
        caps.languages = sorted(self._accepted_languages())
        return caps

    def get_metadata(self) -> EngineMetadata:
        version = None
        if self.is_available():
            try:
                import transformers

                version = getattr(transformers, "__version__", None)
            except Exception:  # noqa: BLE001 - metadata is best-effort
                pass

        model_label = self.model_name
        if self._resolved_revision:
            model_label = f"{self.model_name}@{self._resolved_revision[:8]}"
        elif self.revision:
            model_label = f"{self.model_name}@{self.revision}"

        return EngineMetadata(
            engine_id=self.engine_id(),
            display_name="Wav2Vec2 (CTC)",
            version=version,
            model=model_label,
            device=self.device,
            compute_type="float32",
            attribution=ATTRIBUTION,
            installed=self.is_available(),
        )

    # -- model resolution & loading -----------------------------------------

    def _resolve_model_target(self) -> tuple[str | Path, dict[str, Any]]:
        """Return the target path or HF repo ID with loading kwargs.

        auto_download=False forces local-files-only loading (mirrors the Vosk
        engine's opt-in download posture): no surprise network fetches.
        """
        if self._model_dir:
            path = Path(self._model_dir)
            if path.exists():
                return path, {}
        kwargs: dict[str, Any] = {"revision": self.revision}
        if not self.auto_download:
            kwargs["local_files_only"] = True
        return self.model_name, kwargs

    def _model_usable(self) -> bool:
        """True when transcription can proceed without a network download:
        an explicit local dir, or a cached HF snapshot of the revision."""
        if self._model is not None:
            return True
        if self._model_dir and Path(self._model_dir).exists():
            return True
        if self.auto_download:
            return True
        try:
            from huggingface_hub import try_to_load_from_cache

            cached = try_to_load_from_cache(
                self.model_name, "config.json", revision=self.revision
            )
            return isinstance(cached, (str, Path))
        except Exception:  # noqa: BLE001 - cache probe is best-effort
            return False

    async def _ensure_model(self) -> tuple[Any, Any]:
        """Load processor and model into memory in a worker thread."""
        if self._model is not None and self._processor is not None:
            return self._processor, self._model

        if not self.is_available():
            raise EngineInitializationError(
                "Wav2Vec2 runtime dependencies are not installed. "
                "Install with: pip install -r requirements-speech-wav2vec2.txt"
            )

        target, kwargs = self._resolve_model_target()
        logger.info("Loading Wav2Vec2 model (%s, revision=%s)...", target, self.revision)

        def _load_blocking() -> tuple[Any, Any]:
            import torch
            from transformers import AutoModelForCTC, AutoProcessor

            processor = AutoProcessor.from_pretrained(target, **kwargs)
            model = AutoModelForCTC.from_pretrained(target, **kwargs)
            model.eval()

            # Ensure model is on requested device
            if self.device != "cpu" and torch.cuda.is_available():
                model = model.to(self.device)
            else:
                model = model.to("cpu")

            return processor, model

        try:
            processor, model = await asyncio.to_thread(_load_blocking)
        except Exception as exc:
            self.last_error = str(exc)
            raise EngineInitializationError(
                f"Failed to load Wav2Vec2 model '{target}': {exc}"
            ) from exc

        self._processor = processor
        self._model = model

        # Track exact HF revision commit hash if available
        commit_hash = getattr(getattr(model, "config", None), "_commit_hash", None)
        self._resolved_revision = commit_hash or self.revision

        logger.info(
            "Wav2Vec2 model ready: %s (revision: %s)",
            self.model_name,
            self._resolved_revision,
        )
        return self._processor, self._model

    # -- lifecycle -----------------------------------------------------------

    async def initialize(self) -> None:
        async with self._lock:
            await self._ensure_model()

    async def health_check(self) -> EngineHealth:
        if not self.is_available():
            return EngineHealth(
                status="unavailable",
                detail="Wav2Vec2 package not installed "
                "(pip install -r requirements-speech-wav2vec2.txt)",
                model_loaded=False,
            )
        if self._model is None:
            return EngineHealth(
                status="degraded",
                detail=f"package installed but model '{self.model_name}' not loaded in memory",
                model_loaded=False,
            )
        return EngineHealth(
            status="healthy",
            detail=f"model {self.model_name} (revision: {self._resolved_revision or self.revision}) loaded on {self.device}",
            model_loaded=True,
        )

    async def shutdown(self) -> None:
        async with self._lock:
            self._processor = None
            self._model = None
            self._resolved_revision = None
            gc.collect()

    # -- transcription ---------------------------------------------------------

    async def transcribe(
        self,
        audio: AudioData,
        language: str | None = None,
    ) -> TranscriptionResult:
        if audio.samples.size == 0:
            raise TranscriptionFailed("AudioData contains zero samples.")
        if audio.sample_rate != self.sample_rate:
            raise TranscriptionFailed(
                f"wav2vec2 expects {self.sample_rate} Hz; got {audio.sample_rate}. "
                "Prepare audio through app.speech.audio.prepare_engine_audio."
            )
        base_lang = (language or "en").split("-")[0].lower()
        accepted = self._accepted_languages()
        if base_lang not in accepted:
            raise TranscriptionFailed(
                f"wav2vec2 model '{self.model_name}' is English-only for the "
                f"configured language set {sorted(accepted)} (got "
                f"language={language!r}). Swap SPEECH_WAV2VEC2_MODEL or adjust "
                "speech_wav2vec2_languages."
            )

        processor, model = await self._ensure_model()

        started = time.perf_counter()
        try:
            payload = await asyncio.wait_for(
                asyncio.to_thread(
                    self._transcribe_blocking,
                    processor,
                    model,
                    audio.samples,
                ),
                timeout=self.timeout_seconds,
            )
        except TimeoutError as exc:
            raise EngineTimeout(
                f"wav2vec2 transcription exceeded {self.timeout_seconds:.0f}s."
            ) from exc
        except Exception as exc:
            self.last_error = str(exc)
            raise TranscriptionFailed(f"wav2vec2 transcription failed: {exc}") from exc

        text, segments, word_timings, duration = payload
        return TranscriptionResult(
            engine=self.engine_id(),
            text=text,
            language=(language or "en").split("-")[0].lower(),
            language_probability=None,  # fixed acoustic model, no detection
            segments=segments,
            duration_seconds=duration or audio.duration_seconds,
            processing_time_seconds=time.perf_counter() - started,
            metadata={
                "model": self.model_name,
                "revision": self._resolved_revision or self.revision,
                "device": self.device,
                "architecture": "wav2vec2-ctc",
                "words_tracked": self.word_timestamps,
            },
            word_timings=word_timings,
        )

    def _transcribe_blocking(
        self,
        processor: Any,
        model: Any,
        samples: np.ndarray,
    ) -> tuple[str, list[TranscriptionSegment], list[WordTiming], float]:
        """CPU/GPU bound forward pass and CTC decoding."""
        import torch

        duration = float(samples.size / self.sample_rate)

        # 1. Feature extraction
        inputs = processor(
            samples,
            sampling_rate=self.sample_rate,
            return_tensors="pt",
            padding=True,
        )
        input_values = inputs.input_values
        if self.device != "cpu" and torch.cuda.is_available():
            input_values = input_values.to(self.device)

        # 2. Forward pass with CTC loss head
        with torch.no_grad():
            logits = model(input_values).logits

        # 3. Argmax CTC decoding
        predicted_ids = torch.argmax(logits, dim=-1)

        # 4. CTC word offsets & timestamps
        segments: list[TranscriptionSegment] = []
        word_timings: list[WordTiming] = []
        raw_text = ""

        if self.word_timestamps and hasattr(processor, "tokenizer"):
            try:
                # Hugging Face tokenizer returns word offsets for CTC models
                decoded = processor.tokenizer.decode(
                    predicted_ids[0],
                    output_word_offsets=True,
                )
                raw_text = (
                    getattr(decoded, "text", None)
                    or (decoded.get("text") if isinstance(decoded, dict) else str(decoded))
                    or ""
                ).strip()

                word_offsets = (
                    getattr(decoded, "word_offsets", None)
                    or (decoded.get("word_offsets") if isinstance(decoded, dict) else None)
                    or []
                )

                # Wav2Vec2 downsamples by a stride of 320 at 16 kHz (20ms per frame)
                stride_samples = getattr(getattr(model, "config", None), "inputs_to_logits_ratio", 320)
                time_offset = float(stride_samples / self.sample_rate)

                for item in word_offsets:
                    w_text = item.get("word", "") if isinstance(item, dict) else getattr(item, "word", "")
                    s_off = item.get("start_offset", 0) if isinstance(item, dict) else getattr(item, "start_offset", 0)
                    e_off = item.get("end_offset", 0) if isinstance(item, dict) else getattr(item, "end_offset", 0)

                    start_sec = round(float(s_off * time_offset), 3)
                    end_sec = round(float(e_off * time_offset), 3)
                    if end_sec <= start_sec:
                        end_sec = round(start_sec + time_offset, 3)

                    # Ensure within bounds
                    start_sec = min(start_sec, duration)
                    end_sec = min(max(end_sec, start_sec + 0.01), duration)

                    segments.append(
                        TranscriptionSegment(
                            start_seconds=start_sec,
                            end_seconds=end_sec,
                            text=w_text,
                        )
                    )
                    word_timings.append(
                        WordTiming(
                            start_seconds=start_sec,
                            end_seconds=end_sec,
                            confidence=None,  # CTC argmax does not fabricate confidence
                        )
                    )
            except Exception as dec_err:  # noqa: BLE001 - fallback path below
                logger.debug("CTC word offset decode fallback: %s", dec_err)

        if not raw_text:
            # Fallback direct batch decode
            decoded_batch = processor.batch_decode(predicted_ids)
            raw_text = (decoded_batch[0] if decoded_batch else "").strip()

        # If no word offsets produced segments, create a single whole-clip segment
        if not segments and raw_text:
            segments.append(
                TranscriptionSegment(
                    start_seconds=0.0,
                    end_seconds=duration,
                    text=raw_text,
                )
            )

        return raw_text, segments, word_timings, duration

    # -- streaming (chunked window) --------------------------------------------

    def transcribe_stream(
        self,
        audio: AudioData,
        chunk_seconds: float = 3.0,
    ) -> Iterator[PartialTranscription]:
        """Sliding chunked-window progressive transcription.

        Because CTC models are non-autoregressive whole-sequence encoders,
        true streaming decode requires windowed audio slicing.
        """
        if self._model is None or self._processor is None:
            raise TranscriptionFailed(
                "wav2vec2 model is not loaded; call initialize() first."
            )

        samples = audio.samples
        total_samples = samples.size
        chunk_samples = max(int(chunk_seconds * self.sample_rate), self.sample_rate)

        chunk_index = 0
        start_idx = 0
        while start_idx < total_samples:
            end_idx = min(start_idx + chunk_samples, total_samples)
            is_final = end_idx >= total_samples
            chunk_slice = samples[start_idx:end_idx]

            start_sec = round(start_idx / self.sample_rate, 3)
            end_sec = round(end_idx / self.sample_rate, 3)

            try:
                text, _, _, _ = self._transcribe_blocking(
                    self._processor,
                    self._model,
                    chunk_slice,
                )
            except Exception as exc:  # noqa: BLE001 - one bad window must not kill the stream
                logger.warning("wav2vec2 stream chunk %d failed: %s", chunk_index, exc)
                text = ""

            yield PartialTranscription(
                text=text,
                is_final=is_final,
                chunk_index=chunk_index,
                start_seconds=start_sec,
                end_seconds=end_sec,
            )

            chunk_index += 1
            start_idx = end_idx

