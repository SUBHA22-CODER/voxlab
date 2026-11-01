"""Shared fixtures: in-memory async SQLite, ASGI test client, fake agent."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.api.deps import get_db
from app.main import create_app
from app.models import Agent, Scenario, User
from app.core.security import hash_password


@pytest.fixture(autouse=True)
def _relax_rate_limit():
    """Tests share one client IP; disable the auth rate limit per test."""
    from app.core import rate_limit

    original = rate_limit.MAX_REQUESTS
    rate_limit.MAX_REQUESTS = 1_000_000
    rate_limit._hits.clear()
    yield
    rate_limit.MAX_REQUESTS = original
    rate_limit._hits.clear()


@pytest_asyncio.fixture
async def db_engine(tmp_path):
    # File-backed SQLite (not :memory:) so each session gets its own
    # connection and transactions are properly isolated — a shared
    # StaticPool connection lets concurrent sessions clobber each other.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def app(db_engine):
    """The FastAPI app with the test database injected via get_db override."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    application = create_app()

    async def override_get_db():
        async with factory() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db
    application.state._test_db_factory = factory
    return application


@pytest_asyncio.fixture
async def client(app):
    """HTTP client bound to the app with the test database injected."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def user(db_session) -> User:
    row = User(email="dev@example.com", password_hash=hash_password("password123"))
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


@pytest_asyncio.fixture
async def auth_headers(client, user) -> dict:
    response = await client.post(
        "/api/auth/login",
        json={"email": "dev@example.com", "password": "password123"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def agent(db_session, user) -> Agent:
    row = Agent(
        user_id=user.id,
        name="Test Agent",
        endpoint="http://localhost:9999/conversation",
        agent_type="http",
        config={"timeout_s": 10},
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


@pytest_asyncio.fixture
async def scenario(db_session) -> Scenario:
    row = Scenario(
        name="Echo Scenario",
        category="conversation",
        is_builtin=True,
        definition={
            "name": "Echo Scenario",
            "category": "conversation",
            "steps": [{"type": "user_message", "content": "hello"}],
            "expected_behavior": "replies politely",
            "latency_budget_ms": 5000,
            "checks": [{"type": "reply_nonempty", "turn": -1}],
        },
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row
