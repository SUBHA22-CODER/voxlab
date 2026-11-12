# providers.py
# Provider status, capabilities, and health check endpoint for VoxLab.

from __future__ import annotations

from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.models import User
from app.core.config import get_settings
from app.providers.gnani.client import GnaniClient
from app.providers.gnani.languages import supported_stt_languages, supported_tts_languages
from app.speech.registry import engine_registry

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])


@router.get("")
async def list_providers(user: User = Depends(get_current_user)):
    """Return status and capabilities of all integrated speech & dictation providers."""
    settings = get_settings()
    gnani_client = GnaniClient(api_key=settings.gnani_api_key, base_url=settings.gnani_base_url)
    gnani_health = await gnani_client.health_check()

    providers = [
        {
            "id": "wispr_flow",
            "name": "Wispr Flow",
            "category": "dictation_pipeline",
            "status": "active",
            "capabilities": {
                "dictation_cleaner": True,
                "conversational_fuzzing": True,
                "wer_cer_scoring": True,
                "semantic_analysis": True,
                "self_correction_testing": True,
                "human_in_the_loop": True,
            },
            "description": "Dictation reliability, disfluency resolution, and self-correction testing platform.",
            "attribution": "Tailored for Wispr Flow dictation pipelines. https://wisprflow.ai",
        },
        {
            "id": "gnani_ai",
            "name": "Gnani AI",
            "category": "indic_multilingual_voice_ai",
            "status": "active" if gnani_health.has_api_key and settings.gnani_enabled else "unconfigured",
            "models": {
                "stt": settings.gnani_stt_model,
                "tts": settings.gnani_tts_model,
            },
            "capabilities": {
                "prisma_stt": True,
                "timbre_tts": True,
                "indic_speech_lab": True,
                "code_switching": True,
                "languages_count": len(supported_stt_languages()),
                "stt_languages": supported_stt_languages(),
                "tts_languages": supported_tts_languages(),
            },
            "health": gnani_health.model_dump(),
            "description": "Enterprise Indic voice infrastructure covering 12+ Indian languages and code-switching.",
            "attribution": "Official Gnani AI Vachana platform integration. https://docs.gnani.ai/",
        },
    ]

    return {
        "providers": providers,
        "local_speech_engines": engine_registry.describe_all(),
    }
