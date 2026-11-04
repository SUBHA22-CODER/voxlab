"""End-to-end API tests: register → run benchmark → traces → report → compare."""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.engine.orchestrator import Orchestrator
from tests.scripted_agent import ScriptedAgentAdapter

pytestmark = pytest.mark.integration


async def wait_for_run(client, run_id: int, headers: dict, timeout_s: float = 15.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        response = await client.get(f"/api/test-runs/{run_id}", headers=headers)
        data = response.json()
        if data["status"] in ("completed", "failed", "cancelled"):
            return data
        await asyncio.sleep(0.05)
    raise TimeoutError(f"run {run_id} did not finish in {timeout_s}s")


class TestAuthFlow:
    async def test_register_login_me(self, client):
        response = await client.post(
            "/api/auth/register",
            json={"email": "new@example.com", "password": "password123"},
        )
        assert response.status_code == 201
        token = response.json()["access_token"]

        response = await client.post(
            "/api/auth/login",
            json={"email": "new@example.com", "password": "password123"},
        )
        assert response.status_code == 200

        response = await client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["email"] == "new@example.com"

    async def test_duplicate_registration_conflict(self, client, user):
        response = await client.post(
            "/api/auth/register",
            json={"email": "dev@example.com", "password": "password123"},
        )
        assert response.status_code == 409

    async def test_wrong_password_unauthorized(self, client, user):
        response = await client.post(
            "/api/auth/login",
            json={"email": "dev@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401

    async def test_me_requires_token(self, client):
        response = await client.get("/api/auth/me")
        assert response.status_code == 401


class TestAgentRegistry:
    async def test_register_and_list_agents(self, client, auth_headers):
        response = await client.post(
            "/api/agents",
            headers=auth_headers,
            json={
                "name": "My Agent",
                "endpoint": "https://api.example.com/agent/conversation",
                "agent_type": "http",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["connection_status"] == "untested"
        assert "auth_config" not in body  # secrets never serialized

        response = await client.get("/api/agents", headers=auth_headers)
        assert len(response.json()) == 1

    async def test_rejects_bad_scheme(self, client, auth_headers):
        response = await client.post(
            "/api/agents",
            headers=auth_headers,
            json={"name": "x", "endpoint": "ftp://example.com", "agent_type": "http"},
        )
        assert response.status_code == 400

    async def test_agent_isolation_between_users(self, client, auth_headers, user):
        # Another user's account.
        await client.post(
            "/api/auth/register",
            json={"email": "other@example.com", "password": "password123"},
        )
        other_login = await client.post(
            "/api/auth/login",
            json={"email": "other@example.com", "password": "password123"},
        )
        other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

        await client.post(
            "/api/agents",
            headers=auth_headers,
            json={"name": "Mine", "endpoint": "https://x.example.com/conv", "agent_type": "http"},
        )
        response = await client.get("/api/agents", headers=other_headers)
        assert not any(a["name"] == "Mine" for a in response.json())


class TestBenchmarkFlow:
    async def test_full_benchmark_flow(self, client, db_engine, auth_headers, agent, scenario, monkeypatch):
        fake_adapter = ScriptedAgentAdapter(
            {
                "hello": {
                    "reply": "Hello! How can I help?",
                    "state": {"turns": 1},
                    "tool_calls": [
                        {"name": "check_order_status", "args": {}, "status": "success", "duration_ms": 40}
                    ],
                }
            }
        )
        monkeypatch.setattr(
            "app.engine.orchestrator.build_adapter", lambda cfg, auth: fake_adapter
        )
        test_factory = async_sessionmaker(db_engine, expire_on_commit=False)
        test_orchestrator = Orchestrator(test_factory)
        monkeypatch.setattr("app.api.test_runs.orchestrator", test_orchestrator)

        # Start a benchmark run (dispatches in background).
        response = await client.post(
            "/api/test-runs",
            headers=auth_headers,
            json={"agent_id": agent.id, "scenario_ids": [scenario.id]},
        )
        assert response.status_code == 202, response.text
        run_id = response.json()["id"]

        run = await wait_for_run(client, run_id, auth_headers)
        assert run["status"] == "completed", run.get("error")
        assert run["progress"] == 1
        assert len(run["sessions"]) == 1
        assert run["sessions"][0]["evaluation"]["scores"]["latency"] > 0

        # Report attached to the run.
        report = run["report"]
        assert report is not None
        assert 0 <= report["score"] <= 100
        assert report["formula"].startswith("Score =")
        assert report["totals"]["completed"] == 1

        # Session detail: events + trace collected.
        session_id = run["sessions"][0]["id"]
        response = await client.get(f"/api/sessions/{session_id}", headers=auth_headers)
        body = response.json()
        event_types = [e["event_type"] for e in body["events"]]
        assert "session_started" in event_types
        assert "user_message" in event_types
        assert "agent_message" in event_types
        assert "tool_call" in event_types
        assert body["trace"]["summary"]["turn_count"] == 1

        # Spec endpoint: GET /api/sessions/{id}/traces
        response = await client.get(f"/api/sessions/{session_id}/traces", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["trace_data"]["turns"][0]["stages"]

        # Run report endpoint.
        response = await client.get(f"/api/test-runs/{run_id}/report", headers=auth_headers)
        assert response.status_code == 200
        report_id = response.json()["id"]

        # Second run for the comparison endpoint.
        response = await client.post(
            "/api/test-runs",
            headers=auth_headers,
            json={"agent_id": agent.id, "scenario_ids": [scenario.id]},
        )
        run2_id = response.json()["id"]
        await wait_for_run(client, run2_id, auth_headers)
        response = await client.get(f"/api/test-runs/{run2_id}/report", headers=auth_headers)
        report2_id = response.json()["id"]

        response = await client.get(
            f"/api/reports/{report_id}/compare/{report2_id}", headers=auth_headers
        )
        assert response.status_code == 200
        comparison = response.json()
        assert "deltas" in comparison and "score" in comparison["deltas"]

    async def test_run_requires_owned_agent(self, client, auth_headers, scenario):
        response = await client.post(
            "/api/test-runs",
            headers=auth_headers,
            json={"agent_id": 99999, "scenario_ids": [scenario.id]},
        )
        assert response.status_code == 404

    async def test_run_requires_scenarios(self, client, auth_headers, agent):
        response = await client.post(
            "/api/test-runs",
            headers=auth_headers,
            json={"agent_id": agent.id, "scenario_ids": []},
        )
        assert response.status_code == 400

    async def test_scenario_crud(self, client, auth_headers):
        response = await client.post(
            "/api/scenarios",
            headers=auth_headers,
            json={
                "name": "Custom Check",
                "category": "conversation",
                "definition": {
                    "name": "Custom Check",
                    "category": "conversation",
                    "steps": [{"type": "user_message", "content": "ping"}],
                    "checks": [],
                },
            },
        )
        assert response.status_code == 201
        scenario_id = response.json()["id"]

        response = await client.get("/api/scenarios", headers=auth_headers)
        names = [s["name"] for s in response.json()]
        assert "Custom Check" in names

        response = await client.delete(f"/api/scenarios/{scenario_id}", headers=auth_headers)
        assert response.status_code == 204

    async def test_scenario_rejects_missing_steps(self, client, auth_headers):
        response = await client.post(
            "/api/scenarios",
            headers=auth_headers,
            json={"name": "Bad", "category": "x", "definition": {"no_steps": True}},
        )
        assert response.status_code == 400
