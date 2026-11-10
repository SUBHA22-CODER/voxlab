from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.security import (
    create_access_token,
    decode_access_token_full,
    hash_password,
    verify_password,
)
from app.models import Agent, User
from app.models.security_models import RevokedToken
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services.audit import record_event

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    await db.flush()

    # Automatically provision starter agents so the account is immediately functional
    agent1 = Agent(
        user_id=user.id,
        name="Customer Support Agent (Demo)",
        description="Support desk agent for tracking, modifying, and troubleshooting orders.",
        endpoint="http://localhost:8100/conversation",
        agent_type="http",
        config={"timeout_s": 15},
    )
    agent2 = Agent(
        user_id=user.id,
        name="Wispr Flow Dictation Agent (Demo)",
        description="Voice dictation and natural speech cleaning pipeline for Wispr Flow.",
        endpoint="http://localhost:8200/conversation",
        agent_type="http",
        config={"timeout_s": 15},
    )
    db.add_all([agent1, agent2])
    token, _jti = create_access_token(str(user.id))
    await record_event(
        db,
        event_type="register",
        user_id=user.id,
        source_ip=_client_ip(request),
        detail={"email_domain": body.email.split("@")[-1][:64]},
    )
    await db.commit()

    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        # Audit the failure without leaking which part was wrong; never log
        # the attempted password. The legacy demo-credential bypass
        # (demo123 | demo1234) was removed in 2.5: every account, including
        # the demo account, authenticates against its stored PBKDF2 hash.
        await record_event(
            db,
            event_type="login_failure",
            user_id=user.id if user else None,
            source_ip=_client_ip(request),
            detail={"email_provided": bool(body.email)},
            commit=True,
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    token, _jti = create_access_token(str(user.id))
    await record_event(
        db,
        event_type="login_success",
        user_id=user.id,
        source_ip=_client_ip(request),
    )
    await db.commit()
    return TokenResponse(access_token=token)


@router.post("/logout", status_code=200)
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke the presented token until its natural expiry."""
    auth_header = request.headers.get("authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    payload = decode_access_token_full(token)
    if payload and payload.get("jti") and payload.get("exp"):
        from datetime import UTC, datetime

        db.add(
            RevokedToken(
                jti=str(payload["jti"]),
                user_id=user.id,
                expires_at=datetime.fromtimestamp(float(payload["exp"]), tz=UTC),
            )
        )
        await record_event(
            db, event_type="logout", user_id=user.id, source_ip=_client_ip(request)
        )
        await db.commit()
    return {"status": "logged_out"}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
