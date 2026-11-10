"""VoxLab 2.0 audio APIs: engines listing, health, upload + transcribe."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.audio import EngineHealthOut, EngineOut, TranscriptionOut
from app.speech.base import SpeechEngine
from app.speech.exceptions import SpeechError
from app.speech.metrics import compute_transcript_metrics
from app.speech.registry import engine_registry
from app.speech.runtime import decode_upload_to_audio, get_engine, speech_error_to_http

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["audio-v1"])


@router.get("/engines", response_model=list[EngineOut])
async def list_engines(user: User = Depends(get_current_user)):
    """Every known engine with honest install status (never aspirational)."""
    return engine_registry.describe_all()


@router.get("/engines/{engine_id}/health", response_model=EngineHealthOut)
async def engine_health(engine_id: str, user: User = Depends(get_current_user)):
    """Live health of one engine (initializes it on first call)."""
    try:
        engine: SpeechEngine = await get_engine(engine_id)
        health = await engine.health_check()
    except SpeechError as exc:
        raise speech_error_to_http(exc) from exc
    return EngineHealthOut(
        engine_id=engine_id, status=health.status,
        detail=health.detail, model_loaded=health.model_loaded,
    )


@router.post("/audio/transcribe", response_model=TranscriptionOut)
async def transcribe_audio(
    file: UploadFile = File(...),
    engine_id: str = Form(default="whisper_local"),
    language: str | None = Form(default=None),
    reference_transcript: str | None = Form(default=None),
    entities: str | None = Form(default=None),  # comma-separated
    technical_vocab: str | None = Form(default=None),  # comma-separated
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Transcribe an uploaded clip; when a reference transcript is supplied,
    the response also carries the full honest metric report (WER/CER/...)."""
    blob = await file.read()
    try:
        audio_data, _prep, _loaded = await decode_upload_to_audio(blob, file.filename)
        engine = await get_engine(engine_id)
        result = await engine.transcribe(audio_data, language=language)
    except SpeechError as exc:
        raise speech_error_to_http(exc) from exc

    metrics = None
    if reference_transcript:
        metrics = compute_transcript_metrics(
            reference_transcript,
            result.text,
            entities=[e.strip() for e in entities.split(",")] if entities else None,
            technical_vocab=[v.strip() for v in technical_vocab.split(",")] if technical_vocab else None,
            hypothesis_language=result.language,
            processing_time_seconds=result.processing_time_seconds,
            audio_duration_seconds=result.duration_seconds,
        ).to_dict()

    return TranscriptionOut(
        **result.to_dict(),
        metrics=metrics,
    )
