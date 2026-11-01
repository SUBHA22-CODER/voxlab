from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import Agent, Session, Trace, User
from app.schemas import TraceOut

router = APIRouter(prefix="/api", tags=["traces"])


@router.get("/sessions/{session_id}/traces", response_model=TraceOut)
async def get_session_traces(
    session_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    session = await db.get(Session, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    agent = await db.get(Agent, session.agent_id)
    if agent is None or agent.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    trace = await db.scalar(select(Trace).where(Trace.session_id == session.id))
    if trace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trace not collected yet")
    return trace
