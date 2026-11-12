# indic.py
# API routes for Indic Speech Lab, Gnani AI Prisma STT, and Timbre TTS.

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models import User
from app.providers.gnani.languages import (
    INDIC_LANGUAGES,
    TIMBRE_VOICES,
    supported_stt_languages,
    supported_tts_languages,
)
from app.providers.gnani.timbre_adapter import GnaniTimbreEngine
from app.indic.benchmarks import INDIC_BENCHMARK_CORPUS, evaluate_indic_transcription

router = APIRouter(prefix="/api/v1/indic", tags=["indic-speech-lab"])


class IndicEvaluationRequest(BaseModel):
    reference: str = Field(min_length=1)
    hypothesis: str
    expected_loanwords: list[str] = Field(default_factory=list)
    expected_entities: list[str] = Field(default_factory=list)


class TTSSynthesizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    voice: str = Field(default="Nalini")
    language: str = Field(default="hi-IN")
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


@router.get("/languages")
async def list_indic_languages(user: User = Depends(get_current_user)):
    """List all supported Indic languages with script and voice metadata."""
    return {
        "languages": [
            {
                "code": lang.code,
                "name": lang.name,
                "native_name": lang.native_name,
                "script": lang.script,
                "supports_stt": lang.supports_stt,
                "supports_tts": lang.supports_tts,
                "default_voice": lang.default_voice,
                "code_switch_variant": lang.code_switch_variant,
            }
            for lang in INDIC_LANGUAGES.values()
        ],
        "stt_supported": supported_stt_languages(),
        "tts_supported": supported_tts_languages(),
    }


@router.get("/benchmarks")
async def list_indic_benchmarks(user: User = Depends(get_current_user)):
    """Return the reproducible Indic speech and code-switching benchmark corpus."""
    return {
        "items": [
            {
                "id": b.id,
                "language": b.language,
                "category": b.category,
                "reference_transcript": b.reference_transcript,
                "description": b.description,
                "expected_entities": b.expected_entities,
                "expected_numbers": b.expected_numbers,
                "english_loanwords": b.english_loanwords,
            }
            for b in INDIC_BENCHMARK_CORPUS
        ]
    }


@router.post("/evaluate")
async def evaluate_indic(
    body: IndicEvaluationRequest,
    user: User = Depends(get_current_user),
):
    """Dual-layer evaluation: Raw verbatim scoring vs Indic-Normalized scoring."""
    report = evaluate_indic_transcription(
        reference=body.reference,
        hypothesis=body.hypothesis,
        expected_loanwords=body.expected_loanwords or None,
        expected_entities=body.expected_entities or None,
    )
    return report.to_dict()


@router.get("/voices")
async def list_timbre_voices(user: User = Depends(get_current_user)):
    """List supported Gnani Timbre TTS expressive voices."""
    return {
        "voices": TIMBRE_VOICES,
    }


@router.post("/tts/synthesize")
async def synthesize_speech(
    body: TTSSynthesizeRequest,
    user: User = Depends(get_current_user),
):
    """Synthesize speech using Gnani Timbre TTS."""
    engine = GnaniTimbreEngine()
    if not engine.is_available():
        raise HTTPException(
            status_code=503,
            detail="Gnani Timbre TTS is not active. Configure GNANI_ENABLED=true and GNANI_API_KEY in backend environment.",
        )

    try:
        res = await engine.synthesize(
            text=body.text,
            voice=body.voice,
            language=body.language,
            speed=body.speed,
        )
        return Response(
            content=res.audio_bytes,
            media_type="audio/wav",
            headers={
                "X-Latency-Seconds": str(res.latency_seconds),
                "X-Duration-Seconds": str(res.duration_seconds),
                "X-Voice": res.voice,
                "X-Language": res.language,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Timbre TTS synthesis failed: {exc}") from exc
