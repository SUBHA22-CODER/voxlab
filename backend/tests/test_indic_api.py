# test_indic_api.py
# API test suite for Indic Speech Lab endpoints (/api/v1/indic/* and /api/v1/providers).

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_indic_languages(client, auth_headers) -> None:
    response = await client.get("/api/v1/indic/languages", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "languages" in data
    assert "stt_supported" in data
    assert "tts_supported" in data
    codes = [entry["code"] for entry in data["languages"]]
    assert "hi-IN" in codes
    assert "ta-IN" in codes
    assert "te-IN" in codes
    assert "bn-IN" in codes


@pytest.mark.asyncio
async def test_list_indic_benchmarks(client, auth_headers) -> None:
    response = await client.get("/api/v1/indic/benchmarks", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) >= 8
    categories = {b["category"] for b in data["items"]}
    assert "code_switching" in categories
    assert "banking" in categories
    assert "numbers_currency" in categories


@pytest.mark.asyncio
async def test_evaluate_indic_endpoint(client, auth_headers) -> None:
    response = await client.post(
        "/api/v1/indic/evaluate",
        headers=auth_headers,
        json={
            "reference": "खाते में ₹५,००० रुपये जमा हैं।",
            "hypothesis": "खाते में 5000 रुपये जमा हैं",
        },
    )
    assert response.status_code == 200
    data = response.json()
    # Indic normalization maps ५००० to 5000 and strips Danda, yielding 0 WER!
    assert data["normalized_wer"] == 0.0
    assert "code_switch_ratio" in data


@pytest.mark.asyncio
async def test_list_providers_endpoint(client, auth_headers) -> None:
    response = await client.get("/api/v1/providers", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert "local_speech_engines" in data

    provider_ids = [p["id"] for p in data["providers"]]
    assert "wispr_flow" in provider_ids
    assert "gnani_ai" in provider_ids

