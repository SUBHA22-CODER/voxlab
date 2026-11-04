"""SQLAlchemy models for Darwin — Fuzzing and CI for Voice & Dictation pipelines."""

from __future__ import annotations

from datetime import datetime
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models import utcnow


class DarwinRun(Base):
    __tablename__ = "darwin_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    # queued | running | completed | failed | cancelled
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    # {population_size, generations, top_k, personas: [...], seed, max_sessions, failure_threshold}
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    # {current_generation, total_generations, sessions_executed, best_fitness, avg_fitness}
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    findings: Mapped[list["DarwinFinding"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    generations_data: Mapped[list["DarwinGeneration"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="DarwinGeneration.generation_index"
    )


class DarwinGeneration(Base):
    __tablename__ = "darwin_generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("darwin_runs.id"), index=True)
    generation_index: Mapped[int] = mapped_column(Integer, index=True)
    best_fitness: Mapped[float] = mapped_column(Float, default=0.0)
    avg_fitness: Mapped[float] = mapped_column(Float, default=0.0)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped["DarwinRun"] = relationship(back_populates="generations_data")


class DarwinFinding(Base):
    __tablename__ = "darwin_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("darwin_runs.id"), index=True)
    persona: Mapped[str] = mapped_column(String(64), index=True)
    strategy: Mapped[str] = mapped_column(String(255))
    genome: Mapped[dict] = mapped_column(JSON, default=dict)
    minimized_steps: Mapped[list] = mapped_column(JSON, default=list)
    original_steps_count: Mapped[int] = mapped_column(Integer, default=0)
    minimized_steps_count: Mapped[int] = mapped_column(Integer, default=0)
    fitness: Mapped[float] = mapped_column(Float, default=0.0)
    # {category, summary, evidence_event_ids, confidence, suggested_fix_area}
    diagnosis: Mapped[dict] = mapped_column(JSON, default=dict)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exported_scenario_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Phase 2: {proposed_patch, status, before_score, after_score, diff, verified}
    patch_proposal: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped["DarwinRun"] = relationship(back_populates="findings")
