"""Background worker abstraction.

MVP: in-process asyncio execution (zero infra). When REDIS_URL is set and a
separate worker deployment is desired, `dispatch_to_queue` enqueues the run
for an ARQ worker running `execute_run` — the orchestration logic is shared.
"""

from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def worker_mode() -> str:
    return "redis" if get_settings().redis_url else "in-process"


async def dispatch_to_queue(run_id: int) -> bool:
    """Try to enqueue to Redis/ARQ. Returns False when Redis isn't configured."""
    settings = get_settings()
    if not settings.redis_url:
        return False
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await pool.enqueue_job("execute_voxlab_run", run_id)
        await pool.aclose()
        return True
    except Exception as exc:
        logger.warning("Redis dispatch failed (%s); falling back in-process", exc)
        return False


# Entry point executed by an ARQ worker (if deployed that way).
async def execute_voxlab_run(ctx: dict, run_id: int) -> None:
    from app.core.database import SessionLocal
    from app.engine.orchestrator import Orchestrator

    await Orchestrator(SessionLocal).execute_run(run_id)
