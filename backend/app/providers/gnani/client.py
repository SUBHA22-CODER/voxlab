# client.py
# Resilient async API client for Gnani AI (Prisma STT & Timbre TTS).
# Complies with official specs: https://docs.gnani.ai/
# Zero credential leakage: API keys are redacted from logs and errors.

from __future__ import annotations

import asyncio
import io
import logging
import struct
import time
import wave

import httpx

from .schemas import (
    GnaniHealthCheck,
    PrismaSTTResponse,
    TimbreAudioConfig,
    TimbreTTSRequest,
    TimbreTTSResponse,
)
from .languages import supported_stt_languages

logger = logging.getLogger("voxlab.providers.gnani")

DEFAULT_BASE_URL = "https://api.vachana.ai"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 0.5


class GnaniAPIError(Exception):
    """Base exception for Gnani API errors."""

    def __init__(self, message: str, status_code: int | None = None, response_body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class GnaniAuthenticationError(GnaniAPIError):
    """Raised when X-API-Key-ID is missing or rejected (401/403)."""


class GnaniRateLimitError(GnaniAPIError):
    """Raised when rate limit is exceeded (429)."""


class GnaniClient:
    """Async client managing communication with Gnani Vachana APIs."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": "VoxLab-Reliability-Platform/2.5",
        }
        if self.api_key:
            headers["X-API-Key-ID"] = self.api_key
        return headers

    def _redacted_headers(self) -> dict[str, str]:
        headers = self._headers()
        if "X-API-Key-ID" in headers:
            headers["X-API-Key-ID"] = "REDACTED"
        return headers

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        model: str = "prisma-v2.5",
        language_code: str = "hi-IN",
    ) -> PrismaSTTResponse:
        """Transcribe speech audio via Gnani Prisma STT (POST /stt/v3)."""
        if not self.api_key:
            raise GnaniAuthenticationError("GNANI_API_KEY is not configured on VoxLab backend.")

        url = f"{self.base_url}/stt/v3"
        started = time.perf_counter()

        # Build multipart/form-data payload as per official docs
        files = {
            "audio_file": (filename, audio_bytes, "audio/wav"),
        }
        data = {
            "model": model,
            "language_code": language_code,
        }

        headers = {"X-API-Key-ID": self.api_key}

        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    logger.debug("Dispatching Prisma STT request to %s (attempt %d)", url, attempt)
                    response = await client.post(url, headers=headers, files=files, data=data)

                latency = time.perf_counter() - started

                if response.status_code in (401, 403):
                    raise GnaniAuthenticationError(
                        f"Gnani authentication failed with HTTP {response.status_code}.",
                        status_code=response.status_code,
                        response_body=response.text,
                    )
                if response.status_code == 429:
                    raise GnaniRateLimitError(
                        "Gnani rate limit reached (HTTP 429).",
                        status_code=429,
                        response_body=response.text,
                    )
                if response.status_code >= 500:
                    raise GnaniAPIError(
                        f"Gnani server error: HTTP {response.status_code}",
                        status_code=response.status_code,
                        response_body=response.text,
                    )

                if response.status_code >= 400:
                    raise GnaniAPIError(
                        f"Gnani API error: HTTP {response.status_code}",
                        status_code=response.status_code,
                        response_body=response.text,
                    )
                payload = response.json()

                # Extract transcript per official schema: 'transcript' or fallback 'text'
                transcript = (
                    payload.get("transcript")
                    or payload.get("text")
                    or ""
                ).strip()

                return PrismaSTTResponse(
                    success=payload.get("success", True),
                    request_id=payload.get("request_id"),
                    transcript=transcript,
                    model=payload.get("model", model),
                    detected_language_code=payload.get("detected_language_code", language_code),
                    processing_time=payload.get("processing_time"),
                    end_to_end_latency=payload.get("end_to_end_latency", round(latency, 4)),
                    raw=payload,
                )

            except (httpx.ConnectError, httpx.TimeoutException, GnaniAPIError) as exc:
                last_exc = exc
                if isinstance(exc, (GnaniAuthenticationError, GnaniRateLimitError)):
                    raise
                if attempt < MAX_RETRIES:
                    backoff = INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1))
                    logger.warning("Gnani STT error (%s); retrying in %.2fs...", exc, backoff)
                    await asyncio.sleep(backoff)
                else:
                    break

        raise GnaniAPIError(f"Prisma STT request failed after {MAX_RETRIES} attempts: {last_exc}")

    async def synthesize(
        self,
        text: str,
        voice: str = "Nalini",
        model: str = "timbre-v2.5",
        language: str = "hi-IN",
        speed: float = 1.0,
        audio_config: TimbreAudioConfig | None = None,
    ) -> TimbreTTSResponse:
        """Synthesize speech audio via Gnani Timbre TTS (POST /api/v1/tts/inference)."""
        if not self.api_key:
            raise GnaniAuthenticationError("GNANI_API_KEY is not configured on VoxLab backend.")

        url = f"{self.base_url}/api/v1/tts/inference"
        cfg = audio_config or TimbreAudioConfig()

        request_body = TimbreTTSRequest(
            text=text,
            voice=voice,
            model=model,
            language=language,
            speed=speed,
            audio_config=cfg,
        ).model_dump()

        headers = {
            "Content-Type": "application/json",
            "X-API-Key-ID": self.api_key,
        }

        started = time.perf_counter()
        last_exc: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    logger.debug("Dispatching Timbre TTS request to %s (attempt %d)", url, attempt)
                    response = await client.post(url, headers=headers, json=request_body)

                latency = time.perf_counter() - started

                if response.status_code in (401, 403):
                    raise GnaniAuthenticationError(
                        f"Gnani authentication failed with HTTP {response.status_code}.",
                        status_code=response.status_code,
                        response_body=response.text,
                    )
                if response.status_code == 429:
                    raise GnaniRateLimitError(
                        "Gnani rate limit reached (HTTP 429).",
                        status_code=429,
                        response_body=response.text,
                    )
                if response.status_code >= 500:
                    raise GnaniAPIError(
                        f"Gnani server error: HTTP {response.status_code}",
                        status_code=response.status_code,
                        response_body=response.text,
                    )

                if response.status_code >= 400:
                    raise GnaniAPIError(
                        f"Gnani API error: HTTP {response.status_code}",
                        status_code=response.status_code,
                        response_body=response.text,
                    )

                raw_content = response.content
                content_type = response.headers.get("content-type", "audio/wav")

                # If Gnani returns streaming chunked WAV (RIFF with 0xFFFFFFFF header),
                # patch header sizes with actual received byte count so audio plays properly in browsers.
                if len(raw_content) >= 44 and raw_content[:4] == b"RIFF":
                    mutable = bytearray(raw_content)
                    struct.pack_into("<I", mutable, 4, len(mutable) - 8)
                    struct.pack_into("<I", mutable, 40, len(mutable) - 44)
                    audio_bytes = bytes(mutable)
                elif len(raw_content) > 0 and raw_content[:4] != b"RIFF":
                    # Raw PCM fallback: wrap into standard RIFF WAV
                    buf = io.BytesIO()
                    with wave.open(buf, "wb") as wf:
                        wf.setnchannels(cfg.num_channels)
                        wf.setsampwidth(cfg.sample_width)
                        wf.setframerate(cfg.sample_rate)
                        wf.writeframes(raw_content)
                    audio_bytes = buf.getvalue()
                else:
                    audio_bytes = raw_content

                # Compute exact duration from patched WAV
                duration = 0.0
                sample_rate = cfg.sample_rate
                try:
                    with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                        frames = wf.getnframes()
                        sample_rate = wf.getframerate()
                        duration = round(frames / sample_rate, 4)
                except Exception:  # noqa: BLE001 - non-wav duration estimate
                    # Non-wav or chunked stream estimate
                    duration = max(0.1, round(len(text) * 0.06, 2))

                return TimbreTTSResponse(
                    success=True,
                    audio_bytes=audio_bytes,
                    duration_seconds=duration,
                    latency_seconds=round(latency, 4),
                    format=content_type,
                    sample_rate=sample_rate,
                    voice=voice,
                    language=language,
                    model=model,
                )

            except (httpx.ConnectError, httpx.TimeoutException, GnaniAPIError) as exc:
                last_exc = exc
                if isinstance(exc, (GnaniAuthenticationError, GnaniRateLimitError)):
                    raise
                if attempt < MAX_RETRIES:
                    backoff = INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1))
                    logger.warning("Gnani TTS error (%s); retrying in %.2fs...", exc, backoff)
                    await asyncio.sleep(backoff)
                else:
                    break

        raise GnaniAPIError(f"Timbre TTS request failed after {MAX_RETRIES} attempts: {last_exc}")

    async def health_check(self) -> GnaniHealthCheck:
        """Inspect provider configuration and connectivity without leaking keys."""
        from ...core.config import get_settings

        settings = get_settings()
        has_key = bool(self.api_key)

        if not settings.gnani_enabled:
            return GnaniHealthCheck(
                status="unconfigured",
                stt_model=settings.gnani_stt_model,
                tts_model=settings.gnani_tts_model,
                base_url=self.base_url,
                has_api_key=has_key,
                supported_languages_count=len(supported_stt_languages()),
                detail="Gnani AI integration is disabled (GNANI_ENABLED=false). Set GNANI_ENABLED=true and GNANI_API_KEY to activate.",
            )

        if not has_key:
            return GnaniHealthCheck(
                status="unconfigured",
                stt_model=settings.gnani_stt_model,
                tts_model=settings.gnani_tts_model,
                base_url=self.base_url,
                has_api_key=False,
                supported_languages_count=len(supported_stt_languages()),
                detail="GNANI_API_KEY is not configured.",
            )

        # Basic connectivity probe
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(self.base_url, headers=self._headers())
                status = "healthy" if res.status_code < 500 else "error"
                detail = f"Endpoint responded with HTTP {res.status_code}."
        except Exception as exc:  # noqa: BLE001 - health probe never raises
            status = "error"
            detail = f"Connectivity check failed: {exc}"

        return GnaniHealthCheck(
            status=status,
            stt_model=settings.gnani_stt_model,
            tts_model=settings.gnani_tts_model,
            base_url=self.base_url,
            has_api_key=True,
            supported_languages_count=len(supported_stt_languages()),
            detail=detail,
        )
