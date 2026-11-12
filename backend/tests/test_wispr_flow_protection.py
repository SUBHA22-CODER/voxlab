# test_wispr_flow_protection.py
# Mandatory Phase 10: Rigorous regression protection suite for Wispr Flow.
# Ensures Gnani AI integration introduces ZERO side-effects or regressions into Wispr Flow.

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.darwin.personas import get_persona
from app.speech.metrics import compute_transcript_metrics, NormalizationConfig
from app.speech.alignment import align_words
from app.speech.semantic import analyze_semantic_errors
from app.speech.registry import engine_registry


def test_wispr_flow_cleaner_personas_remain_intact() -> None:
    """Verify original Wispr Flow dictation personas are untouched."""
    self_corrector = get_persona("self_corrector")
    assert self_corrector.is_dictation_focused is True
    assert "rapidly changes mind" in self_corrector.description.lower()
    assert any("4821" in h for h in self_corrector.heuristic_bank)

    filler_rambler = get_persona("filler_heavy_rambler")
    assert filler_rambler.is_dictation_focused is True
    assert "verbal crutches" in filler_rambler.system_prompt.lower()

    homophone = get_persona("homophone_confuser")
    assert homophone.is_dictation_focused is True


def test_wispr_flow_transcript_scoring_uncompromised() -> None:
    """Verify Wispr Flow deterministic ground truth scoring runs with zero external dependencies."""
    ref = "Schedule the kubernetes deployment for order 42"
    hyp = "Schedule the cavirnetts demployment for order forty two"

    metrics = compute_transcript_metrics(
        ref,
        hyp,
        entities=["kubernetes"],
        technical_vocab=["kubernetes", "deployment"],
        normalization=NormalizationConfig(expand_numbers=True),
    )

    assert metrics.wer > 0.0
    assert metrics.number_accuracy == 1.0  # Canonical number expansion preserved
    assert metrics.entity_accuracy == 0.0  # 'cavirnetts' failed 'kubernetes'

    alignment = align_words(ref, hyp)
    assert alignment.substitutions >= 1

    semantic = analyze_semantic_errors(
        ref, hyp, entities=["kubernetes"], technical_vocab=["kubernetes"]
    )
    assert semantic.meaning_preserved is False
    assert any(e.error_type == "terminology_error" for e in semantic.errors)
    assert any(e.error_type == "entity_error" for e in semantic.errors)


@pytest.mark.asyncio
async def test_wispr_flow_api_scoring_endpoint(client, auth_headers) -> None:
    """Ensure /api/v1/audio/score endpoint responds properly without Gnani dependencies."""
    response = await client.post(
        "/api/v1/audio/score",
        headers=auth_headers,
        json={
            "reference": "Cancel my booking for order forty two immediately",
            "hypothesis": "Cancel my booking for order 42 immediately",
            "label": "wispr-flow-baseline-check",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "human_in_the_loop"
    assert data["metrics"]["ground_truth"]["wer"] == 0.0  # 42 == forty two


def test_engine_registry_contains_local_engines_when_gnani_disabled() -> None:
    """Verify Whisper, Vosk, and Wav2Vec2 remain registered even when Gnani is disabled."""
    known = engine_registry.known_engines()
    assert "whisper_local" in known
    assert "vosk" in known
    assert "wav2vec2" in known
    assert "gnani_prisma" in known

    # When GNANI_ENABLED is false, gnani_prisma reports installed=False honestly
    settings = get_settings()
    if not settings.gnani_enabled:
        assert engine_registry.is_installed("gnani_prisma") is False
        hint = engine_registry.install_hint("gnani_prisma")
        assert "GNANI_ENABLED=true" in hint
