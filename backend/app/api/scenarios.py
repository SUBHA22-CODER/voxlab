from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import Scenario, User
from app.schemas import ScenarioCreate, ScenarioOut

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


@router.get("", response_model=list[ScenarioOut])
async def list_scenarios(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    rows = await db.scalars(
        select(Scenario)
        .where(or_(Scenario.is_builtin.is_(True), Scenario.user_id == user.id))
        .order_by(Scenario.category, Scenario.name)
    )
    return list(rows)


@router.post("", response_model=ScenarioOut, status_code=201)
async def create_scenario(
    body: ScenarioCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    definition = body.definition
    if not isinstance(definition.get("steps"), list):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "definition.steps must be a list")
    scenario = Scenario(
        user_id=user.id,
        name=body.name,
        category=body.category,
        definition=definition,
        is_builtin=False,
    )
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)
    return scenario


@router.get("/{scenario_id}", response_model=ScenarioOut)
async def get_scenario(
    scenario_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scenario = await db.get(Scenario, scenario_id)
    if scenario is None or not (scenario.is_builtin or scenario.user_id == user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scenario not found")
    return scenario


@router.delete("/{scenario_id}", status_code=204)
async def delete_scenario(
    scenario_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scenario = await db.get(Scenario, scenario_id)
    if scenario is None or scenario.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scenario not found")
    await db.delete(scenario)
    await db.commit()
