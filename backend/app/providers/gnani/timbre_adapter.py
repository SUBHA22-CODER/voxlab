# timbre_adapter.py
# Adapter for Gnani AI Timbre Text-to-Speech (TTS v2.5 / v3.0).
# Powers the Indic Speech Lab audio generation, pronunciation tests, and agent voice output.

from __future__ import annotations

import logging
from typing import Any

from ...core.config import get_settings
from .client import GnaniClient
from .languages import TIMBRE_VOICES, get_indic_language, supported_tts_languages
from .schemas import TimbreAudioConfig, TimbreTTSResponse

logger = logging.getLogger("voxlab.providers.gnani.timbre")


class GnaniTimbreEngine:
    """Service adapter for Gnani Timbre Text-to-Speech synthesis."""

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
        self.model_name = model_name or settings.gnani_tts_model or "timbre-v2.5"
        self.timeout_seconds = timeout_seconds
        self._client = GnaniClient(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout_seconds=self.timeout_seconds,
        )

    @classmethod
    def is_available(cls) -> bool:
        settings = get_settings()
        return bool(settings.gnani_enabled and settings.gnani_api_key)

    @classmethod
    def list_voices(cls) -> list[dict[str, Any]]:
        return TIMBRE_VOICES

    @classmethod
    def list_languages(cls) -> list[str]:
        return supported_tts_languages()

    async def synthesize(
        self,
        text: str,
        voice: str = "Nalini",
        language: str = "hi-IN",
        speed: float = 1.0,
        sample_rate: int = 16000,
    ) -> TimbreTTSResponse:
        """Synthesize text into speech audio bytes."""
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Text to synthesize must not be empty.")

        lang_obj = get_indic_language(language)
        target_lang = lang_obj.code if lang_obj else language

        cfg = TimbreAudioConfig(
            encoding="linear_pcm",
            container="wav",
            num_channels=1,
            sample_rate=sample_rate,
            sample_width=2,
        )

        return await self._client.synthesize(
            text=clean_text,
            voice=voice,
            model=self.model_name,
            language=target_lang,
            speed=speed,
            audio_config=cfg,
        )

