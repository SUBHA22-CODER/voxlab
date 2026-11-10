"""Darwin Evolution Engine — Genetic algorithm loop, budget control, and failure discovery."""

from __future__ import annotations

import asyncio
import copy
import logging
import random
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.base import build_adapter
from app.core.config import get_settings
from app.core.limits import max_darwin_sessions
from app.core.security import decrypt_credentials
from app.darwin.attacker import Attacker
from app.darwin.diagnoser import Diagnoser
from app.darwin.fitness import FitnessResult, compute_fitness
from app.darwin.genome import (
    Genome,
    crossover,
    create_random_genome,
    mutate,
)
from app.darwin.minimizer import ddmin
from app.darwin.personas import get_active_personas
from app.engine.evaluation_engine import EvaluationEngine
from app.engine.scenario_runner import RunOutput, ScenarioRunner
from app.engine.trace_collector import (
    EVENT_SESSION_ENDED,
    EVENT_SESSION_STARTED,
    TraceCollector,
)
from app.models import Agent, Session, utcnow
from app.models.darwin import DarwinFinding, DarwinGeneration, DarwinRun
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


class EvolutionEngine:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        llm: LLMService | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.llm = llm if llm is not None else LLMService()
        self.diagnoser = Diagnoser(self.llm)
        self.attacker = Attacker(self.llm)
        self._tasks: dict[int, asyncio.Task] = {}

    async def dispatch(self, darwin_run_id: int) -> None:
        self._tasks[darwin_run_id] = asyncio.create_task(self.execute_evolution(darwin_run_id))

    async def cancel(self, darwin_run_id: int) -> bool:
        task = self._tasks.get(darwin_run_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    async def execute_evolution(self, darwin_run_id: int) -> None:
        try:
            await self._run_evolution_loop(darwin_run_id)
        except asyncio.CancelledError:
            await self._mark_status(darwin_run_id, status="cancelled")
            logger.info("Darwin run %s cancelled by user", darwin_run_id)
        except Exception as exc:
            logger.exception("Darwin run %s failed: %s", darwin_run_id, exc)
            await self._mark_status(darwin_run_id, status="failed", error=str(exc)[:2000])

    async def _mark_status(self, run_id: int, status: str, error: str | None = None) -> None:
        async with self.session_factory() as db:
            run = await db.get(DarwinRun, run_id)
            if run:
                run.status = status
                run.error = error
                run.finished_at = utcnow()
                await db.commit()

    async def _run_evolution_loop(self, darwin_run_id: int) -> None:
        settings = get_settings()
        max_budget = max_darwin_sessions()

        async with self.session_factory() as db:
            run = await db.get(DarwinRun, darwin_run_id)
            if run is None:
                return
            run.status = "running"
            await db.commit()

            cfg = run.config or {}
            agent = await db.get(Agent, run.agent_id)
            if not agent:
                run.status = "failed"
                run.error = "Agent not found"
                await db.commit()
                return

            pop_size = int(cfg.get("population_size", 6))
            num_generations = int(cfg.get("generations", 5))
            top_k = int(cfg.get("top_k", 2))
            seed = int(cfg.get("seed", 42))
            failure_threshold = float(cfg.get("failure_threshold", 0.5))
            selected_personas = cfg.get("personas") or [p.id for p in get_active_personas()]

            # Hard budget verification: pop_size * generations <= budget
            total_planned = pop_size * num_generations
            if total_planned > max_budget:
                num_generations = max(1, max_budget // pop_size)
                run_cfg = dict(run.config or {})
                run_cfg["generations"] = num_generations
                run.config = run_cfg
                run_st = dict(run.stats or {})
                run_st["total_generations"] = num_generations
                run.stats = run_st
                await db.commit()
                logger.info(
                    "Darwin run %s clamped generations to %d due to budget cap (%d)",
                    darwin_run_id, num_generations, max_budget
                )

        rng = random.Random(seed)
        judge_mode = cfg.get("judge_mode", "auto")
        is_heuristic_run = (judge_mode == "heuristic") or not self.llm.available
        effective_llm = self.llm if not is_heuristic_run else LLMService(api_key="")
        eval_engine = EvaluationEngine(effective_llm, settings.default_latency_budget_ms)
        effective_attacker = self.attacker if not is_heuristic_run else Attacker(llm=effective_llm)
        effective_diagnoser = self.diagnoser if not is_heuristic_run else Diagnoser(llm=effective_llm)

        # 1. Generation 0 initialization
        population: list[Genome] = []
        for i in range(pop_size):
            p_id = selected_personas[i % len(selected_personas)]
            g = create_random_genome(p_id, seed=seed + i, generation=0, rng=rng)
            population.append(g)

        sessions_executed = 0
        discovered_hashes: set[str] = set()
        total_expected = min(max_budget, num_generations * pop_size)

        for gen_idx in range(num_generations):
            if sessions_executed >= max_budget:
                logger.info("Reached Darwin budget cap of %d sessions. Stopping.", max_budget)
                break

            gen_results: list[tuple[Genome, FitnessResult, RunOutput, Session, list[dict[str, Any]]]] = []

            for g in population:
                if sessions_executed >= max_budget:
                    break
                sessions_executed += 1
                try:
                    res = await self._evaluate_candidate(
                        agent, g, eval_engine, darwin_run_id, attacker=effective_attacker
                    )
                    if res is not None:
                        gen_results.append(res)
                        # Mid-run crash detection: if agent is unreachable/killed, cleanly stop
                        if res[2].agent_error and "connection_error" in res[2].agent_error.lower():
                            logger.error("Agent became unreachable mid-run: %s", res[2].agent_error)
                            async with self.session_factory() as db:
                                r_obj = await db.get(DarwinRun, darwin_run_id)
                                if r_obj:
                                    r_obj.status = "partial" if (gen_idx > 0 or len(gen_results) > 1) else "failed"
                                    r_obj.error = f"Agent endpoint unreachable: {res[2].agent_error}"
                                    r_obj.finished_at = utcnow()
                                    curr_st = dict(r_obj.stats or {})
                                    curr_st["sessions_executed"] = sessions_executed
                                    curr_st["heuristic_mode"] = is_heuristic_run
                                    r_obj.stats = curr_st
                                    await db.commit()
                            return
                except Exception as eval_err:
                    logger.warning("Error evaluating candidate genome %s: %s", g.id, eval_err)

                # Incremental progress update so user sees live counter on every session
                try:
                    async with self.session_factory() as db:
                        r_obj = await db.get(DarwinRun, darwin_run_id)
                        if r_obj:
                            current_stats = dict(r_obj.stats or {})
                            current_stats["sessions_executed"] = sessions_executed
                            current_stats["current_generation"] = gen_idx
                            current_stats["heuristic_mode"] = is_heuristic_run
                            if gen_results:
                                current_stats["best_fitness"] = round(
                                    max(item[1].fitness for item in gen_results), 4
                                )
                            r_obj.stats = current_stats
                            r_obj.progress = int((sessions_executed / max(1, total_expected)) * 100)
                            await db.commit()
                except Exception as update_err:
                    logger.debug("Failed incremental progress update: %s", update_err)

            if not gen_results:
                break

            # Sort by fitness descending (highest fitness = worst agent performance = best attack)
            gen_results.sort(key=lambda item: item[1].fitness, reverse=True)

            best_fitness = gen_results[0][1].fitness
            avg_fitness = sum(item[1].fitness for item in gen_results) / len(gen_results)

            # Persist Generation record & findings
            async with self.session_factory() as db:
                gen_record = DarwinGeneration(
                    run_id=darwin_run_id,
                    generation_index=gen_idx,
                    best_fitness=round(best_fitness, 4),
                    avg_fitness=round(avg_fitness, 4),
                    stats={
                        "population_size": len(gen_results),
                        "sessions_executed": sessions_executed,
                        "best_overall_score": gen_results[0][1].overall_score,
                    },
                )
                db.add(gen_record)

                # Process failures / findings
                for candidate_genome, fit_res, run_out, sess_row, events in gen_results:
                    if fit_res.fitness >= failure_threshold:
                        ghash = candidate_genome.id
                        if ghash not in discovered_hashes:
                            discovered_hashes.add(ghash)

                            # Run ddmin failure minimizer
                            minimized_steps = await self._minimize_failure(
                                agent, candidate_genome, eval_engine, darwin_run_id, failure_threshold
                            )

                            # Diagnose failure
                            diag = await effective_diagnoser.diagnose(
                                scenario=candidate_genome.compile_to_scenario(),
                                events=events,
                                failed_checks=fit_res.failed_checks,
                                transcript=run_out.transcript,
                            )

                            finding = DarwinFinding(
                                run_id=darwin_run_id,
                                persona=candidate_genome.persona,
                                strategy=candidate_genome.strategy,
                                genome=candidate_genome.to_dict(),
                                minimized_steps=minimized_steps,
                                original_steps_count=len(candidate_genome.steps),
                                minimized_steps_count=len(minimized_steps),
                                fitness=fit_res.fitness,
                                diagnosis=diag.model_dump(),
                                trace_id=sess_row.trace_id,
                                session_id=sess_row.id,
                            )
                            db.add(finding)

                # Update run progress & stats for this completed generation
                r_obj = await db.get(DarwinRun, darwin_run_id)
                if r_obj:
                    r_obj.progress = int(((gen_idx + 1) / num_generations) * 100)
                    r_obj.stats = {
                        "current_generation": gen_idx + 1,
                        "total_generations": num_generations,
                        "sessions_executed": sessions_executed,
                        "best_fitness": round(best_fitness, 4),
                        "avg_fitness": round(avg_fitness, 4),
                        "findings_count": len(discovered_hashes),
                    }
                await db.commit()

            # Evolution breeding for next generation
            survivors = [item[0] for item in gen_results[:top_k]]
            next_population: list[Genome] = copy.deepcopy(survivors)

            while len(next_population) < pop_size:
                if rng.random() < 0.5 and len(survivors) >= 2:
                    p1, p2 = rng.sample(survivors, 2)
                    child = crossover(p1, p2, rng=rng)
                else:
                    parent = rng.choice(survivors)
                    child = mutate(parent, rng=rng)
                next_population.append(child)

            population = next_population

        # Finalize run
        async with self.session_factory() as db:
            final_run = await db.get(DarwinRun, darwin_run_id)
            if final_run:
                final_run.status = "completed"
                final_run.finished_at = utcnow()
                final_run.progress = 100
                st = dict(final_run.stats or {})
                st["heuristic_mode"] = is_heuristic_run
                final_run.stats = st
                await db.commit()

    async def _evaluate_candidate(
        self,
        agent: Agent,
        genome: Genome,
        engine: EvaluationEngine,
        darwin_run_id: int,
        attacker: Attacker | None = None,
    ) -> tuple[Genome, FitnessResult, RunOutput, Session, list[dict[str, Any]]]:
        # Adaptive utterance materialization (in-memory, no open DB transaction)
        act = attacker or self.attacker
        materialized = await act.materialize_genome(copy.deepcopy(genome))
        scenario_def = materialized.compile_to_scenario()

        trace_id = uuid.uuid4().hex
        runner_session_id = f"darwin-{uuid.uuid4().hex[:12]}"
        collector = TraceCollector(0, trace_id)
        collector.record(
            EVENT_SESSION_STARTED,
            {"persona": genome.persona, "strategy": genome.strategy},
        )

        adapter = build_adapter(
            {
                "endpoint": agent.endpoint,
                "agent_type": agent.agent_type,
                "session_id": runner_session_id,
                "timeout_s": (agent.config or {}).get("timeout_s", 15),
            },
            decrypt_credentials(agent.auth_config_encrypted),
        )

        runner = ScenarioRunner(adapter, scenario_def, collector)
        try:
            run_output = await runner.run()
            status_val = "completed"
        except Exception as exc:
            run_output = RunOutput(agent_error=str(exc))
            status_val = "failed"

        collector.record(
            EVENT_SESSION_ENDED,
            {"turns": len(run_output.transcript) // 2},
        )

        # Evaluate scenario (in-memory)
        scores, feedback = await engine.evaluate(scenario_def, run_output)
        checks = feedback.get("checks", [])
        fit_res = compute_fitness(scores, checks, run_output, persona_id=genome.persona)

        # Short, isolated DB commit (<5ms)
        async with self.session_factory() as db:
            sess_row = Session(
                agent_id=agent.id,
                trace_id=trace_id,
                source="darwin_fuzz",
                status=status_val,
                finished_at=utcnow(),
            )
            db.add(sess_row)
            await db.flush()
            collector.session_id = sess_row.id
            await collector.flush(db)
            await db.commit()
            return materialized, fit_res, run_output, sess_row, collector._events


    async def _minimize_failure(
        self,
        agent: Agent,
        genome: Genome,
        engine: EvaluationEngine,
        darwin_run_id: int,
        failure_threshold: float,
    ) -> list[dict[str, Any]]:
        """Uses ddmin to shrink steps while maintaining failure condition."""
        async def predicate(test_steps: list[dict[str, Any]]) -> bool:
            test_genome = copy.deepcopy(genome)
            test_genome.steps = test_steps
            scen = test_genome.compile_to_scenario()

            collector = TraceCollector(0, "ddmin_trace")
            adapter = build_adapter(
                {
                    "endpoint": agent.endpoint,
                    "agent_type": agent.agent_type,
                    "session_id": f"ddmin-{uuid.uuid4().hex[:8]}",
                    "timeout_s": (agent.config or {}).get("timeout_s", 30),
                },
                decrypt_credentials(agent.auth_config_encrypted),
            )
            runner = ScenarioRunner(adapter, scen, collector)
            try:
                out = await runner.run()
                scores, fb = await engine.evaluate(scen, out)
                res = compute_fitness(scores, fb.get("checks", []), out, persona_id=genome.persona)
                return res.fitness >= failure_threshold
            except Exception:
                return False

        minimized = await ddmin(genome.steps, predicate, max_evaluations=12)
        return minimized
