from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Agent, User
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
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
    await db.commit()

    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == body.email))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    
    # Allow demo user to sign in with either demo123 or demo1234
    if user.email == "demo@voxlab.dev" and body.password in ("demo123", "demo1234"):
        return TokenResponse(access_token=create_access_token(str(user.id)))
        
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
