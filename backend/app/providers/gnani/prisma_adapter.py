# prisma_adapter.py
# Adapter integrating Gnani AI Prisma STT into VoxLab's SpeechEngine interface.
# Enables standard WER/CER evaluation, benchmark comparisons, and Darwin testing.

from __future__ import annotations

import io
import time
import wave

import numpy as np

from ...core.config import get_settings
from ...speech.base import (
    AudioData,
    EngineCapabilities,
    EngineHealth,
    EngineMetadata,
    SpeechEngine,
    TranscriptionResult,
    TranscriptionSegment,
)
from ...speech.exceptions import EngineNotInstalled, TranscriptionFailed
from .client import GnaniClient, GnaniAuthenticationError, GnaniRateLimitError
from .languages import supported_stt_languages, get_indic_language

ATTRIBUTION = (
    "Gnani AI Prisma Speech-to-Text: Enterprise Indic multilingual ASR platform "
    "covering 12+ Indian languages and code-switching dialects. https://docs.gnani.ai/"
)


class GnaniPrismaEngine(SpeechEngine):
    """SpeechEngine adapter for Gnani AI Prisma STT (v2.5 / v3.0)."""

    ATTRIBUTION = ATTRIBUTION

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.gnani_api_key
        self.base_url = base_url or settings.gnani_base_url
        self.model_name = model_name or settings.gnani_stt_model or "prisma-v2.5"
        self.timeout_seconds = timeout_seconds
        self._client = GnaniClient(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout_seconds=self.timeout_seconds,
        )

    @classmethod
    def engine_id(cls) -> str:
        return "gnani_prisma"

    @classmethod
    def is_available(cls) -> bool:
        """True only when GNANI_ENABLED is true and GNANI_API_KEY is configured."""
        settings = get_settings()
        return bool(settings.gnani_enabled and settings.gnani_api_key)

    @classmethod
    def install_hint(cls) -> str:
        return (
            "Gnani Prisma STT requires GNANI_ENABLED=true and a valid GNANI_API_KEY "
            "configured in environment variables. See docs/GNANI_INTEGRATION.md"
        )

    @classmethod
    def describe_capabilities(cls) -> EngineCapabilities:
        return EngineCapabilities(
            languages=supported_stt_languages(),
            supports_timestamps=False,  # Prisma REST v2.5 provides utterance-level transcript
            supports_language_detection=True,  # 'indic-auto'
            streaming_mode="none",
            max_audio_duration_seconds=600.0,
        )

    def get_capabilities(self) -> EngineCapabilities:
        return self.describe_capabilities()

    def get_metadata(self) -> EngineMetadata:
        return EngineMetadata(
            engine_id=self.engine_id(),
            display_name="Gnani Prisma STT",
            version="2.5",
            model=self.model_name,
            device="cloud-api",
            compute_type="fp16",
            attribution=self.ATTRIBUTION,
            installed=self.is_available(),
        )

    async def initialize(self) -> None:
        """Validate API client setup."""
        if not self.is_available():
            raise EngineNotInstalled(self.install_hint())

    async def health_check(self) -> EngineHealth:
        check = await self._client.health_check()
        return EngineHealth(
            status="healthy" if check.status == "healthy" else "unhealthy",
            detail=check.detail,
            model_loaded=check.has_api_key,
        )

    def _audio_to_wav_bytes(self, audio: AudioData) -> bytes:
        """Convert float32 AudioData samples into standard 16-bit PCM WAV bytes."""
        samples_int16 = (np.clip(audio.samples, -1.0, 1.0) * 32767.0).astype(np.int16)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(audio.sample_rate)
            wf.writeframes(samples_int16.tobytes())
        return buffer.getvalue()

    async def transcribe(
        self,
        audio: AudioData,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe speech audio using Gnani Prisma STT API."""
        if audio.samples.size == 0:
            raise TranscriptionFailed("AudioData contains zero samples.")

        target_lang = "hi-IN"
        if language:
            lang_obj = get_indic_language(language)
            target_lang = lang_obj.code if lang_obj else language

        wav_bytes = self._audio_to_wav_bytes(audio)
        started = time.perf_counter()

        try:
            res = await self._client.transcribe(
                audio_bytes=wav_bytes,
                filename="voxlab_sample.wav",
                model=self.model_name,
                language_code=target_lang,
            )
        except GnaniAuthenticationError as exc:
            raise TranscriptionFailed(f"Gnani Prisma authentication failed: {exc}") from exc
        except GnaniRateLimitError as exc:
            raise TranscriptionFailed(f"Gnani Prisma rate limit exceeded: {exc}") from exc
        except Exception as exc:
            raise TranscriptionFailed(f"Gnani Prisma transcription failed: {exc}") from exc

        duration = audio.duration_seconds
        segments = [
            TranscriptionSegment(
                start_seconds=0.0,
                end_seconds=duration,
                text=res.transcript,
            )
        ] if res.transcript else []

        return TranscriptionResult(
            engine=self.engine_id(),
            text=res.transcript,
            language=res.detected_language_code or target_lang,
            language_probability=1.0,
            segments=segments,
            duration_seconds=duration,
            processing_time_seconds=res.processing_time or (time.perf_counter() - started),
            metadata={
                "model": res.model,
                "request_id": res.request_id,
                "provider": "gnani.ai",
                "architecture": "indic-conformer-asr",
            },
            word_timings=[],
        )

