"""VoxLab 2.0 regression corpus APIs: persistent audio failure cases + replay."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.models import User
from app.models.darwin_audio import AudioFinding, AudioRegressionCase
from app.schemas.audio import AudioRegressionCaseOut, AudioRegressionRunOut
from app.speech.exceptions import SpeechError
from app.speech.metrics import NormalizationConfig, compute_transcript_metrics
from app.speech.runtime import get_engine, speech_error_to_http

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/regressions", tags=["regressions-v1"])

# Replay classification thresholds (documented, not magic):
#   WER <= FIXED_WER          -> "fixed" (engine now transcribes this clip well)
#   WER >= 0.5 * baseline WER -> "still_failing"
#   otherwise                 -> "improved"
FIXED_WER = 0.10
STILL_FAILING_RATIO = 0.5


async def create_case_from_finding(
    db: AsyncSession, finding: AudioFinding, user_id: int
) -> AudioRegressionCase:
    """Persist a finding as a replayable regression case."""
    reproduction = finding.reproduction or {}
    worst = finding.metrics.get("ground_truth", {})
    case = AudioRegressionCase(
        test_id=uuid.uuid4().hex[:12],
        user_id=user_id,
        engine=reproduction.get("engine", "whisper_local"),
        model_version=str(reproduction.get("model") or ""),
        language="en",
        severity=_severity_from_wer(worst.get("wer")),
        failure_category=finding.persona_id,
        seed_audio_ref=finding.run.config.get("seed_audio_ref", "") if finding.run else "",
        chain=(finding.minimized_genome or finding.genome).get("transform_chain", []),
        seed=int(reproduction.get("seed", 0)),
        reference_transcript=finding.reference_transcript,
        expected_behavior=(
            f"Engine must transcribe this clip with WER <= {FIXED_WER:.2f} "
            f"(baseline failure WER was {worst.get('wer', 'n/a')})."
        ),
        metrics=finding.metrics,
        tags=["darwin", finding.persona_id],
    )
    db.add(case)
    await db.commit()
    return case


def _severity_from_wer(wer: float | None) -> str:
    if wer is None:
        return "medium"
    if wer >= 0.8:
        return "critical"
    if wer >= 0.5:
        return "high"
    if wer >= 0.25:
        return "medium"
    return "low"


async def _user_case(db: AsyncSession, case_id: int, user: User) -> AudioRegressionCase:
    case = await db.get(AudioRegressionCase, case_id)
    if case is None or case.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Regression case not found")
    return case


@router.get("", response_model=list[AudioRegressionCaseOut])
async def list_cases(
    engine: str | None = None,
    severity: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Browse the regression corpus (optionally filtered)."""
    query = select(AudioRegressionCase).where(AudioRegressionCase.user_id == user.id)
    if engine:
        query = query.where(AudioRegressionCase.engine == engine)
    if severity:
        query = query.where(AudioRegressionCase.severity == severity)
    rows = (await db.scalars(query.order_by(AudioRegressionCase.id.desc()))).all()
    return [
        AudioRegressionCaseOut(
            id=c.id, test_id=c.test_id, engine=c.engine,
            model_version=c.model_version, language=c.language,
            severity=c.severity, failure_category=c.failure_category,
            seed_audio_ref=c.seed_audio_ref, chain=c.chain, seed=c.seed,
            reference_transcript=c.reference_transcript,
            expected_behavior=c.expected_behavior, metrics=c.metrics,
            tags=c.tags, last_run=c.last_run, created_at=c.created_at,
        )
        for c in rows
    ]


@router.post("/from-finding/{finding_id}", response_model=AudioRegressionCaseOut,
             status_code=status.HTTP_201_CREATED)
async def promote_finding(
    finding_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Promote a Darwin audio finding into the persistent regression corpus."""
    finding = await db.get(
        AudioFinding, finding_id, options=[selectinload(AudioFinding.run)]
    )
    if finding is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")
    run = finding.run
    if run is None or run.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")
    case = await create_case_from_finding(db, finding, user.id)
    return AudioRegressionCaseOut(
        id=case.id, test_id=case.test_id, engine=case.engine,
        model_version=case.model_version, language=case.language,
        severity=case.severity, failure_category=case.failure_category,
        seed_audio_ref=case.seed_audio_ref, chain=case.chain, seed=case.seed,
        reference_transcript=case.reference_transcript,
        expected_behavior=case.expected_behavior, metrics=case.metrics,
        tags=case.tags, last_run=case.last_run, created_at=case.created_at,
    )


@router.post("/{case_id}/run", response_model=AudioRegressionRunOut)
async def replay_case(
    case_id: int,
    engine_id: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Replay a regression case through the engine now and classify the result."""
    case = await _user_case(db, case_id, user)

    from app.darwin_audio.artifacts import ArtifactError
    from app.speech.base import AudioData
    from app.speech.runtime import artifact_store
    from app.speech.audio import load_audio, prepare_engine_audio
    from app.speech.transforms import apply_chain, TransformSpec

    engine = await get_engine(engine_id or case.engine)
    try:
        store = artifact_store()
        seed_blob = store.read_bytes(case.seed_audio_ref)
        loaded = load_audio(seed_blob, filename="seed.wav")
        seed_samples, _ = prepare_engine_audio(loaded)
        chain = [TransformSpec.from_dict(s) for s in (case.chain or [])]
        candidate = apply_chain(seed_samples, 16000, chain)
        result = await engine.transcribe(AudioData(samples=candidate), language=case.language or None)
    except (SpeechError, ArtifactError) as exc:
        raise speech_error_to_http(exc) from exc

    report = compute_transcript_metrics(
        case.reference_transcript,
        result.text,
        hypothesis_language=result.language,
        processing_time_seconds=result.processing_time_seconds,
        audio_duration_seconds=result.duration_seconds,
        normalization=NormalizationConfig(expand_numbers=True),
    )
    baseline_wer = float((case.metrics or {}).get("ground_truth", {}).get("wer", 1.0) or 1.0)
    wer = report.wer
    if wer <= FIXED_WER:
        replay_status = "fixed"
    elif wer >= STILL_FAILING_RATIO * baseline_wer:
        replay_status = "still_failing"
    else:
        replay_status = "improved"

    case.last_run = {
        "status": replay_status,
        "wer": round(wer, 4),
        "cer": round(report.cer, 4),
        "hypothesis": result.text,
        "engine": engine.engine_id(),
        "model": engine.get_metadata().model,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    await db.commit()

    return AudioRegressionRunOut(
        test_id=case.test_id, status=replay_status, wer=round(wer, 4),
        cer=round(report.cer, 4), hypothesis=result.text,
    )


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a case (privacy-aware deletion, owner-only)."""
    case = await _user_case(db, case_id, user)
    await db.delete(case)
    await db.commit()
