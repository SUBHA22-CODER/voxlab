"""Test-run orchestration: drives scenarios → traces → evaluation → report."""

from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.base import build_adapter
from app.core.config import get_settings
from app.core.security import decrypt_credentials
from app.engine.evaluation_engine import EvaluationEngine
from app.engine.reports import generate_report_summary
from app.engine.scenario_runner import ScenarioRunner
from app.engine.trace_collector import (
    EVENT_SESSION_ENDED,
    EVENT_SESSION_STARTED,
    TraceCollector,
)
from app.models import (
    Agent,
    Evaluation,
    Report,
    Scenario,
    Session,
    TestRun,
    utcnow,
)
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


class Orchestrator:
    """In-process background executor for benchmark runs.

    Swap point for ARQ/Celery: `dispatch` enqueues to Redis instead when a
    worker deployment is configured (see app/workers/runner.py).
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory
        self._tasks: dict[int, asyncio.Task] = {}

    async def dispatch(self, run_id: int) -> None:
        self._tasks[run_id] = asyncio.create_task(self.execute_run(run_id))

    async def cancel(self, run_id: int) -> bool:
        task = self._tasks.get(run_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    async def execute_run(self, run_id: int) -> None:
        settings = get_settings()
        try:
            await self._execute(run_id, settings)
        except asyncio.CancelledError:
            await self._mark_run(run_id, status="cancelled")
            logger.info("Run %s cancelled", run_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Run %s failed", run_id)
            await self._mark_run(run_id, status="failed", error=str(exc)[:2000])

    async def _execute(self, run_id: int, settings) -> None:
        async with self.session_factory() as db:
            run = await db.get(TestRun, run_id)
            if run is None:
                return
            run.status = "running"
            await db.commit()

            agent = await db.get(Agent, run.agent_id)
            scenario_ids = run.config.get("scenario_ids", [])
            scenarios = (
                await db.scalars(select(Scenario).where(Scenario.id.in_(scenario_ids)))
            ).all()
            scenarios.sort(key=lambda s: scenario_ids.index(s.id))

            llm = LLMService()
            engine = EvaluationEngine(llm, settings.default_latency_budget_ms)

            for scenario in scenarios:
                session_row = Session(
                    test_run_id=run.id,
                    agent_id=agent.id,
                    scenario_id=scenario.id,
                    trace_id=uuid.uuid4().hex,
                    source="test_run",
                )
                db.add(session_row)
                await db.flush()

                try:
                    scores, feedback = await self._run_session(
                        agent, scenario, session_row, engine, db
                    )
                except asyncio.CancelledError:
                    session_row.status = "cancelled"
                    session_row.finished_at = utcnow()
                    await db.commit()
                    raise
                except Exception as exc:  # noqa: BLE001 — isolate session failures
                    logger.exception("Session failed for scenario %s", scenario.name)
                    session_row.status = "failed"
                    session_row.finished_at = utcnow()
                    scores, feedback = {"_error": str(exc)[:500]}, {}

                db.add(
                    Evaluation(
                        session_id=session_row.id,
                        scores=scores,
                        feedback=feedback,
                    )
                )
                run.progress += 1
                await db.commit()

            await self._finalize_run(db, run)

    async def _run_session(
        self,
        agent: Agent,
        scenario: Scenario,
        session_row: Session,
        engine: EvaluationEngine,
        db: AsyncSession,
    ):
        collector = TraceCollector(session_row.id, session_row.trace_id)
        collector.record(
            EVENT_SESSION_STARTED,
            {"scenario": scenario.name, "category": scenario.category},
        )

        adapter = build_adapter(
            {
                "endpoint": agent.endpoint,
                "agent_type": agent.agent_type,
                "session_id": f"vx-s{session_row.id}-{uuid.uuid4().hex[:8]}",
                "timeout_s": (agent.config or {}).get("timeout_s", 30),
            },
            decrypt_credentials(agent.auth_config_encrypted),
        )
        try:
            await adapter.connect()
            runner = ScenarioRunner(adapter, scenario.definition, collector)
            output = await runner.run()
        finally:
            try:
                await adapter.disconnect()
            except Exception:  # noqa: BLE001
                pass

        status = "failed" if output.agent_error and not output.transcript else "completed"
        scores, feedback = await engine.evaluate(scenario.definition, output)
        collector.record(
            EVENT_SESSION_ENDED,
            {"status": status, "turns": len(output.turn_latencies_ms)},
        )
        await collector.flush(db)

        session_row.status = status
        session_row.finished_at = utcnow()
        return scores, feedback

    async def _finalize_run(self, db: AsyncSession, run: TestRun) -> None:
        rows = (
            await db.execute(
                select(
                    Session.id,
                    Session.status,
                    Scenario.name,
                    Scenario.category,
                    Evaluation.scores,
                    Evaluation.feedback,
                )
                .join(Scenario, Session.scenario_id == Scenario.id, isouter=True)
                .join(Evaluation, Evaluation.session_id == Session.id, isouter=True)
                .where(Session.test_run_id == run.id)
            )
        ).all()

        sessions = [
            {
                "session_id": r.id,
                "status": r.status,
                "scenario_name": r.name or "Unknown",
                "category": r.category or "unknown",
                "scores": r.scores or {},
                "feedback": r.feedback or {},
            }
            for r in rows
        ]
        summary = generate_report_summary(run.config, sessions)

        existing = await db.scalars(select(Report).where(Report.test_run_id == run.id))
        report = existing.first()
        if report is None:
            report = Report(test_run_id=run.id)
            db.add(report)
        report.score = summary["score"]
        report.summary = summary

        run.status = "completed"
        run.finished_at = utcnow()
        await db.commit()

    async def _mark_run(
        self, run_id: int, status: str, error: str | None = None
    ) -> None:
        async with self.session_factory() as db:
            run = await db.get(TestRun, run_id)
            if run and run.status not in ("completed", "failed", "cancelled"):
                run.status = status
                run.error = error
                run.finished_at = utcnow()
                await db.commit()
