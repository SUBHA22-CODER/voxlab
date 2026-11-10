import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import build_adapter
from app.api.deps import get_current_user, get_db, get_owned_agent
from app.core.security import decrypt_credentials, encrypt_credentials
from app.models import Agent, User, utcnow
from app.schemas import (
    AgentCreate,
    AgentOut,
    AgentUpdate,
    ConnectionTestResult,
)
from app.services.endpoint_guard import EndpointValidationError, validate_endpoint

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=list[AgentOut])
async def list_agents(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    rows = await db.scalars(
        select(Agent).where(Agent.user_id == user.id).order_by(Agent.id.desc())
    )
    return list(rows)


@router.post("", response_model=AgentOut, status_code=201)
async def register_agent(
    body: AgentCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    try:
        endpoint = validate_endpoint(body.endpoint)
    except EndpointValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    agent = Agent(
        user_id=user.id,
        name=body.name,
        description=body.description,
        endpoint=endpoint,
        agent_type=body.agent_type,
        auth_config_encrypted=encrypt_credentials(body.auth_config),
        stt_provider=body.stt_provider,
        llm_provider=body.llm_provider,
        tts_provider=body.tts_provider,
        config=body.config,
        connection_status="untested",
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent: Agent = Depends(get_owned_agent)):
    return agent


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(
    body: AgentUpdate,
    agent: Agent = Depends(get_owned_agent),
    db: AsyncSession = Depends(get_db),
):
    data = body.model_dump(exclude_unset=True)
    if data.get("endpoint"):
        try:
            data["endpoint"] = validate_endpoint(data["endpoint"])
        except EndpointValidationError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    if "auth_config" in data:
        agent.auth_config_encrypted = encrypt_credentials(data.pop("auth_config"))
    for field, value in data.items():
        setattr(agent, field, value)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent: Agent = Depends(get_owned_agent), db: AsyncSession = Depends(get_db)
):
    await db.delete(agent)
    await db.commit()


@router.post("/{agent_id}/connect", response_model=ConnectionTestResult)
async def test_connection(
    agent: Agent = Depends(get_owned_agent), db: AsyncSession = Depends(get_db)
):
    """Verify the agent endpoint is reachable through its adapter."""
    started = time.perf_counter()
    detail = ""
    ok = False
    adapter = build_adapter(
        {
            "endpoint": agent.endpoint,
            "agent_type": agent.agent_type,
            "session_id": f"vx-probe-{int(time.time())}",
            "timeout_s": (agent.config or {}).get("timeout_s", 30),
        },
        decrypt_credentials(agent.auth_config_encrypted),
    )
    try:
        if agent.config.get("health_path"):
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(agent.endpoint.rstrip("/") + agent.config["health_path"])
                response.raise_for_status()
            ok = True
            detail = "health check passed"
        else:
            # Contract-defined ping: agents answer pings without altering state.
            await adapter.connect()
            result = await adapter.send_message("", {"signal": "ping"})
            ok = result.error is None
            detail = result.reply[:200] if ok else f"agent error: {result.error}"
    except Exception as exc:
        detail = f"connection failed: {exc.__class__.__name__}: {exc}"[:300]
    finally:
        try:
            await adapter.disconnect()
        except Exception:
            pass

    latency_ms = int((time.perf_counter() - started) * 1000)
    agent.connection_status = "connected" if ok else "unreachable"
    agent.config = {**(agent.config or {}), "last_checked_at": utcnow().isoformat()}
    await db.commit()

    return ConnectionTestResult(ok=ok, status=agent.connection_status, detail=detail, latency_ms=latency_ms)
