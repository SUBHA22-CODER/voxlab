"""VoxLab 2.0 multi-engine benchmark APIs: same audio, side-by-side engines."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.models.darwin_audio import AudioBenchmark
from app.schemas.audio import BenchmarkOut
from app.speech.exceptions import SpeechError
from app.speech.metrics import NormalizationConfig, compute_transcript_metrics
from app.speech.registry import engine_registry
from app.speech.runtime import (
    artifact_store,
    decode_upload_to_audio,
    get_engine,
    speech_error_to_http,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/benchmarks", tags=["benchmarks-v1"])


@router.post("/audio", response_model=BenchmarkOut, status_code=status.HTTP_201_CREATED)
async def benchmark_audio(
    file: UploadFile = File(...),
    reference_transcript: str | None = Form(default=None),
    engines: str | None = Form(default=None),  # comma-separated; default = all installed
    label: str = Form(default=""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run the SAME audio through multiple engines under identical conditions.

    Identical source audio, reference transcript, and normalization for every
    engine. Unavailable engines are reported as {"status": "not_installed"} —
    never fabricated rankings; missing metrics are null.
    """
    requested = [e.strip() for e in engines.split(",") if e.strip()] if engines else None
    known = engine_registry.known_engines()
    if requested:
        unknown = [e for e in requested if e not in known]
        if unknown:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown engine(s): {unknown}. Known: {known}",
            )
        targets = requested
    else:
        targets = [e for e in known if engine_registry.is_installed(e)]
        if not targets:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No speech engines installed "
                "(pip install -r requirements-speech.txt).",
            )

    blob = await file.read()
    try:
        audio_data, prep, _loaded = await decode_upload_to_audio(blob, file.filename)
    except SpeechError as exc:
        raise speech_error_to_http(exc) from exc

    store = artifact_store()
    audio_ref, audio_path = store.new_ref(f"{user.id:012x}")
    audio_path.write_bytes(blob)

    results: list[dict[str, object]] = []
    for engine_id in targets:
        entry: dict[str, object] = {"engine": engine_id}
        if not engine_registry.is_installed(engine_id):
            entry.update({"status": "not_installed",
                          "error": engine_registry.install_hint(engine_id)})
            results.append(entry)
            continue
        try:
            engine = await get_engine(engine_id)
            result = await engine.transcribe(audio_data)
            entry.update({
                "status": "ok",
                "model": engine.get_metadata().model,
                "text": result.text,
                "language": result.language,
                "processing_time_seconds": round(result.processing_time_seconds, 4),
            })
            if reference_transcript:
                report = compute_transcript_metrics(
                    reference_transcript,
                    result.text,
                    hypothesis_language=result.language,
                    processing_time_seconds=result.processing_time_seconds,
                    audio_duration_seconds=result.duration_seconds,
                    normalization=NormalizationConfig(expand_numbers=True),
                ).to_dict()
                entry["metrics"] = report
        except SpeechError as exc:
            entry.update({"status": "error", "error": str(exc)})
        results.append(entry)

    benchmark = AudioBenchmark(
        user_id=user.id,
        label=label or (file.filename or "benchmark"),
        engine_results=results,
        audio_duration_seconds=float(prep.get("duration_seconds", 0.0)),
        reference_transcript=reference_transcript or "",
        audio_ref=audio_ref,
    )
    db.add(benchmark)
    await db.commit()

    return BenchmarkOut(
        id=benchmark.id, label=benchmark.label,
        engine_results=benchmark.engine_results,
        audio_duration_seconds=benchmark.audio_duration_seconds,
        reference_transcript=benchmark.reference_transcript,
        audio_ref=benchmark.audio_ref, created_at=benchmark.created_at,
    )


@router.get("", response_model=list[BenchmarkOut])
async def list_benchmarks(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(AudioBenchmark)
            .where(AudioBenchmark.user_id == user.id)
            .order_by(AudioBenchmark.id.desc())
        )
    ).all()
    return [
        BenchmarkOut(
            id=b.id, label=b.label, engine_results=b.engine_results,
            audio_duration_seconds=b.audio_duration_seconds,
            reference_transcript=b.reference_transcript,
            audio_ref=b.audio_ref, created_at=b.created_at,
        )
        for b in rows
    ]


@router.get("/{benchmark_id}", response_model=BenchmarkOut)
async def get_benchmark(
    benchmark_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(AudioBenchmark, benchmark_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Benchmark not found")
    return BenchmarkOut(
        id=row.id, label=row.label, engine_results=row.engine_results,
        audio_duration_seconds=row.audio_duration_seconds,
        reference_transcript=row.reference_transcript,
        audio_ref=row.audio_ref, created_at=row.created_at,
    )
