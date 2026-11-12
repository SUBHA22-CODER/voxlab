# test_gnani_live.py
# Phase 14: Dedicated real API integration test suite for Gnani AI.
# INACTIVE BY DEFAULT: Marked with @pytest.mark.live_api and strictly skips
# unless GNANI_ENABLED=true, GNANI_API_KEY is provided, and operator authorizes live testing.

from __future__ import annotations

import os
import time
import pytest

from app.core.config import get_settings
from app.providers.gnani.client import GnaniClient
from app.indic.normalization import normalize_indic_text
from app.speech.metrics import char_error_rate, word_error_rate

pytestmark = pytest.mark.live_api


@pytest.fixture(scope="module")
def live_client() -> GnaniClient:
    settings = get_settings()
    api_key = settings.gnani_api_key or os.getenv("GNANI_API_KEY", "")
    if not settings.gnani_enabled or not api_key:
        pytest.skip(
            "Live Gnani AI testing skipped: GNANI_ENABLED=true and GNANI_API_KEY are required. "
            "Pass credentials to run live verification."
        )
    return GnaniClient(api_key=api_key, base_url=settings.gnani_base_url)


@pytest.mark.asyncio
async def test_live_gnani_health_and_connectivity(live_client: GnaniClient) -> None:
    """Validate live connectivity and credential acceptance."""
    health = await live_client.health_check()
    assert health.has_api_key is True
    assert health.status == "healthy", f"Gnani endpoint reported unhealthy: {health.detail}"


@pytest.mark.asyncio
async def test_live_timbre_speech_synthesis(live_client: GnaniClient) -> None:
    """Validate real Timbre TTS generation: Hindi text -> WAV audio stream."""
    test_text = "नमस्ते, यह वॉक्सलैब का वास्तविक परीक्षण है।"
    started = time.perf_counter()

    res = await live_client.synthesize(
        text=test_text,
        voice="Nalini",
        language="hi-IN",
        speed=1.0,
    )

    elapsed = time.perf_counter() - started
    assert res.success is True
    assert len(res.audio_bytes) > 1000, "Synthesized audio payload must not be empty"
    assert res.duration_seconds > 0.5, "Duration must be measurable"
    assert res.sample_rate in (16000, 22050, 24000, 48000)
    print(f"\n[LIVE TEST] Timbre TTS generation latency: {elapsed:.3f}s for {len(res.audio_bytes)} bytes")


@pytest.mark.asyncio
async def test_live_prisma_speech_transcription(live_client: GnaniClient) -> None:
    """Validate real Prisma STT transcription using synthesized Hindi audio."""
    # First generate test audio with ground-truth text
    reference_text = "नमस्ते यह वॉक्सलैब का परीक्षण है"
    tts_res = await live_client.synthesize(
        text=reference_text,
        voice="Nalini",
        language="hi-IN",
    )

    # Transcribe the audio through Prisma
    stt_res = await live_client.transcribe(
        audio_bytes=tts_res.audio_bytes,
        filename="live_eval_test.wav",
        language_code="hi-IN",
    )

    assert stt_res.success is True
    assert len(stt_res.transcript) > 0, "Prisma transcript must not be empty"

    # Evaluate WER/CER with Indic normalization
    norm_ref = normalize_indic_text(reference_text)
    norm_hyp = normalize_indic_text(stt_res.transcript)
    wer, _ = word_error_rate(norm_ref, norm_hyp)
    cer = char_error_rate(norm_ref, norm_hyp)

    print(f"\n[LIVE TEST] Prisma Reference: {norm_ref}")
    print(f"[LIVE TEST] Prisma Hypothesis: {norm_hyp}")
    print(f"[LIVE TEST] Live Indic WER: {wer:.4f}, CER: {cer:.4f}")
