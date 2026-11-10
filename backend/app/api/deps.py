"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.darwin.evolution import EvolutionEngine
from app.engine.orchestrator import Orchestrator
from app.models import Agent, User
from app.models.security_models import RevokedToken

bearer = HTTPBearer(auto_error=False)

# Single in-process orchestrator instance (swap for queue dispatch via workers).
orchestrator = Orchestrator(SessionLocal)
evolution_engine = EvolutionEngine(SessionLocal)


async def get_db() -> AsyncSession:
    async with SessionLocal() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    from app.core.security import decode_access_token_full

    payload = decode_access_token_full(credentials.credentials)
    if payload is None or payload.get("sub") is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    # Revocation check: a logged-out (or otherwise revoked) jti is rejected
    # even while the JWT itself is still unexpired.
    jti = payload.get("jti")
    if jti is not None:
        revoked = await db.scalar(
            select(RevokedToken.jti).where(RevokedToken.jti == str(jti))
        )
        if revoked is not None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token revoked")
    user = await db.scalar(select(User).where(User.id == int(payload["sub"])))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


async def get_owned_agent(
    agent_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return agent
