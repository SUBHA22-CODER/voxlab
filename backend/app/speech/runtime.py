# runtime.py
# Shared speech-engine runtime for the API layer: one lazily-initialized
# engine instance per engine id, configured from Settings, safe under
# concurrent requests (async lock around model load).

from __future__ import annotations

import asyncio

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

from .base import SpeechEngine
from .exceptions import EngineNotInstalled, SpeechError
from .registry import engine_registry
from .whisper_local.config import WhisperLocalConfig

WHISPER_LOCAL_ID = "whisper_local"

_init_lock = asyncio.Lock()
_configured: set[str] = set()


async def get_engine(engine_id: str = WHISPER_LOCAL_ID) -> SpeechEngine:
    """Return the shared engine instance, initialized on first use.

    Raises HTTPException 503 with the honest reason when the runtime is not
    installed — the platform never pretends an uninstalled engine can work.
    """
    try:
        engine = engine_registry.get_engine(engine_id)
    except EngineNotInstalled as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    async with _init_lock:
        if engine_id == WHISPER_LOCAL_ID and engine_id not in _configured:
            settings = get_settings()
            engine.config = WhisperLocalConfig(  # type: ignore[attr-defined]
                model_key=settings.speech_whisper_model,
                device=settings.speech_device,
                compute_type=settings.speech_compute_type,
                timeout_seconds=settings.speech_timeout_seconds,
            )
            _configured.add(engine_id)
        if engine_id == "vosk" and engine_id not in _configured:
            settings = get_settings()
            if settings.speech_vosk_model_dir:
                engine._model_dir = settings.speech_vosk_model_dir  # type: ignore[attr-defined]
            _configured.add(engine_id)
        await engine.initialize()
    return engine


async def engine_dependency(engine_id: str = "whisper_local") -> SpeechEngine:
    """FastAPI dependency wrapper around get_engine."""
    return await get_engine(engine_id)


def artifact_store():
    from ..darwin_audio.artifacts import AudioArtifactStore

    return AudioArtifactStore(get_settings().audio_storage_dir)


async def decode_upload_to_audio(blob: bytes, filename: str | None, db: AsyncSession | None = None):
    """Decode an uploaded audio file into engine-ready AudioData with the
    configured limits enforced."""
    from .audio import (
        DEFAULT_MAX_DURATION_SECONDS,
        DEFAULT_MAX_UPLOAD_BYTES,
        load_audio,
        prepare_engine_audio,
        validate_duration,
    )

    settings = get_settings()
    max_bytes = min(settings.speech_max_upload_mb * 1024 * 1024, DEFAULT_MAX_UPLOAD_BYTES) \
        if settings.speech_max_upload_mb else DEFAULT_MAX_UPLOAD_BYTES
    loaded = load_audio(blob, filename=filename, max_bytes=max_bytes)
    validate_duration(loaded, max_duration=settings.speech_max_duration_seconds or DEFAULT_MAX_DURATION_SECONDS)
    samples, prep = prepare_engine_audio(loaded)
    from .base import AudioData

    return AudioData(samples=samples), prep, loaded


def speech_error_to_http(exc: SpeechError) -> HTTPException:
    """Map typed speech errors to honest HTTP status codes."""
    from .exceptions import (
        AudioCorrupt,
        AudioTooLarge,
        AudioValidationError,
        EngineTimeout,
        TranscriptionFailed,
        UnsupportedAudioFormat,
    )

    if isinstance(exc, (AudioTooLarge,)):
        return HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc))
    if isinstance(exc, (UnsupportedAudioFormat, AudioCorrupt, AudioValidationError)):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, (EngineTimeout, TranscriptionFailed)):
        return HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# Re-exported for route modules.
__all__ = [
    "artifact_store",
    "decode_upload_to_audio",
    "engine_dependency",
    "get_engine",
    "speech_error_to_http",
]
