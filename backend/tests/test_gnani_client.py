# test_gnani_client.py
# Unit tests for GnaniClient resilience, retry loop, authentication, and error mapping.

from __future__ import annotations

import httpx
import pytest

from app.providers.gnani.client import (
    GnaniAuthenticationError,
    GnaniClient,
    GnaniRateLimitError,
)


def test_gnani_client_headers_contain_api_key() -> None:
    client = GnaniClient(api_key="test-gnani-key-xyz")
    headers = client._headers()
    assert headers["X-API-Key-ID"] == "test-gnani-key-xyz"
    assert headers["User-Agent"].startswith("VoxLab")


def test_gnani_client_redacts_credentials_in_logs() -> None:
    client = GnaniClient(api_key="super-secret-production-key")
    redacted = client._redacted_headers()
    assert redacted["X-API-Key-ID"] == "REDACTED"
    assert "super-secret" not in str(redacted)


@pytest.mark.asyncio
async def test_transcribe_rejects_empty_api_key() -> None:
    client = GnaniClient(api_key="")
    with pytest.raises(GnaniAuthenticationError, match="not configured"):
        await client.transcribe(audio_bytes=b"dummy-audio-bytes")


@pytest.mark.asyncio
async def test_synthesize_rejects_empty_api_key() -> None:
    client = GnaniClient(api_key="")
    with pytest.raises(GnaniAuthenticationError, match="not configured"):
        await client.synthesize(text="नमस्ते")


@pytest.mark.asyncio
async def test_transcribe_handles_401_auth_error(monkeypatch) -> None:
    client = GnaniClient(api_key="invalid-api-key")

    async def fake_post(*args, **kwargs):
        return httpx.Response(401, json={"detail": "Unauthorized API key"})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with pytest.raises(GnaniAuthenticationError, match="HTTP 401"):
        await client.transcribe(audio_bytes=b"dummy-audio-bytes")


@pytest.mark.asyncio
async def test_transcribe_handles_429_rate_limit(monkeypatch) -> None:
    client = GnaniClient(api_key="valid-key")

    async def fake_post(*args, **kwargs):
        return httpx.Response(429, json={"detail": "Too many requests"})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with pytest.raises(GnaniRateLimitError, match="429"):
        await client.transcribe(audio_bytes=b"dummy-audio-bytes")


@pytest.mark.asyncio
async def test_transcribe_parses_successful_response(monkeypatch) -> None:
    client = GnaniClient(api_key="valid-key")

    fake_json = {
        "success": True,
        "request_id": "gnani-req-9912",
        "transcript": "नमस्ते, आप कैसे हैं?",
        "model": "prisma-v2.5",
        "detected_language_code": "hi-IN",
        "processing_time": 0.42,
        "end_to_end_latency": 0.55,
    }

    async def fake_post(*args, **kwargs):
        return httpx.Response(200, json=fake_json)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    res = await client.transcribe(audio_bytes=b"dummy", language_code="hi-IN")
    assert res.success is True
    assert res.transcript == "नमस्ते, आप कैसे हैं?"
    assert res.request_id == "gnani-req-9912"
    assert res.detected_language_code == "hi-IN"
    assert res.processing_time == 0.42

