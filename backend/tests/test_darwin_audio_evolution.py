# test_darwin_audio_evolution.py
# Offline tests for the Darwin audio evolution loop and chain minimizer.
# A deterministic stub engine replaces faster-whisper: transcribe() returns a
# fixed wrong transcript, guaranteeing findings without any model. Budget
# behavior, persistence, minimization honesty, and artifact storage are the
# contracts under test.

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.darwin_audio.artifacts import AudioArtifactStore, ArtifactError
from app.darwin_audio.evolution import DarwinAudioEngine
from app.darwin_audio.genome import AudioGenome, build_random_genome
from app.darwin_audio.minimizer import minimize_audio_finding
from app.darwin_audio.personas import AUDIO_PERSONAS
from app.models import User
from app.models.darwin_audio import AudioFinding, DarwinAudioGeneration, DarwinAudioRun
from app.speech.base import (
    AudioData,
    EngineCapabilities,
    EngineHealth,
    EngineMetadata,
    PartialTranscription,
    SpeechEngine,
    TranscriptionResult,
)
from app.speech.exceptions import TranscriptionFailed

SR = 16000
WRONG_TRANSCRIPT = "completely different words appear here entirely"


class StubEngine(SpeechEngine):
    """Deterministic engine: always returns the same wrong transcript."""

    @classmethod
    def engine_id(cls) -> str:
        return "stub"

    @classmethod
    def is_available(cls) -> bool:
        return True

    async def initialize(self) -> None:
        return None

    async def health_check(self) -> EngineHealth:
        return EngineHealth(status="healthy", detail="stub", model_loaded=True)

    async def transcribe(self, audio: AudioData, language: str | None = None) -> TranscriptionResult:
        return TranscriptionResult(
            engine="stub",
            text=WRONG_TRANSCRIPT,
            language="en",
            language_probability=0.99,
            duration_seconds=audio.duration_seconds,
            processing_time_seconds=0.01,
        )

    def transcribe_stream(self, audio: AudioData, chunk_seconds: float = 3.0):
        raise TranscriptionFailed("stub has no streaming")

    def get_capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(streaming_mode="none")

    def get_metadata(self) -> EngineMetadata:
        return EngineMetadata(engine_id="stub", display_name="Stub", model="stub-1", device="cpu")

    async def shutdown(self) -> None:
        return None


def _tone(seconds: float = 1.0) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    return (0.5 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'audio.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def run_row(db, tmp_path):
    async with db() as session:
        user = User(email="audio-darwin@voxlab.dev", password_hash="x")
        session.add(user)
        await session.flush()
        run = DarwinAudioRun(
            user_id=user.id,
            status="queued",
            config={
                "personas": ["noisy_environment_speaker", "fast_technical_speaker"],
                "population_size": 2,
                "generations": 2,
                "top_k": 2,
                "seed": 42,
                "failure_threshold": 0.4,
                "reference_transcript": "deploy the service now please",
                "seed_audio_ref": "",
                "language": "en",
            },
            stats={},
            progress=0,
        )
        session.add(run)
        await session.commit()
        return run.id


@pytest.mark.asyncio
async def test_full_run_completes_and_produces_findings(db, run_row, tmp_path):
    store = AudioArtifactStore(tmp_path / "artifacts")
    registry_stub = type("R", (), {})()  # minimal duck-typed registry
    registry_stub.get_engine = lambda _engine_id: StubEngine()

    engine = DarwinAudioEngine(db, store, registry_stub)
    await engine._execute(run_row, seed_audio_override=_tone(1.0))

    async with db() as session:
        run = await session.get(DarwinAudioRun, run_row)
        assert run.status == "completed"
        assert run.progress == 100
        assert run.stats["sessions_executed"] <= 4  # pop 2 x gen 2
        assert run.stats["findings"] >= 1

        generations = (
            await session.scalars(
                select(DarwinAudioGeneration).where(DarwinAudioGeneration.run_id == run_row)
            )
        ).all()
        assert len(generations) == 2

        findings = (
            await session.scalars(
                select(AudioFinding).where(AudioFinding.run_id == run_row)
            )
        ).all()
        assert len(findings) >= 1
        finding = findings[0]
        assert finding.fitness >= 0.4
        assert finding.failed_transcript == WRONG_TRANSCRIPT
        assert finding.reproduction["engine"] == "stub"
        assert finding.reproduction["instructions"]
        # candidate artifact really stored on disk
        assert store.exists(finding.audio_artifact_ref)
        # metrics report is the full honest structure
        assert "ground_truth" in finding.metrics
        assert "heuristic" in finding.metrics


@pytest.mark.asyncio
async def test_budget_clamp_shrinks_generations(db, tmp_path):
    async with db() as session:
        user = User(email="budget@voxlab.dev", password_hash="x")
        session.add(user)
        await session.flush()
        run = DarwinAudioRun(
            user_id=user.id,
            status="queued",
            config={
                "population_size": 8,
                "generations": 50,  # 8*50=400 >> 60 -> clamped to 7
                "reference_transcript": "hello world",
            },
            stats={},
            progress=0,
        )
        session.add(run)
        await session.commit()
        run_id = run.id

    store = AudioArtifactStore(tmp_path / "artifacts")
    registry_stub = type("R", (), {})()
    registry_stub.get_engine = lambda _eid: StubEngine()
    engine = DarwinAudioEngine(db, store, registry_stub)
    await engine._execute(run_id, seed_audio_override=_tone(0.3))

    async with db() as session:
        run = await session.get(DarwinAudioRun, run_id)
        assert run.config["generations"] == 7
        assert run.stats["sessions_executed"] <= 60


@pytest.mark.asyncio
async def test_missing_seed_audio_fails_run_cleanly(db, run_row, tmp_path):
    store = AudioArtifactStore(tmp_path / "artifacts")
    registry_stub = type("R", (), {})()
    registry_stub.get_engine = lambda _eid: StubEngine()
    engine = DarwinAudioEngine(db, store, registry_stub)
    await engine._execute(run_row, seed_audio_override=None)

    async with db() as session:
        run = await session.get(DarwinAudioRun, run_row)
        assert run.status == "failed"
        assert "Seed audio" in (run.error or "")


async def test_minimizer_removes_irrelevant_steps():
    # Failure persists only while 'change_volume' remains in the chain.
    persona = AUDIO_PERSONAS["noisy_environment_speaker"]
    genome = build_random_genome(
        persona=persona, seed_audio_ref="s.wav",
        reference_text="hello world", seed=7, generation=1,
    )
    genome.transform_chain.append(
        type(genome.transform_chain[0])(
            operator="change_volume", params={"gain_db": -12.0}, seed=99
        )
    )

    async def evaluate(candidate: AudioGenome) -> float:
        chain_ops = [s.operator for s in candidate.transform_chain]
        return 0.8 if "change_volume" in chain_ops else 0.0

    result = await minimize_audio_finding(genome, evaluate, max_evaluations=25)
    assert result.failure_reproduced is True
    assert result.minimized_genome is not None
    assert [s.operator for s in result.minimized_genome.transform_chain] == ["change_volume"]
    assert result.minimized_steps < result.original_steps
    assert result.evaluations_used <= 25


async def test_minimizer_refuses_when_baseline_not_reproduced():
    persona = AUDIO_PERSONAS["fast_technical_speaker"]
    genome = build_random_genome(
        persona=persona, seed_audio_ref="s.wav",
        reference_text="hello", seed=3, generation=0,
    )

    async def evaluate(_candidate: AudioGenome) -> float:
        return 0.0  # nothing ever fails

    result = await minimize_audio_finding(genome, evaluate, max_evaluations=10)
    assert result.failure_reproduced is False
    assert result.minimized_genome is None


def test_artifact_store_rejects_path_traversal():
    store = AudioArtifactStore(Path("data/audio"))
    with pytest.raises(ArtifactError):
        store.read_bytes("../../etc/passwd")
    with pytest.raises(ArtifactError):
        store.read_bytes("not-hex/garbage.wav")
    assert store.exists("../../etc/passwd") is False
