# darwin_audio.py
# ORM models for the Darwin audio evolution engine (VoxLab 2.0). Additive to
# the existing text-Darwin models — nothing existing changes.

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models import utcnow


class DarwinAudioRun(Base):
    __tablename__ = "darwin_audio_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    # queued | running | completed | failed | cancelled | partial
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    # personas, population_size, generations, seed, failure_threshold,
    # seed_audio_ref, reference_transcript, language, entities, technical_vocab
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    generations: Mapped[list[DarwinAudioGeneration]] = relationship(
        back_populates="run", cascade="all, delete-orphan",
        order_by="DarwinAudioGeneration.generation_index",
    )
    findings: Mapped[list[AudioFinding]] = relationship(
        back_populates="run", cascade="all, delete-orphan",
    )


class DarwinAudioGeneration(Base):
    __tablename__ = "darwin_audio_generations"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("darwin_audio_runs.id"), index=True)
    generation_index: Mapped[int] = mapped_column(Integer)
    best_fitness: Mapped[float] = mapped_column(Float, default=0.0)
    avg_fitness: Mapped[float] = mapped_column(Float, default=0.0)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    # per-candidate evaluations: genome dict, fitness, metrics, artifact ref

    run: Mapped[DarwinAudioRun] = relationship(back_populates="generations")


class AudioFinding(Base):
    __tablename__ = "darwin_audio_findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("darwin_audio_runs.id"), index=True)
    persona_id: Mapped[str] = mapped_column(String(64))
    genome: Mapped[dict] = mapped_column(JSON)
    genome_hash: Mapped[str] = mapped_column(String(16), index=True)
    original_chain_length: Mapped[int] = mapped_column(Integer, default=0)
    minimized_chain_length: Mapped[int] = mapped_column(Integer, default=0)
    minimized_genome: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fitness: Mapped[float] = mapped_column(Float, default=0.0)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    # full TranscriptMetrics.to_dict() report
    audio_artifact_ref: Mapped[str] = mapped_column(String(512), default="")
    seed_audio_ref: Mapped[str] = mapped_column(String(512), default="")
    reference_transcript: Mapped[Text] = mapped_column(Text, default="")
    failed_transcript: Mapped[Text] = mapped_column(Text, default="")
    reproduction: Mapped[dict] = mapped_column(JSON, default=dict)
    # engine, model, seed, chain — everything needed to replay exactly
    exported_regression_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[DarwinAudioRun] = relationship(back_populates="findings")


class AudioRegressionCase(Base):
    """Persistent regression corpus entry for audio transcription failures."""

    __tablename__ = "audio_regression_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    engine: Mapped[str] = mapped_column(String(64), index=True)
    model_version: Mapped[str] = mapped_column(String(128), default="")
    language: Mapped[str] = mapped_column(String(16), default="en")
    severity: Mapped[str] = mapped_column(String(16), default="medium")  # low|medium|high|critical
    failure_category: Mapped[str] = mapped_column(String(64), default="other")
    seed_audio_ref: Mapped[str] = mapped_column(String(512), default="")
    chain: Mapped[list] = mapped_column(JSON, default=list)  # transform chain to replay
    seed: Mapped[int] = mapped_column(Integer, default=0)
    reference_transcript: Mapped[str] = mapped_column(Text, default="")
    expected_behavior: Mapped[str] = mapped_column(Text, default="")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    last_run: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # last replay result: wer/cer/status ("still_failing"|"fixed"), timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AudioBenchmark(Base):
    """Multi-engine benchmark result for one audio clip."""

    __tablename__ = "audio_benchmarks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    label: Mapped[str] = mapped_column(String(255), default="")
    engine_results: Mapped[list] = mapped_column(JSON, default=list)
    # per engine: {engine, model, text, wer, cer, processing_time_seconds,
    #              realtime_factor, language, status, error}
    audio_duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    reference_transcript: Mapped[str] = mapped_column(Text, default="")
    audio_ref: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
