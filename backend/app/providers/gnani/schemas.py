# schemas.py
# Strictly-typed Pydantic schemas for Gnani AI Prisma STT and Timbre TTS.
# Verified against official documentation (https://docs.gnani.ai/).

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


# --- Prisma Speech-to-Text Schemas ---

class PrismaSTTOptions(BaseModel):
    model: str = Field(default="prisma-v2.5", description="Prisma model version: prisma-v2.5 or prisma-v3.0")
    language_code: str = Field(default="hi-IN", description="Language code (e.g. hi-IN, en-IN, indic-auto)")


class PrismaSTTResponse(BaseModel):
    success: bool = True
    request_id: str | None = None
    transcript: str = ""
    model: str = "prisma-v2.5"
    detected_language_code: str | None = None
    processing_time: float | None = None
    end_to_end_latency: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


# --- Timbre Text-to-Speech Schemas ---

class TimbreAudioConfig(BaseModel):
    encoding: str = "linear_pcm"
    container: str = "wav"
    num_channels: int = 1
    sample_rate: int = 16000
    sample_width: int = 2


class TimbreTTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000, description="Text to synthesize into speech")
    voice: str = Field(default="Nalini", description="Voice identifier (e.g. Nalini, Arjun, Rohan)")
    model: str = Field(default="timbre-v2.5", description="Timbre model version: timbre-v2.5 or timbre-v3.0")
    language: str = Field(default="hi-IN", description="Indic language code (e.g. hi-IN, bn-IN, ta-IN)")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech rate multiplier (0.5 to 2.0)")
    audio_config: TimbreAudioConfig = Field(default_factory=TimbreAudioConfig)


class TimbreTTSResponse(BaseModel):
    success: bool = True
    audio_bytes: bytes = b""
    duration_seconds: float = 0.0
    latency_seconds: float = 0.0
    format: str = "audio/wav"
    sample_rate: int = 16000
    voice: str = "Nalini"
    language: str = "hi-IN"
    model: str = "timbre-v2.5"


# --- Provider Health & Connection Schemas ---

class GnaniHealthCheck(BaseModel):
    provider: str = "gnani"
    status: str  # "healthy" | "unconfigured" | "error"
    stt_model: str
    tts_model: str
    base_url: str
    has_api_key: bool
    supported_languages_count: int
    detail: str = ""

