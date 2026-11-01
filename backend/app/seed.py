"""Seeding: builtin scenarios, demo user, demo agent registration.

Run from the backend/ directory:
    python -m app.seed             # seed user + agent + scenarios
    python -m app.seed --with-run  # also execute a demo benchmark if the
                                   # demo agent is running on :8100
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Agent, Scenario, TestRun, User

logger = logging.getLogger("voxlab.seed")

DEMO_EMAIL = "demo@voxlab.dev"
DEMO_PASSWORD = "demo1234"
DEMO_AGENT_NAME = "Customer Support Agent (Demo)"
DEMO_AGENT_ENDPOINT = "http://localhost:8100/conversation"


def find_scenarios_dir() -> Path | None:
    """Locate the repo-level scenarios/ directory (works local and in Docker)."""
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "scenarios",  # backend/app/seed.py → repo root
        here.parents[1] / "scenarios",  # /app/app/seed.py → /app/scenarios
        Path.cwd() / "scenarios",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


async def load_builtin_scenarios(db: AsyncSession) -> int:
    scenarios_dir = find_scenarios_dir()
    if scenarios_dir is None:
        logger.warning("No scenarios directory found; skipping builtin scenario load")
        return 0

    loaded = 0
    for path in sorted(scenarios_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Skipping unreadable scenario %s: %s", path.name, exc)
            continue
        name = data.get("name") or path.stem
        category = data.get("category", "custom")

        existing = await db.scalar(
            select(Scenario).where(Scenario.name == name, Scenario.is_builtin.is_(True))
        )
        if existing:
            existing.definition = data
            existing.category = category
        else:
            db.add(
                Scenario(
                    name=name,
                    category=category,
                    definition=data,
                    is_builtin=True,
                )
            )
        loaded += 1
    await db.commit()
    return loaded


async def ensure_demo_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        user = User(
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
        )
        db.add(user)
        await db.commit()
        logger.info("Created demo user %s (password: %s)", DEMO_EMAIL, DEMO_PASSWORD)
    return user


async def ensure_demo_agent(db: AsyncSession, user: User) -> Agent:
    agent = await db.scalar(
        select(Agent).where(Agent.user_id == user.id, Agent.name == DEMO_AGENT_NAME)
    )
    if agent is None:
        agent = Agent(
            user_id=user.id,
            name=DEMO_AGENT_NAME,
            description=(
                "Demo customer-support voice agent with mock order APIs and "
                "deliberate failure switches (see agent-examples/)."
            ),
            endpoint=DEMO_AGENT_ENDPOINT,
            agent_type="http",
            stt_provider="browser",
            llm_provider="openai-compatible",
            tts_provider="browser",
            config={"timeout_s": 30},
        )
        db.add(agent)
        await db.commit()
        logger.info("Registered demo agent at %s", DEMO_AGENT_ENDPOINT)
    return agent


async def seed_all(with_run: bool = False) -> None:
    async with SessionLocal() as db:
        await load_builtin_scenarios(db)
        user = await ensure_demo_user(db)
        agent = await ensure_demo_agent(db, user)

    if not with_run:
        return

    # Only auto-run when the demo agent is actually reachable.
    import httpx

    try:
        async with httpx.AsyncClient(timeout=3) as client:
            await client.get("http://localhost:8100/health")
    except httpx.HTTPError:
        logger.warning(
            "Demo agent not reachable on :8100 — skipping demo benchmark run. "
            "Start it with: uvicorn main:app --port 8100 (in agent-examples/customer-support-agent)"
        )
        return

    from app.engine.orchestrator import Orchestrator

    async with SessionLocal() as db:
        scenario_ids = [
            s.id
            for s in (
                await db.scalars(select(Scenario).where(Scenario.is_builtin.is_(True)))
            ).all()
        ]
        run = TestRun(
            user_id=user.id,
            agent_id=agent.id,
            config={"scenario_ids": scenario_ids, "weights": {}},
            total_sessions=len(scenario_ids),
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        run_id = run.id

    logger.info("Executing demo benchmark run %d ...", run_id)
    await Orchestrator(SessionLocal).execute_run(run_id)

    async with SessionLocal() as db:
        from app.models import Report

        report = await db.scalar(select(Report).where(Report.test_run_id == run_id))
        if report:
            logger.info("Demo benchmark complete — score %.2f/100", report.score)
            logger.info("Sign in at the frontend with %s / %s to explore the report.", DEMO_EMAIL, DEMO_PASSWORD)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed VoxLab demo data")
    parser.add_argument(
        "--with-run",
        action="store_true",
        help="Also execute a demo benchmark (requires the demo agent on :8100)",
    )
    args = parser.parse_args()
    asyncio.run(seed_all(with_run=args.with_run))


if __name__ == "__main__":
    main()
