# test_api_v1_audio.py
# Offline API tests for the VoxLab 2.0 v1 surface: engines listing, health,
# transcribe (with reference metrics), darwin audio run creation/validation,
# regression listing, and multi-engine benchmark — all against a stub engine
# so no model download or TTS is involved.

from __future__ import annotations

import io
import wave
from typing import Any

import numpy as np
import pytest

from app.speech.base import (
    AudioData,
    EngineCapabilities,
    EngineHealth,
    EngineMetadata,
    SpeechEngine,
    TranscriptionResult,
)

SR = 16000
STUB_TEXT = "hello voxlab world"


class StubAPIEngine(SpeechEngine):
    @classmethod
    def engine_id(cls) -> str:
        return "stub"

    @classmethod
    def is_available(cls) -> bool:
        return True

    async def initialize(self) -> None:
        return None

    async def health_check(self) -> EngineHealth:
        return EngineHealth(status="healthy", detail="stub ok", model_loaded=True)

    async def transcribe(self, audio: AudioData, language: str | None = None) -> TranscriptionResult:
        return TranscriptionResult(
            engine="stub", text=STUB_TEXT, language="en", language_probability=0.9,
            duration_seconds=audio.duration_seconds, processing_time_seconds=0.02,
            metadata={"model": "stub-model"},
        )

    def transcribe_stream(self, audio: AudioData, chunk_seconds: float = 3.0):
        return iter(())

    def get_capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(streaming_mode="none")

    def get_metadata(self) -> EngineMetadata:
        return EngineMetadata(engine_id="stub", display_name="Stub", model="stub-model", device="cpu")

    async def shutdown(self) -> None:
        return None


async def _patch_stub(monkeypatch) -> None:
    async def fake_get_engine(engine_id: str = "whisper_local"):
        return StubAPIEngine()

    import app.api.v1.audio as audio_mod
    import app.api.v1.benchmarks as benchmarks_mod
    import app.api.v1.regressions as regressions_mod

    monkeypatch.setattr(audio_mod, "get_engine", fake_get_engine)
    monkeypatch.setattr(benchmarks_mod, "get_engine", fake_get_engine)
    monkeypatch.setattr(regressions_mod, "get_engine", fake_get_engine)


def _wav_bytes(seconds: float = 0.3) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SR)
        t = np.arange(int(seconds * SR)) / SR
        tone = (0.4 * np.sin(2 * np.pi * 300.0 * t) * 32767).astype("<i2")
        wav.writeframes(tone.tobytes())
    return buf.getvalue()


# --- engines ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engines_listing_has_honest_structure(client, auth_headers, monkeypatch):
    await _patch_stub(monkeypatch)
    response = await client.get("/api/v1/engines", headers=auth_headers)
    assert response.status_code == 200
    engines = response.json()
    assert isinstance(engines, list) and engines
    entry = engines[0]
    assert {"engine_id", "installed"} <= set(entry)


@pytest.mark.asyncio
async def test_engine_health_with_stub(client, auth_headers, monkeypatch):
    await _patch_stub(monkeypatch)
    response = await client.get("/api/v1/engines/stub/health", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["engine_id"] == "stub"


# --- transcribe ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transcribe_without_reference_returns_text_only(client, auth_headers, monkeypatch):
    await _patch_stub(monkeypatch)
    response = await client.post(
        "/api/v1/audio/transcribe",
        headers=auth_headers,
        files={"file": ("clip.wav", _wav_bytes(), "audio/wav")},
        data={"engine_id": "stub"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == STUB_TEXT
    assert body["engine"] == "stub"
    assert body["metrics"] is None


@pytest.mark.asyncio
async def test_transcribe_with_reference_includes_metrics(client, auth_headers, monkeypatch):
    await _patch_stub(monkeypatch)
    response = await client.post(
        "/api/v1/audio/transcribe",
        headers=auth_headers,
        files={"file": ("clip.wav", _wav_bytes(), "audio/wav")},
        data={
            "engine_id": "stub",
            "reference_transcript": "hello voxlab world",
            "entities": "voxlab",
        },
    )
    assert response.status_code == 200
    metrics = response.json()["metrics"]
    assert metrics is not None
    assert metrics["ground_truth"]["wer"] == 0.0
    assert metrics["ground_truth"]["entity_accuracy"] == 1.0
    assert "heuristic" in metrics


@pytest.mark.asyncio
async def test_transcribe_rejects_corrupt_audio(client, auth_headers, monkeypatch):
    await _patch_stub(monkeypatch)
    response = await client.post(
        "/api/v1/audio/transcribe",
        headers=auth_headers,
        files={"file": ("clip.wav", b"not-a-wav-at-all", "audio/wav")},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_transcribe_requires_auth(client):
    response = await client.post(
        "/api/v1/audio/transcribe",
        files={"file": ("clip.wav", _wav_bytes(), "audio/wav")},
    )
    assert response.status_code == 401


# --- darwin audio --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_darwin_audio_personas_listing(client, auth_headers):
    response = await client.get("/api/v1/darwin/audio/personas", headers=auth_headers)
    assert response.status_code == 200
    personas = {p["id"]: p for p in response.json()}
    assert "noisy_environment_speaker" in personas
    assert personas["self_correcting_speaker"]["is_content_persona"] is True


@pytest.mark.asyncio
async def test_darwin_audio_transforms_catalog(client, auth_headers):
    response = await client.get("/api/v1/darwin/audio/transforms", headers=auth_headers)
    assert response.status_code == 200
    catalog = response.json()
    assert len(catalog) >= 14
    assert all("operator" in entry and "params" in entry for entry in catalog)


@pytest.mark.asyncio
async def test_darwin_audio_evolve_validates_personas(client, auth_headers):
    response = await client.post(
        "/api/v1/darwin/audio/evolve",
        headers=auth_headers,
        files={"file": ("seed.wav", _wav_bytes(), "audio/wav")},
        data={
            "reference_transcript": "hello world",
            "personas": "does_not_exist_persona",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_darwin_audio_evolve_accepts_run(client, auth_headers, db_session):
    response = await client.post(
        "/api/v1/darwin/audio/evolve",
        headers=auth_headers,
        files={"file": ("seed.wav", _wav_bytes(), "audio/wav")},
        data={
            "reference_transcript": "hello world",
            "population_size": "2",
            "generations": "1",
            "engine_id": "stub",  # never initialized in this test
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] in {"queued", "running", "completed", "failed"}
    assert body["config"]["reference_transcript"] == "hello world"


@pytest.mark.asyncio
async def test_darwin_audio_runs_listing(client, auth_headers):
    response = await client.get("/api/v1/darwin/audio/runs", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# --- regressions -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regressions_listing_empty(client, auth_headers):
    response = await client.get("/api/v1/regressions", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_regression_replay_unknown_case_404(client, auth_headers, monkeypatch):
    await _patch_stub(monkeypatch)
    response = await client.post("/api/v1/regressions/9999/run", headers=auth_headers)
    assert response.status_code == 404


# --- benchmarks ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_benchmark_with_stub_engine(client, auth_headers, monkeypatch):
    await _patch_stub(monkeypatch)
    from app.speech import registry as registry_mod

    monkeypatch.setattr(registry_mod.engine_registry, "known_engines", lambda: ["stub"])
    monkeypatch.setattr(registry_mod.engine_registry, "is_installed", lambda _eid: True)

    response = await client.post(
        "/api/v1/benchmarks/audio",
        headers=auth_headers,
        files={"file": ("clip.wav", _wav_bytes(), "audio/wav")},
        data={
            "engines": "stub",
            "reference_transcript": "hello voxlab world",
            "label": "unit-test benchmark",
        },
    )
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    assert body["label"] == "unit-test benchmark"
    assert len(body["engine_results"]) == 1
    entry = body["engine_results"][0]
    assert entry["engine"] == "stub"
    assert entry["status"] == "ok"
    assert entry["metrics"]["ground_truth"]["wer"] == 0.0


@pytest.mark.asyncio
async def test_benchmark_unknown_engine_rejected(client, auth_headers, monkeypatch):
    await _patch_stub(monkeypatch)
    response = await client.post(
        "/api/v1/benchmarks/audio",
        headers=auth_headers,
        files={"file": ("clip.wav", _wav_bytes(), "audio/wav")},
        data={"engines": "nonexistent_engine"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_transcribe_with_reference_returns_alignment_and_semantic(
    client, auth_headers, monkeypatch
):
    """Phase 3+4 surfaces ride along on the transcribe response."""
    await _patch_stub(monkeypatch)
    response = await client.post(
        "/api/v1/audio/transcribe",
        headers=auth_headers,
        files={"file": ("clip.wav", _wav_bytes(), "audio/wav")},
        data={
            "reference_transcript": "completely different reference words",
            "entities": "kubernetes",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["alignment"] is not None
    assert body["alignment"]["counts"]["substitutions"] >= 1
    assert body["semantic"] is not None
    assert "meaning_preserved" in body["semantic"]
    # The advisory LLM layer is opt-in: absent unless explicitly requested.
    assert body["llm_judgment"] is None


@pytest.mark.asyncio
async def test_score_transcript_wispr_flow_style(client, auth_headers):
    """Human-in-the-loop scoring: text in, full honest report out — no audio."""
    response = await client.post(
        "/api/v1/audio/score",
        headers=auth_headers,
        json={
            "reference": "Schedule the kubernetes deployment for order 42",
            "hypothesis": "Schedule the cavirnetts demployment for order forty two",
            "label": "wispr-flow-pro-capture",
            "entities": ["kubernetes"],
            "technical_vocab": ["kubernetes", "deployment"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "human_in_the_loop"
    gt = body["metrics"]["ground_truth"]
    assert gt["wer"] > 0  # "cavirnetts demployment" garbled
    assert gt["number_accuracy"] == 1.0  # "42" == "forty two" (expand_numbers)
    assert body["alignment"]["counts"]["substitutions"] >= 1
    assert body["semantic"]["meaning_preserved"] is False
    assert any(e["type"] == "terminology_error" for e in body["semantic"]["errors"])

    assert response.status_code != 500


@pytest.mark.asyncio
async def test_score_transcript_requires_reference(client, auth_headers):
    response = await client.post(
        "/api/v1/audio/score", headers=auth_headers, json={"reference": "", "hypothesis": "x"}
    )
    assert response.status_code == 422
