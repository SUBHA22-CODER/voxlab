from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, orchestrator
from app.models import Agent, Evaluation, Report, Scenario, Session, TestRun, User
from app.schemas import (
    ReportOut,
    SessionSummary,
    TestRunCreate,
    TestRunDetail,
    TestRunOut,
)
from app.workers.runner import dispatch_to_queue

router = APIRouter(prefix="/api/test-runs", tags=["test-runs"])


@router.post("", response_model=TestRunOut, status_code=202)
async def start_test_run(
    body: TestRunCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agent = await db.get(Agent, body.agent_id)
    if agent is None or agent.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    if not body.scenario_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Select at least one scenario")

    scenarios = (
        await db.scalars(select(Scenario).where(Scenario.id.in_(body.scenario_ids)))
    ).all()
    if len(scenarios) != len(set(body.scenario_ids)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "One or more scenarios not found")

    run = TestRun(
        user_id=user.id,
        agent_id=agent.id,
        status="queued",
        config={
            "scenario_ids": body.scenario_ids,
            "weights": body.weights or {},
            "latency_budget_ms": body.latency_budget_ms,
        },
        total_sessions=len(body.scenario_ids),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    if not await dispatch_to_queue(run.id):
        await orchestrator.dispatch(run.id)
    return run


@router.get("", response_model=list[TestRunOut])
async def list_test_runs(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    rows = await db.scalars(
        select(TestRun).where(TestRun.user_id == user.id).order_by(TestRun.id.desc())
    )
    return list(rows)


async def _load_run_detail(run: TestRun, db: AsyncSession) -> TestRunDetail:
    session_rows = (
        await db.scalars(
            select(Session).where(Session.test_run_id == run.id).order_by(Session.id)
        )
    ).all()
    scenario_ids = [s.scenario_id for s in session_rows if s.scenario_id]
    scenario_names = {}
    if scenario_ids:
        scenario_rows = (
            await db.scalars(select(Scenario).where(Scenario.id.in_(scenario_ids)))
        ).all()
        scenario_names = {s.id: s.name for s in scenario_rows}

    evals = (
        await db.scalars(
            select(Evaluation).where(
                Evaluation.session_id.in_([s.id for s in session_rows] or [0])
            )
        )
    ).all() if session_rows else []
    eval_by_session = {e.session_id: e for e in evals}

    sessions = []
    for s in session_rows:
        evaluation = None
        if s.id in eval_by_session:
            evaluation = {
                "scores": eval_by_session[s.id].scores,
                "feedback": eval_by_session[s.id].feedback,
            }
        sessions.append(
            SessionSummary(
                id=s.id,
                scenario_id=s.scenario_id,
                scenario_name=scenario_names.get(s.scenario_id),
                status=s.status,
                started_at=s.started_at,
                finished_at=s.finished_at,
                evaluation=evaluation,
            )
        )

    report_row = await db.scalar(select(Report).where(Report.test_run_id == run.id))
    detail = TestRunDetail(
        id=run.id,
        agent_id=run.agent_id,
        status=run.status,
        progress=run.progress,
        total_sessions=run.total_sessions,
        config=run.config,
        error=run.error,
        started_at=run.started_at,
        finished_at=run.finished_at,
        sessions=sessions,
        report=report_row.summary if report_row else None,
    )
    return detail


@router.get("/{run_id}", response_model=TestRunDetail)
async def get_test_run(
    run_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    run = await db.get(TestRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test run not found")
    return await _load_run_detail(run, db)


@router.post("/{run_id}/cancel", response_model=TestRunOut)
async def cancel_test_run(
    run_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    run = await db.get(TestRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test run not found")
    if run.status in ("completed", "failed", "cancelled"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Run already {run.status}")
    await orchestrator.cancel(run.id)
    await db.refresh(run)
    return run


@router.get("/{run_id}/report", response_model=ReportOut)
async def get_run_report(
    run_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    run = await db.get(TestRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test run not found")
    report = await db.scalar(select(Report).where(Report.test_run_id == run.id))
    if report is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Report not generated yet (run status: %s)" % run.status,
        )
    return report
