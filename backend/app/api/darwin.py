"""Darwin API Router — Endpoints for genetic voice & dictation fuzzing."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import evolution_engine, get_current_user, get_db
from app.core.limits import clamp_generations
from app.darwin.patcher import Patcher
from app.darwin.personas import get_active_personas
from app.darwin.regression import export_finding_to_regression
from app.models import Agent, User
from app.models.darwin import DarwinFinding, DarwinGeneration, DarwinRun
from app.schemas.darwin import (
    DarwinFindingOut,
    DarwinPersonaOut,
    DarwinRunCreate,
    DarwinRunDetail,
    DarwinRunOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/darwin", tags=["darwin"])
patcher = Patcher()


@router.get("/personas", response_model=list[DarwinPersonaOut])
async def list_personas(
    user: User = Depends(get_current_user),
):
    """List available active attack personas for fuzzing runs."""
    active = get_active_personas()
    return [
        DarwinPersonaOut(
            id=p.id,
            name=p.name,
            description=p.description,
            is_dictation_focused=p.is_dictation_focused,
            strategies=p.strategies,
        )
        for p in active
    ]


@router.post("/runs", response_model=DarwinRunOut, status_code=202)
async def create_darwin_run(
    body: DarwinRunCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start an evolutionary fuzzing run against an agent."""
    agent = await db.get(Agent, body.agent_id)
    if agent is None or agent.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")

    active_p_ids = [p.id for p in get_active_personas()]
    personas_to_use = [pid for pid in body.personas if pid in active_p_ids]
    if not personas_to_use:
        personas_to_use = active_p_ids

    # Enforce hard budget cap: pop_size * generations <= 60 (single source:
    # app.core.limits)
    effective_generations = clamp_generations(body.population_size, body.generations)

    run = DarwinRun(
        user_id=user.id,
        agent_id=agent.id,
        status="queued",
        config={
            "population_size": body.population_size,
            "generations": effective_generations,
            "requested_generations": body.generations,
            "top_k": body.top_k,
            "personas": personas_to_use,
            "seed": body.seed,
            "failure_threshold": body.failure_threshold,
            "judge_mode": body.judge_mode,
        },
        stats={
            "current_generation": 0,
            "total_generations": effective_generations,
            "sessions_executed": 0,
            "best_fitness": 0.0,
            "avg_fitness": 0.0,
            "findings_count": 0,
            "heuristic_mode": (body.judge_mode == "heuristic"),
        },
        progress=0,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Dispatch to in-process background worker
    await evolution_engine.dispatch(run.id)
    return run


@router.get("/runs", response_model=list[DarwinRunOut])
async def list_darwin_runs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all Darwin runs for the authenticated user."""
    runs = (
        await db.scalars(
            select(DarwinRun)
            .where(DarwinRun.user_id == user.id)
            .order_by(DarwinRun.id.desc())
        )
    ).all()
    return runs


@router.get("/runs/{run_id}", response_model=DarwinRunDetail)
async def get_darwin_run(
    run_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get complete run details including generation stats and findings."""
    run = await db.scalar(
        select(DarwinRun)
        .where(DarwinRun.id == run_id, DarwinRun.user_id == user.id)
        .options(
            selectinload(DarwinRun.generations_data),
            selectinload(DarwinRun.findings),
        )
    )
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Darwin run not found")
    return run


@router.post("/runs/{run_id}/cancel", response_model=DarwinRunOut)
async def cancel_darwin_run(
    run_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an active Darwin run."""
    run = await db.get(DarwinRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Darwin run not found")
    if run.status in ("completed", "failed", "cancelled"):
        return run

    cancelled = await evolution_engine.cancel(run_id)
    if cancelled:
        run.status = "cancelled"
        await db.commit()
        await db.refresh(run)
    return run


@router.get("/findings/{finding_id}", response_model=DarwinFindingOut)
async def get_finding(
    finding_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full details of a specific minimized failure finding."""
    finding = await db.get(DarwinFinding, finding_id)
    if finding is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")

    run = await db.get(DarwinRun, finding.run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Unauthorized finding access")
    return finding


@router.post("/findings/{finding_id}/export")
async def export_finding(
    finding_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export minimized finding into the regression scenario suite."""
    finding = await db.get(DarwinFinding, finding_id)
    if finding is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")

    run = await db.get(DarwinRun, finding.run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Unauthorized finding export")

    file_path, scenario_id = await export_finding_to_regression(finding, db)
    return {
        "status": "exported",
        "file_name": file_path.name,
        "file_path": str(file_path),
        "scenario_id": scenario_id,
        "message": f"Successfully exported to regression suite as {file_path.name}",
    }



@router.post("/findings/{finding_id}/verify-patch")
async def verify_finding_patch(
    finding_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sandbox verification of root cause patch proposal against minimized failure."""
    finding = await db.get(DarwinFinding, finding_id)
    if finding is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")

    run = await db.get(DarwinRun, finding.run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Unauthorized finding patch verification")

    agent = await db.get(Agent, run.agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")

    result = await patcher.verify_patch(finding, agent, db)
    return result
