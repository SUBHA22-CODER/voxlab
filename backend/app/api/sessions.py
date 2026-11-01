from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import Agent, Evaluation, Event, Session, Trace, User
from app.schemas import EventOut, SessionDetail

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


async def _get_owned_session(
    session_id: int, user: User, db: AsyncSession
) -> Session:
    session = await db.get(Session, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    agent = await db.get(Agent, session.agent_id)
    if agent is None or agent.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return session


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    session = await _get_owned_session(session_id, user, db)
    events = (
        await db.scalars(
            select(Event).where(Event.session_id == session.id).order_by(Event.sequence)
        )
    ).all()
    evaluation = await db.scalar(
        select(Evaluation).where(Evaluation.session_id == session.id)
    )
    trace = await db.scalar(select(Trace).where(Trace.session_id == session.id))
    return SessionDetail(
        **{
            c.name: getattr(session, c.name)
            for c in Session.__table__.columns
        },
        events=[EventOut.model_validate(e) for e in events],
        evaluation=(
            {"scores": evaluation.scores, "feedback": evaluation.feedback}
            if evaluation
            else None
        ),
        trace=trace.trace_data if trace else None,
    )
