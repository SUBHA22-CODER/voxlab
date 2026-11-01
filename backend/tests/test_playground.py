"""Tests for the live playground WebSocket and the agent connection check."""

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.testclient import TestClient

from app.core.database import Base
from tests.scripted_agent import ScriptedAgentAdapter

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def ws_db(tmp_path):
    """Dedicated engine for WS tests.

    TestClient serves the app on its own portal/event loop, so the shared
    test engine's pooled connections would be reused across loops. NullPool
    creates a fresh connection per checkout, which is loop-safe.
    """
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'ws.db'}", poolclass=NullPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def mirror_agent(ws_db, agent):
    """The playground reads the agent from its own DB; replicate the fixture row."""
    from app.models import Agent as AgentRow

    async with ws_db() as db:
        db.add(
            AgentRow(
                id=agent.id,
                user_id=agent.user_id,
                name=agent.name,
                endpoint=agent.endpoint,
                agent_type="http",
            )
        )
        await db.commit()


def setup_playground(monkeypatch, app, factory, fake_adapter):
    # Keep TestClient's lifespan off the real database.
    async def _noop(*args, **kwargs):
        return 0

    monkeypatch.setattr("app.main.init_db", _noop)
    monkeypatch.setattr("app.main.load_builtin_scenarios", _noop)
    monkeypatch.setattr("app.api.playground.build_adapter", lambda cfg, auth: fake_adapter)
    monkeypatch.setattr("app.api.playground.SessionLocal", factory)


class TestPlaygroundWebSocket:
    async def test_rejects_bad_token(self, app, agent, monkeypatch, ws_db):
        async def _noop(*args, **kwargs):
            return 0

        monkeypatch.setattr("app.main.init_db", _noop)
        monkeypatch.setattr("app.main.load_builtin_scenarios", _noop)
        with TestClient(app) as tc:
            with pytest.raises(Exception):
                with tc.websocket_connect(f"/ws/playground/{agent.id}?token=bad"):
                    tc.receive_json()  # pragma: no cover


class TestAgentConnectionCheck:
    async def test_health_path_connection_test(
        self, client, auth_headers, agent, db_session, monkeypatch
    ):
        agent.config = {"health_path": "/health", "timeout_s": 5}
        db_session.add(agent)
        await db_session.commit()

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path.endswith("/health")
            return httpx.Response(200, json={"status": "ok"})

        real_client = httpx.AsyncClient

        def factory(*args, **kwargs):
            return real_client(transport=httpx.MockTransport(handler))

        monkeypatch.setattr("app.api.agents.httpx.AsyncClient", factory)

        response = await client.post(f"/api/agents/{agent.id}/connect", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True, f"connect failed: {body}"
        assert body["status"] == "connected"
