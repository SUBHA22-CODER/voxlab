import logging
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
from app.seed import load_builtin_scenarios

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("voxlab")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev/demo convenience: create tables on startup. Use Alembic for strict
    # production schema management.
    await init_db()
    async with SessionLocal() as db:
        loaded = await load_builtin_scenarios(db)
    logger.info("Builtin scenarios loaded: %d", loaded)
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
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

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log full context server-side; return a generic message to clients.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    @app.get("/api/health", tags=["health"])
    async def health() -> dict:
        return {
            "status": "ok",
            "app": settings.app_name,
            "llm_judge": "enabled" if get_settings().llm_api_key else "heuristic",
        }

    return app


app = create_app()
