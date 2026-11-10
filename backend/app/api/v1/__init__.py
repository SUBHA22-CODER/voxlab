"""VoxLab 2.0 versioned API surface (v1): audio, darwin audio, regressions,
benchmarks. Existing /api/* routes remain untouched (backward compatibility)."""

from fastapi import APIRouter

from .audio import router as audio_router
from .benchmarks import router as benchmarks_router
from .darwin_audio import router as darwin_audio_router
from .regressions import router as regressions_router
from .analytics import router as analytics_router
from .security import router as security_router

api_v1_router = APIRouter()
api_v1_router.include_router(audio_router)
api_v1_router.include_router(darwin_audio_router)
api_v1_router.include_router(regressions_router)
api_v1_router.include_router(benchmarks_router)
api_v1_router.include_router(security_router)
api_v1_router.include_router(analytics_router)

__all__ = ["api_v1_router"]
