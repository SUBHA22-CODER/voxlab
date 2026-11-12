"""VoxLab 2.0 audio APIs: engines listing, health, upload + transcribe."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.audio import (
    EngineHealthOut,
    EngineOut,
    ScoreRequest,
    ScoreResponse,
    TranscriptionOut,
)
from app.speech.base import SpeechEngine
from app.speech.exceptions import SpeechError
from app.speech.alignment import WordTiming, align_words
from app.speech.metrics import NormalizationConfig, compute_transcript_metrics
from app.speech.semantic import analyze_semantic_errors
from app.speech.semantic_llm import judge_semantics_with_llm
from app.services.llm import LLMService
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
    use_llm_judge: bool = Form(default=False),  # advisory LLM layer is opt-in
    reference_language: str | None = Form(default=None),  # enables language_correct
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

    alignment_payload = None
    semantic_payload = None
    llm_payload = None
    metrics = None
    if reference_transcript:
        metrics = compute_transcript_metrics(
            reference_transcript,
            result.text,
            entities=[e.strip() for e in entities.split(",")] if entities else None,
            technical_vocab=[v.strip() for v in technical_vocab.split(",")] if technical_vocab else None,
            reference_language=reference_language,
            hypothesis_language=result.language,
            processing_time_seconds=result.processing_time_seconds,
            audio_duration_seconds=result.duration_seconds,
        ).to_dict()

        # Word-level localization: engine word timings join the alignment only
        # when the engine supplied them (never invented).
        timings = (
            [WordTiming(start_seconds=w.start_seconds, end_seconds=w.end_seconds, confidence=w.confidence)
             for w in result.word_timings]
            if result.word_timings
            else None
        )
        alignment_payload = align_words(reference_transcript, result.text, timings).to_dict()

        # Deterministic semantic layer (ground truth).
        entity_list = [e.strip() for e in entities.split(",") if e.strip()] if entities else None
        vocab_list = [v.strip() for v in technical_vocab.split(",") if v.strip()] if technical_vocab else None
        semantic = analyze_semantic_errors(
            reference_transcript, result.text, entities=entity_list, technical_vocab=vocab_list
        )
        semantic_payload = semantic.to_dict()

        # LLM judgment layer (advisory, fully labeled). Opt-in: transcripts
        # are only sent to the external LLM provider when the caller asks for
        # it AND a key is configured (explicit configuration + consent).
        if use_llm_judge:
            llm = LLMService()
            if llm.available:
                judgment = await judge_semantics_with_llm(llm, reference_transcript, result.text)
                llm_payload = judgment.to_dict()
            else:
                from app.speech.semantic_llm import LLMSemanticJudgment

                llm_payload = LLMSemanticJudgment(
                    available=False, provenance={"reason": "no_llm_key"}
                ).to_dict()

    return TranscriptionOut(
        **result.to_dict(),
        metrics=metrics,
        alignment=alignment_payload,
        semantic=semantic_payload,
        llm_judgment=llm_payload,
    )


@router.post("/audio/score", response_model=ScoreResponse)
async def score_transcript(
    body: ScoreRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Score a transcript from any text source against a reference.

    Built for human-in-the-loop benchmarking: dictate into your product
    (e.g. Wispr Flow types into the Audio Lab capture box), paste the
    result, and VoxLab scores it through the SAME deterministic metric,
    alignment, and semantic layers used for the engine leaderboard.
    The advisory LLM layer runs only when a key is configured AND
    use_llm_judge was enabled client-side (omitted here by default).
    """
    from datetime import UTC, datetime

    metrics = compute_transcript_metrics(
        body.reference,
        body.hypothesis,
        entities=body.entities or None,
        technical_vocab=body.technical_vocab or None,
        normalization=NormalizationConfig(expand_numbers=True),
    ).to_dict()
    alignment = align_words(body.reference, body.hypothesis).to_dict()
    semantic = analyze_semantic_errors(
        body.reference,
        body.hypothesis,
        entities=body.entities or None,
        technical_vocab=body.technical_vocab or None,
    ).to_dict()
    return ScoreResponse(
        label=body.label or f"manual-{datetime.now(UTC).strftime('%H%M%S')}",
        source="human_in_the_loop",
        reference=body.reference,
        hypothesis=body.hypothesis,
        metrics=metrics,
        alignment=alignment,
        semantic=semantic,
    )
