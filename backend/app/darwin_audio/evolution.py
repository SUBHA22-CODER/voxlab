# evolution.py
# The Darwin audio evolution loop (VoxLab 2.0 Phase 4).
#
#   SEED AUDIO + REFERENCE TRANSCRIPT
#     -> per-persona genome population (persona presets + content mutations)
#     -> materialize (TTS content mutations or seeded audio transforms)
#     -> transcribe (real speech engine via the registry)
#     -> compare vs effective reference (WER/CER/number/entity metrics)
#     -> failure scoring with validity gates (fitness.py)
#     -> selection of the strongest failures
#     -> mutation / crossover breeding
#     -> ddmin minimization of finding chains (minimizer.py)
#     -> persisted AudioFindings = the regression corpus
#
# Engineering rules honored:
# - Hard budget cap via app.core.limits (DARWIN_MAX_SESSIONS, default 60);
#   every transcription is a session; the loop stops, never bypasses.
# - No database transaction is held across a transcription call: each
#   evaluation is a short atomic commit, matching the AGENTS.md rule.
# - Engine errors are harness failures, not adversarial successes — the
#   candidate is recorded invalid, never rewarded.

from __future__ import annotations

import asyncio
import logging
import random
import time
import wave
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.limits import clamp_generations, max_darwin_sessions
from app.models.darwin_audio import AudioFinding, DarwinAudioGeneration, DarwinAudioRun
from app.speech.audio import load_audio, prepare_engine_audio
from app.speech.base import AudioData
from app.speech.exceptions import SpeechError
from app.speech.metrics import (
    NormalizationConfig,
    compute_transcript_metrics,
)
from app.speech.registry import EngineRegistry
from app.speech.tts import is_available as tts_available
from app.speech.tts import synthesize_to_wav

from .artifacts import AudioArtifactStore
from .fitness import compute_audio_fitness
from .genome import AudioGenome, build_random_genome, crossover_genomes, mutate_genome
from .minimizer import minimize_audio_finding
from .personas import AudioPersona, get_audio_personas

logger = logging.getLogger(__name__)


@dataclass
class EvaluationRecord:
    genome: AudioGenome
    failure_score: float
    rewarded_score: float
    valid: bool
    metrics: dict[str, Any]
    failed_transcript: str
    effective_reference: str
    artifact_ref: str
    source: str
    engine_id: str
    error: str | None = None
    processing_time: float = 0.0
    gates: dict[str, bool] = field(default_factory=dict)


def _audio_rms(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))


class DarwinAudioEngine:
    """Async evolution loop for audio adversarial testing."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        artifact_store: AudioArtifactStore,
        registry: EngineRegistry,
    ) -> None:
        self.session_factory = session_factory
        self.artifacts = artifact_store
        self.registry = registry
        self._tasks: dict[int, asyncio.Task[None]] = {}

    # -- public API -----------------------------------------------------------

    async def start_run(self, run_id: int, seed_audio_override: np.ndarray | None = None) -> None:
        task = asyncio.create_task(self._execute(run_id, seed_audio_override))
        self._tasks[run_id] = task
        task.add_done_callback(lambda _t: self._tasks.pop(run_id, None))

    async def cancel_run(self, run_id: int) -> bool:
        task = self._tasks.get(run_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    # -- the loop ---------------------------------------------------------------

    async def _execute(self, run_id: int, seed_audio_override: np.ndarray | None) -> None:
        started = time.perf_counter()
        try:
            await self._run_loop(run_id, seed_audio_override, started)
        except asyncio.CancelledError:
            await self._finalize(run_id, status="cancelled", error="cancelled by user")
            raise
        except Exception as exc:
            logger.exception("Darwin audio run %s crashed", run_id)
            await self._finalize(run_id, status="failed", error=str(exc))

    async def _run_loop(
        self, run_id: int, seed_audio_override: np.ndarray | None, started: float
    ) -> None:
        cfg, personas, seed_audio, seed_sr, reference_text = await self._load_run(
            run_id, seed_audio_override
        )
        if seed_audio is None or seed_audio.size == 0:
            await self._finalize(run_id, status="failed", error="Seed audio missing or empty")
            return

        population_size = int(cfg.get("population_size", 4))
        generations = clamp_generations(population_size, int(cfg.get("generations", 3)))
        top_k = max(1, int(cfg.get("top_k", 2)))
        seed = int(cfg.get("seed", 42))
        failure_threshold = float(cfg.get("failure_threshold", 0.5))
        budget = max_darwin_sessions()
        total_expected = min(budget, population_size * generations)

        await self._patch_run(
            run_id,
            status="running",
            config_patch={"generations": generations},
            stats_patch={"total_generations": generations, "budget": budget,
                         "planned_evaluations": total_expected},
        )

        engine = self.registry.get_engine(str(cfg.get("engine_id", "whisper_local")))
        await engine.initialize()
        metadata = engine.get_metadata()

        tts_synth = self._make_tts_synth(run_id) if tts_available() else None

        # Generation 0: deterministic population across personas.
        rng = random.Random(seed)
        population: list[AudioGenome] = []
        for i in range(population_size):
            persona = personas[i % len(personas)]
            population.append(
                build_random_genome(
                    persona=persona,
                    seed_audio_ref=str(cfg.get("seed_audio_ref", "")),
                    reference_text=reference_text,
                    seed=seed + i * 1009,
                    generation=0,
                    language=str(cfg.get("language", "en")),
                )
            )

        sessions_executed = 0
        discovered: set[str] = set()
        all_records: list[EvaluationRecord] = []

        for gen_idx in range(generations):
            if sessions_executed >= budget:
                logger.info("Audio Darwin budget cap %d reached; stopping.", budget)
                break
            gen_records: list[EvaluationRecord] = []

            for genome in population:
                if sessions_executed >= budget:
                    break
                record = await self._evaluate_candidate(
                    run_id, genome, engine, metadata, seed_audio, seed_sr,
                    cfg, tts_synth,
                )
                sessions_executed += 1
                gen_records.append(record)
                await self._record_progress(
                    run_id, sessions_executed, total_expected, gen_idx, gen_records
                )

            if not gen_records:
                break

            valid_records = [r for r in gen_records if r.valid]
            scored = valid_records or gen_records
            best = max(r.rewarded_score for r in gen_records)
            avg = sum(r.rewarded_score for r in gen_records) / len(gen_records)
            await self._commit_generation(run_id, gen_idx, best, avg, gen_records)

            # Findings: every valid candidate above threshold, deduped.
            for record in gen_records:
                if (
                    record.valid
                    and record.rewarded_score >= failure_threshold
                    and record.genome.genome_id not in discovered
                ):
                    discovered.add(record.genome.genome_id)
                    all_records.append(record)
                    await self._create_finding(
                        run_id, record, metadata, engine, seed_audio, seed_sr, cfg
                    )

            # Breed next generation from the strongest failures.
            ranked = sorted(
                scored, key=lambda r: r.rewarded_score, reverse=True
            )
            survivors = [r.genome for r in ranked[:top_k]]
            next_population: list[AudioGenome] = [g for g in survivors]
            while len(next_population) < population_size:
                if rng.random() < 0.5 and len(survivors) >= 2:
                    a, b = rng.sample(survivors, 2)
                    next_population.append(crossover_genomes(a, b, seed=rng.randint(0, 2**31 - 1)))
                else:
                    parent = rng.choice(survivors)
                    next_population.append(mutate_genome(parent, mutation_seed=rng.randint(0, 2**31 - 1)))
            population = next_population[:population_size]

        best_overall = max((r.rewarded_score for r in all_records), default=0.0)
        await self._finalize(
            run_id,
            status="completed",
            stats_patch={
                "sessions_executed": sessions_executed,
                "findings": len(all_records),
                "best_failure_score": round(best_overall, 4),
                "engine": metadata.engine_id,
                "model": metadata.model,
                "wall_time_seconds": round(time.perf_counter() - started, 2),
                "tts_enabled": tts_synth is not None,
            },
        )

    # -- evaluation --------------------------------------------------------------

    async def _evaluate_candidate(
        self,
        run_id: int,
        genome: AudioGenome,
        engine: Any,
        metadata: Any,
        seed_audio: np.ndarray,
        seed_sr: int,
        cfg: dict[str, Any],
        tts_synth: Callable[[str], Any] | None,
    ) -> EvaluationRecord:
        ref, path = self.artifacts.new_ref(str(run_id))
        try:
            materialized = await genome.materialize(
                seed_audio=seed_audio, sample_rate=seed_sr, tts_synth=tts_synth
            )
            result = await engine.transcribe(
                AudioData(samples=materialized.samples, sample_rate=materialized.sample_rate),
                language=genome.seed_language or None,
            )
            report = compute_transcript_metrics(
                materialized.effective_reference,
                result.text,
                entities=cfg.get("entities") or None,
                technical_vocab=cfg.get("technical_vocab") or None,
                processing_time_seconds=result.processing_time_seconds,
                audio_duration_seconds=result.duration_seconds,
                normalization=NormalizationConfig(expand_numbers=True),
            )
            seed_duration = seed_audio.size / seed_sr
            fitness = compute_audio_fitness(
                wer=report.wer,
                cer=report.cer,
                number_accuracy=report.number_accuracy,
                entity_accuracy=report.entity_accuracy,
                semantic_overlap=report.semantic_overlap_proxy or 0.0,
                audio_rms=_audio_rms(materialized.samples),
                seed_duration=seed_duration,
                candidate_duration=materialized.samples.size / materialized.sample_rate,
            )
            with wave.open(str(path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(materialized.sample_rate)
                wav.writeframes(
                    (np.clip(materialized.samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
                )
            return EvaluationRecord(
                genome=genome,
                failure_score=fitness.failure_score,
                rewarded_score=fitness.rewarded_score,
                valid=fitness.valid,
                metrics=report.to_dict(),
                failed_transcript=result.text,
                effective_reference=materialized.effective_reference,
                artifact_ref=ref,
                source=materialized.source,
                engine_id=str(metadata.engine_id),
                processing_time=result.processing_time_seconds,
                gates=fitness.gates,
            )
        except SpeechError as exc:
            logger.warning("Candidate %s failed to evaluate: %s", genome.genome_id, exc)
            return EvaluationRecord(
                genome=genome,
                failure_score=0.0,
                rewarded_score=0.0,
                valid=False,
                metrics={},
                failed_transcript="",
                effective_reference=genome.seed_transcript,
                artifact_ref=ref,
                source="error",
                engine_id=str(metadata.engine_id),
                error=str(exc),
            )

    def _make_tts_synth(self, run_id: int) -> Callable[[str], Any]:
        async def synth(text: str) -> np.ndarray:
            _ref, path = self.artifacts.new_ref(str(run_id))
            await synthesize_to_wav(text, path)
            loaded = load_audio(path.read_bytes(), filename="tts.wav")
            samples, _prep = prepare_engine_audio(loaded)
            return samples

        return synth

    # -- persistence (short atomic transactions only) ------------------------------

    async def _load_run(
        self, run_id: int, seed_audio_override: np.ndarray | None
    ) -> tuple[dict[str, Any], list[AudioPersona], np.ndarray | None, int, str]:
        async with self.session_factory() as db:
            run = await db.get(DarwinAudioRun, run_id)
            if run is None:
                raise RuntimeError(f"Darwin audio run {run_id} not found")
            cfg = dict(run.config or {})
            personas = get_audio_personas(cfg.get("personas"))
            seed_audio: np.ndarray | None = None
            seed_sr = 16000
            if seed_audio_override is not None:
                seed_audio = np.asarray(seed_audio_override, dtype=np.float32)
            elif cfg.get("seed_audio_ref"):
                blob = self.artifacts.read_bytes(str(cfg["seed_audio_ref"]))
                loaded = load_audio(blob, filename="seed.wav")
                samples, _prep = prepare_engine_audio(loaded)
                seed_audio = samples
                seed_sr = 16000
            return cfg, personas, seed_audio, seed_sr, str(cfg.get("reference_transcript", ""))

    async def _patch_run(
        self,
        run_id: int,
        *,
        status: str | None = None,
        config_patch: dict | None = None,
        stats_patch: dict | None = None,
        progress: int | None = None,
    ) -> None:
        from app.models import utcnow

        async with self.session_factory() as db:
            run = await db.get(DarwinAudioRun, run_id)
            if run is None:
                return
            if status:
                run.status = status
                if status == "running":
                    run.started_at = utcnow()
            if config_patch:
                merged = dict(run.config or {})
                merged.update(config_patch)
                run.config = merged
            if stats_patch:
                merged = dict(run.stats or {})
                merged.update(stats_patch)
                run.stats = merged
            if progress is not None:
                run.progress = int(progress)
            await db.commit()

    async def _record_progress(
        self,
        run_id: int,
        sessions_executed: int,
        total_expected: int,
        gen_idx: int,
        gen_records: list[EvaluationRecord],
    ) -> None:
        stats_patch: dict[str, Any] = {
            "sessions_executed": sessions_executed,
            "current_generation": gen_idx,
        }
        if gen_records:
            stats_patch["best_failure_score"] = round(
                max(r.rewarded_score for r in gen_records), 4
            )
        await self._patch_run(
            run_id,
            stats_patch=stats_patch,
            progress=int((sessions_executed / max(1, total_expected)) * 100),
        )

    async def _commit_generation(
        self,
        run_id: int,
        gen_idx: int,
        best: float,
        avg: float,
        records: list[EvaluationRecord],
    ) -> None:
        async with self.session_factory() as db:
            db.add(
                DarwinAudioGeneration(
                    run_id=run_id,
                    generation_index=gen_idx,
                    best_fitness=round(float(best), 6),
                    avg_fitness=round(float(avg), 6),
                    stats={
                        "evaluations": [
                            {
                                "genome_id": r.genome.genome_id,
                                "persona_id": r.genome.persona_id,
                                "failure_score": r.failure_score,
                                "rewarded_score": r.rewarded_score,
                                "valid": r.valid,
                                "source": r.source,
                                "artifact_ref": r.artifact_ref,
                                "wer": r.metrics.get("ground_truth", {}).get("wer"),
                                "error": r.error,
                            }
                            for r in records
                        ]
                    },
                )
            )
            await db.commit()

    async def _create_finding(
        self,
        run_id: int,
        record: EvaluationRecord,
        metadata: Any,
        engine: Any,
        seed_audio: np.ndarray,
        seed_sr: int,
        cfg: dict[str, Any],
    ) -> None:
        """Minimize the failing chain, verify reproduction, persist the finding."""
        minimization = await minimize_audio_finding(
            record.genome,
            evaluate=self._make_minimize_evaluator(
                run_id, metadata, engine, seed_audio, seed_sr, cfg
            ),
        )
        minimized_genome = minimization.minimized_genome
        async with self.session_factory() as db:
            db.add(
                AudioFinding(
                    run_id=run_id,
                    persona_id=record.genome.persona_id,
                    genome=record.genome.to_dict(),
                    genome_hash=record.genome.genome_id,
                    original_chain_length=minimization.original_steps,
                    minimized_chain_length=minimization.minimized_steps,
                    minimized_genome=minimized_genome.to_dict() if minimized_genome else None,
                    fitness=record.rewarded_score,
                    metrics=record.metrics,
                    audio_artifact_ref=record.artifact_ref,
                    seed_audio_ref=record.genome.seed_audio_ref,
                    reference_transcript=record.effective_reference,
                    failed_transcript=record.failed_transcript,
                    reproduction={
                        "engine": record.engine_id,
                        "model": getattr(metadata, "model", None),
                        "device": getattr(metadata, "device", None),
                        "seed": record.genome.seed,
                        "chain": [s.to_dict() for s in record.genome.transform_chain],
                        "content_mutations": record.genome.content_mutations,
                        "source": record.source,
                        "minimized_chain": [s.to_dict() for s in minimized_genome.transform_chain]
                        if minimized_genome
                        else None,
                        "minimization_evaluations": minimization.evaluations_used,
                        "failure_reproduced": minimization.failure_reproduced,
                        "instructions": "Replay: load seed audio, apply minimized "
                        "chain via app.speech.transforms.apply_chain, transcribe "
                        "with the same engine/model, compare against the stored "
                        "reference transcript.",
                    },
                )
            )
            await db.commit()

    def _make_minimize_evaluator(
        self,
        run_id: int,
        metadata: Any,
        engine: Any,
        seed_audio: np.ndarray,
        seed_sr: int,
        cfg: dict[str, Any],
    ) -> Callable[[AudioGenome], Any]:
        async def evaluate(candidate: AudioGenome) -> float:
            fresh = await self._evaluate_candidate(
                run_id, candidate, engine, metadata, seed_audio, seed_sr, cfg, None
            )
            return fresh.rewarded_score if fresh.valid else 0.0

        return evaluate

    async def _finalize(
        self,
        run_id: int,
        *,
        status: str,
        error: str | None = None,
        stats_patch: dict | None = None,
    ) -> None:
        from app.models import utcnow

        async with self.session_factory() as db:
            run = await db.get(DarwinAudioRun, run_id)
            if run is None:
                return
            run.status = status
            run.error = error
            run.progress = 100 if status == "completed" else run.progress
            run.finished_at = utcnow()
            if stats_patch:
                merged = dict(run.stats or {})
                merged.update(stats_patch)
                run.stats = merged
            await db.commit()
