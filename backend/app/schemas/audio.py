"""Pydantic schemas for the VoxLab 2.0 audio APIs (v1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# --- engines ------------------------------------------------------------------


class EngineOut(BaseModel):
    engine_id: str
    installed: bool
    capabilities: dict[str, Any] | None = None
    attribution: str | None = None
    install_hint: str | None = None


class EngineHealthOut(BaseModel):
    engine_id: str
    status: str
    detail: str
    model_loaded: bool


# --- transcription --------------------------------------------------------------


class TranscriptionOut(BaseModel):
    engine: str
    text: str
    language: str | None = None
    language_probability: float | None = None
    segments: list[dict[str, Any]] = Field(default_factory=list)
    duration_seconds: float = 0.0
    processing_time_seconds: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] | None = None  # present when a reference was given


# --- darwin audio -----------------------------------------------------------------


class DarwinAudioRunCreate(BaseModel):
    population_size: int = Field(default=4, ge=2, le=20)
    generations: int = Field(default=3, ge=1, le=20)
    top_k: int = Field(default=2, ge=1, le=10)
    personas: list[str] = Field(default_factory=list)
    seed: int = Field(default=42)
    failure_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    reference_transcript: str = Field(min_length=1)
    language: str = "en"
    engine_id: str = "whisper_local"
    entities: list[str] = Field(default_factory=list)
    technical_vocab: list[str] = Field(default_factory=list)


class DarwinAudioRunOut(BaseModel):
    id: int
    status: str
    config: dict[str, Any]
    stats: dict[str, Any]
    progress: int
    error: str | None = None
    created_at: datetime


class DarwinAudioFindingOut(BaseModel):
    id: int
    run_id: int
    persona_id: str
    genome: dict[str, Any]
    original_chain_length: int
    minimized_chain_length: int
    minimized_genome: dict[str, Any] | None = None
    fitness: float
    metrics: dict[str, Any]
    audio_artifact_ref: str
    reference_transcript: str
    failed_transcript: str
    reproduction: dict[str, Any]
    created_at: datetime


# --- regression corpus ---------------------------------------------------------------


class AudioRegressionCaseOut(BaseModel):
    id: int
    test_id: str
    engine: str
    model_version: str
    language: str
    severity: str
    failure_category: str
    seed_audio_ref: str
    chain: list[dict[str, Any]]
    seed: int
    reference_transcript: str
    expected_behavior: str
    metrics: dict[str, Any]
    tags: list[Any]
    last_run: dict[str, Any] | None = None
    created_at: datetime


class AudioRegressionRunOut(BaseModel):
    test_id: str
    status: str  # "still_failing" | "fixed" | "error"
    wer: float | None = None
    cer: float | None = None
    hypothesis: str = ""
    detail: str = ""


# --- benchmarks ------------------------------------------------------------------------


class BenchmarkOut(BaseModel):
    id: int
    label: str
    engine_results: list[dict[str, Any]]
    audio_duration_seconds: float
    reference_transcript: str
    audio_ref: str
    created_at: datetime
