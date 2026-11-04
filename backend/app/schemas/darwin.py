"""Pydantic schemas for Darwin fuzzing API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DarwinRunCreate(BaseModel):
    agent_id: int
    population_size: int = Field(default=6, ge=2, le=30)
    generations: int = Field(default=5, ge=1, le=20)
    top_k: int = Field(default=2, ge=1, le=10)
    personas: list[str] = Field(default_factory=list)
    seed: int = Field(default=42)
    failure_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    judge_mode: str = Field(default="auto")


class DarwinGenerationOut(BaseModel):
    id: int
    generation_index: int
    best_fitness: float
    avg_fitness: float
    stats: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class DarwinFindingOut(BaseModel):
    id: int
    run_id: int
    persona: str
    strategy: str
    genome: dict[str, Any]
    minimized_steps: list[dict[str, Any]]
    original_steps_count: int
    minimized_steps_count: int
    fitness: float
    diagnosis: dict[str, Any]
    trace_id: str | None = None
    session_id: int | None = None
    exported_scenario_id: int | None = None
    patch_proposal: dict[str, Any] | None = None
    created_at: datetime


class DarwinRunOut(BaseModel):
    id: int
    agent_id: int
    status: str
    config: dict[str, Any]
    stats: dict[str, Any]
    progress: int
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class DarwinRunDetail(DarwinRunOut):
    generations_data: list[DarwinGenerationOut] = Field(default_factory=list)
    findings: list[DarwinFindingOut] = Field(default_factory=list)


class DarwinPersonaOut(BaseModel):
    id: str
    name: str
    description: str
    is_dictation_focused: bool
    strategies: list[str]
