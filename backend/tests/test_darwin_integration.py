"""Integration test for Darwin: runs small evolutionary campaign against demo agent."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.darwin.evolution import EvolutionEngine
from app.darwin.regression import export_finding_to_regression
from app.models import Agent, User
from app.models.darwin import DarwinFinding, DarwinGeneration, DarwinRun
from app.services.llm import LLMService
from tests.scripted_agent import ScriptedAgentAdapter


@pytest.mark.asyncio
@pytest.mark.integration
async def test_darwin_evolution_integration_run(db_session: AsyncSession, monkeypatch):
    # Setup test user and test agent
    user = User(email="darwin_tester@voxlab.dev", password_hash="testpass")
    db_session.add(user)
    await db_session.flush()

    # Agent with deliberate weaknesses (returns un-cleansed text containing "no wait" to trigger failure)
    fake_adapter = ScriptedAgentAdapter(
        default={
            "reply": "I have processed your request for Tuesday, no wait, Wednesday.",
            "tool_calls": [],
            "state": {"turns": 1},
            "timings": {"llm_ms": 100, "tool_ms": 20},
        }
    )
    monkeypatch.setattr("app.darwin.evolution.build_adapter", lambda *args, **kwargs: fake_adapter)

    agent = Agent(
        user_id=user.id,
        name="Test Voice Agent",
        endpoint="http://localhost:8100/conversation",
        agent_type="http",
        config={"timeout_s": 10},
    )
    db_session.add(agent)
    await db_session.flush()

    # Create Darwin run record
    run = DarwinRun(
        user_id=user.id,
        agent_id=agent.id,
        status="queued",
        config={
            "population_size": 4,
            "generations": 2,
            "top_k": 2,
            "personas": ["self_corrector", "impatient_interrupter"],
            "seed": 100,
            "failure_threshold": 0.3,
        },
        stats={},
        progress=0,
    )
    db_session.add(run)
    await db_session.commit()

    # Run evolution engine with mocked LLM (heuristic mode)
    factory = async_sessionmaker(db_session.bind, expire_on_commit=False)
    mock_llm = LLMService(api_key="")
    engine = EvolutionEngine(factory, llm=mock_llm)
    await engine.execute_evolution(run.id)

    # Verify run completed
    await db_session.refresh(run)
    assert run.status == "completed"
    assert run.progress == 100

    # Verify generations were recorded
    generations = (
        await db_session.scalars(
            select(DarwinGeneration).where(DarwinGeneration.run_id == run.id)
        )
    ).all()
    assert len(generations) >= 1
    assert generations[0].best_fitness >= 0.0

    # Verify findings were produced, minimized, diagnosed, and can be exported
    findings = (
        await db_session.scalars(
            select(DarwinFinding).where(DarwinFinding.run_id == run.id)
        )
    ).all()
    assert len(findings) >= 1

    f = findings[0]
    assert f.persona in ["self_corrector", "impatient_interrupter"]
    assert len(f.minimized_steps) <= f.original_steps_count
    assert "category" in f.diagnosis

    # Test regression export
    path, scen_id = await export_finding_to_regression(f, db_session)
    assert path.exists()
    assert scen_id is not None
