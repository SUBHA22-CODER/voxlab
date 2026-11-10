import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    agents,
    auth,
    darwin,
    playground,
    reports,
    scenarios,
    sessions,
    test_runs,
    traces,
)
from app.core.config import get_settings
from app.core.database import SessionLocal, dispose_engine, init_db
from app.core.rate_limit import auth_rate_limit_middleware
from app.seed import ensure_demo_user, load_builtin_scenarios

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("voxlab")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # Dev/demo convenience: create tables on startup. Alembic migrations are
    # available for strict production schema management (VoxLab 2.5).
    await init_db()
    async with SessionLocal() as db:
        loaded = await load_builtin_scenarios(db)
        await ensure_demo_user(db)
    logger.info("Builtin scenarios loaded: %d", loaded)

    # Audio retention sweep (VoxLab 2.5): recordings are sensitive and must
    # not linger past the configured window. Runs in a worker thread — the
    # directory scan must not delay startup.
    from app.services.retention import sweep_old_artifacts

    retention_stats = await asyncio.to_thread(
        sweep_old_artifacts, settings.audio_storage_dir, settings.audio_retention_days
    )
    if retention_stats["deleted"]:
        logger.info("Audio retention sweep: %s", retention_stats)
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_origin_regex=r"^https://.*\.onrender\.com$|^https://.*\.vercel\.app$|^http://localhost(:\d+)?$|^http://127\.0\.0\.1(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(auth_rate_limit_middleware)

    for router in (
        auth.router,
        agents.router,
        scenarios.router,
        test_runs.router,
        sessions.router,
        traces.router,
        reports.router,
        darwin.router,
    ):
        app.include_router(router)
    app.include_router(playground.router)

    # VoxLab 2.0 versioned APIs (audio, darwin audio, regressions, benchmarks)
    from app.api.v1 import api_v1_router

    app.include_router(api_v1_router)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log full context server-side; return a generic message to clients.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    @app.get("/", tags=["root"])
    async def root() -> dict:
        return {
            "name": "VoxLab API & Darwin Fuzzing Engine",
            "status": "online",
            "version": "0.1.0",
            "docs_url": "/docs",
            "health_url": "/api/health",
        }

    @app.get("/api/health", tags=["health"])
    async def health() -> dict:
        return {
            "status": "ok",
            "app": settings.app_name,
            "llm_judge": "enabled" if get_settings().llm_api_key else "heuristic",
        }

    return app


app = create_app()
