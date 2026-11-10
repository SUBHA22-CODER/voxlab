"""VoxLab 2.0 Darwin audio APIs: evolutionary transcription-failure discovery."""

from __future__ import annotations

import logging

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.darwin_audio.artifacts import AudioArtifactStore
from app.darwin_audio.evolution import DarwinAudioEngine
from app.darwin_audio.personas import AUDIO_PERSONAS
from app.darwin_audio.personas import get_audio_personas as resolve_personas
from app.models import User, utcnow
from app.models.darwin_audio import DarwinAudioRun
from app.schemas.audio import (
    DarwinAudioFindingOut,
    DarwinAudioRunCreate,
    DarwinAudioRunOut,
)
from app.speech.exceptions import SpeechError
from app.speech.registry import engine_registry
from app.speech.runtime import (
    artifact_store,
    decode_upload_to_audio,
    speech_error_to_http,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/darwin/audio", tags=["darwin-audio-v1"])


def _get_darwin_engine(db_session_factory) -> DarwinAudioEngine:
    settings = get_settings()
    return DarwinAudioEngine(
        db_session_factory,
        AudioArtifactStore(settings.audio_storage_dir),
        engine_registry,
    )


@router.get("/personas")
async def list_audio_personas(user: User = Depends(get_current_user)):
    """Audio attack personas (presets + content personas, honestly labeled)."""
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "is_content_persona": p.is_content_persona,
            "is_dictation_focused": p.is_dictation_focused,
            "preset_operators": [s.operator for s in p.preset],
        }
        for p in AUDIO_PERSONAS.values()
    ]


@router.get("/transforms")
async def list_transforms(user: User = Depends(get_current_user)):
    """Catalog of every audio transform operator with parameter bounds."""
    from app.speech.transforms import list_transforms as catalog

    return catalog()


@router.post("/evolve", response_model=DarwinAudioRunOut, status_code=status.HTTP_202_ACCEPTED)
async def start_audio_evolution(
    file: UploadFile = File(...),
    reference_transcript: str = Form(...),
    engine_id: str = Form(default="whisper_local"),
    language: str = Form(default="en"),
    population_size: int = Form(default=4),
    generations: int = Form(default=3),
    top_k: int = Form(default=2),
    seed: int = Form(default=42),
    failure_threshold: float = Form(default=0.5),
    personas: str | None = Form(default=None),  # comma-separated ids
    entities: str | None = Form(default=None),
    technical_vocab: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload seed audio + its reference transcript and start an evolution run.

    Returns 202 immediately; the run executes in the background with live
    progress in GET /api/v1/darwin/audio/runs/{id}.
    """
    # Validate persona ids up front (fail fast, honestly).
    requested = [p.strip() for p in personas.split(",") if p.strip()] if personas else None
    try:
        resolve_personas(requested)
    except KeyError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    blob = await file.read()
    try:
        await decode_upload_to_audio(blob, file.filename)
    except SpeechError as exc:
        raise speech_error_to_http(exc) from exc

    store = artifact_store()
    run_scope = f"{user.id:012x}"
    seed_ref, seed_path = store.new_ref(run_scope)
    seed_path.write_bytes(blob)

    config = {
        "population_size": population_size,
        "generations": generations,
        "top_k": top_k,
        "seed": seed,
        "failure_threshold": failure_threshold,
        "personas": requested,
        "reference_transcript": reference_transcript,
        "language": language,
        "engine_id": engine_id,
        "seed_audio_ref": seed_ref,
        "seed_filename": file.filename,
        "entities": [e.strip() for e in entities.split(",")] if entities else [],
        "technical_vocab": [v.strip() for v in technical_vocab.split(",")] if technical_vocab else [],
    }
    # The typed schema double-checks bounds (single validation source).
    DarwinAudioRunCreate(**{**config, "personas": requested or []})

    run = DarwinAudioRun(user_id=user.id, status="queued", config=config, stats={}, progress=0)
    db.add(run)
    await db.commit()

    darwin = _get_darwin_engine(db.bind)
    await darwin.start_run(run.id)
    return DarwinAudioRunOut(
        id=run.id, status=run.status, config=run.config,
        stats=run.stats, progress=run.progress, error=run.error,
        created_at=run.created_at,
    )


@router.get("/runs", response_model=list[DarwinAudioRunOut])
async def list_runs(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(DarwinAudioRun)
            .where(DarwinAudioRun.user_id == user.id)
            .order_by(DarwinAudioRun.id.desc())
        )
    ).all()
    return [
        DarwinAudioRunOut(
            id=r.id, status=r.status, config=r.config, stats=r.stats,
            progress=r.progress, error=r.error, created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/runs/{run_id}", response_model=DarwinAudioRunOut)
async def get_run(run_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    run = await db.get(DarwinAudioRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return DarwinAudioRunOut(
        id=run.id, status=run.status, config=run.config, stats=run.stats,
        progress=run.progress, error=run.error, created_at=run.created_at,
    )


@router.post("/runs/{run_id}/cancel", response_model=DarwinAudioRunOut)
async def cancel_run(run_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    run = await db.get(DarwinAudioRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    darwin = _get_darwin_engine(db.bind)
    await darwin.cancel_run(run_id)
    run.status = "cancelled"
    run.finished_at = utcnow()
    await db.commit()
    return DarwinAudioRunOut(
        id=run.id, status=run.status, config=run.config, stats=run.stats,
        progress=run.progress, error=run.error, created_at=run.created_at,
    )


@router.get("/runs/{run_id}/findings", response_model=list[DarwinAudioFindingOut])
async def list_findings(run_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    run = await db.get(
        DarwinAudioRun, run_id, options=[selectinload(DarwinAudioRun.findings)]
    )
    if run is None or run.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return [
        DarwinAudioFindingOut(
            id=f.id, run_id=f.run_id, persona_id=f.persona_id, genome=f.genome,
            original_chain_length=f.original_chain_length,
            minimized_chain_length=f.minimized_chain_length,
            minimized_genome=f.minimized_genome, fitness=f.fitness,
            metrics=f.metrics, audio_artifact_ref=f.audio_artifact_ref,
            reference_transcript=f.reference_transcript,
            failed_transcript=f.failed_transcript, reproduction=f.reproduction,
            created_at=f.created_at,
        )
        for f in run.findings
    ]
