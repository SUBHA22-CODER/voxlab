# test_darwin_audio_genome.py
# TDD unit tests for the Darwin audio genome and fitness layers. Written
# BEFORE the implementation (tdd-workflow). All offline: synthetic audio,
# no model, no TTS — content mutation is tested as a pure text function.

from __future__ import annotations

import numpy as np
import pytest

from app.darwin_audio.fitness import (
    AUDIO_FITNESS_WEIGHTS,
    AudioFitness,
    compute_audio_fitness,
)
from app.darwin_audio.genome import (
    AudioGenome,
    MaterializedGenome,
    build_random_genome,
    crossover_genomes,
    mutate_genome,
)
from app.darwin_audio.personas import AUDIO_PERSONAS
from app.speech.exceptions import TransformError
from app.speech.metrics import NormalizationConfig
from app.speech.transforms import TransformSpec, apply_chain, list_transforms

SR = 16000


def _tone(seconds: float = 1.0, freq: float = 220.0) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


# --- transform registry -----------------------------------------------------------


def test_all_documented_transforms_are_registered_and_listed():
    catalog = list_transforms()
    names = {entry["operator"] for entry in catalog}
    expected = {
        "add_background_noise", "add_typing_clicks", "add_fan_hum",
        "change_volume", "clip_speech", "insert_silence", "dropout_spans",
        "tape_speed_change", "pitch_shift", "telephony_bandpass",
        "lowpass_muffle", "add_echo", "fade_edges", "volume_pump",
    }
    assert expected <= names
    for entry in catalog:
        assert "params" in entry


def test_every_persona_preset_uses_registered_operators():
    for persona in AUDIO_PERSONAS.values():
        for spec in persona.preset:
            assert spec.operator in {e["operator"] for e in list_transforms()}, persona.id


def test_transforms_are_deterministic_for_same_seed():
    tone = _tone()
    spec = TransformSpec(
        operator="add_background_noise", params={"snr_db": 10.0, "noise_type": "white"}, seed=7
    )
    out_a = apply_chain(tone, SR, [spec])
    out_b = apply_chain(tone, SR, [spec])
    assert np.array_equal(out_a, out_b)


def test_different_seeds_diverge():
    tone = _tone()
    spec_a = TransformSpec(operator="add_typing_clicks", params={"click_count": 6}, seed=1)
    spec_b = TransformSpec(operator="add_typing_clicks", params={"click_count": 6}, seed=2)
    assert not np.array_equal(
        apply_chain(tone, SR, [spec_a]), apply_chain(tone, SR, [spec_b])
    )


def test_out_of_bounds_params_rejected():
    spec = TransformSpec(operator="change_volume", params={"gain_db": 99.0}, seed=1)
    with pytest.raises(TransformError, match="outside bounds"):
        apply_chain(_tone(0.1), SR, [spec])


def test_unknown_operator_rejected():
    spec = TransformSpec(operator="does_not_exist", seed=1)
    with pytest.raises(TransformError, match="Unknown transform"):
        apply_chain(_tone(0.1), SR, [spec])


def test_input_array_never_mutated():
    tone = _tone()
    original = tone.copy()
    apply_chain(
        tone,
        SR,
        [TransformSpec(operator="add_background_noise", params={"snr_db": 5}, seed=3)],
    )
    assert np.array_equal(tone, original)


def test_transform_spec_roundtrip_serialization():
    spec = TransformSpec(operator="add_echo", params={"delay_ms": 150.0, "decay": 0.3}, seed=9)
    revived = TransformSpec.from_dict(spec.to_dict())
    assert revived == spec


# --- genome ------------------------------------------------------------------------


def test_build_random_genome_is_deterministic():
    ga = build_random_genome(
        persona=AUDIO_PERSONAS["noisy_environment_speaker"],
        seed_audio_ref="seed.wav",
        reference_text="deploy the service",
        seed=42,
        generation=0,
    )
    gb = build_random_genome(
        persona=AUDIO_PERSONAS["noisy_environment_speaker"],
        seed_audio_ref="seed.wav",
        reference_text="deploy the service",
        seed=42,
        generation=0,
    )
    assert ga.genome_id == gb.genome_id
    assert ga.transform_chain == gb.transform_chain


def test_genome_ids_differ_across_personas():
    ga = build_random_genome(
        persona=AUDIO_PERSONAS["noisy_environment_speaker"],
        seed_audio_ref="seed.wav", reference_text="x", seed=42, generation=0,
    )
    gb = build_random_genome(
        persona=AUDIO_PERSONAS["fast_technical_speaker"],
        seed_audio_ref="seed.wav", reference_text="x", seed=42, generation=0,
    )
    assert ga.genome_id != gb.genome_id


async def test_genome_materialize_applies_chain_without_tts():
    genome = build_random_genome(
        persona=AUDIO_PERSONAS["noisy_environment_speaker"],
        seed_audio_ref="seed.wav",
        reference_text="hello world",
        seed=5,
        generation=0,
    )
    # No TTS available in tests -> audio personas fall back to transforming
    # the provided seed audio; effective reference stays the original.
    materialized = await genome.materialize(seed_audio=_tone(0.8), sample_rate=SR, tts_synth=None)
    assert isinstance(materialized, MaterializedGenome)
    assert materialized.effective_reference == "hello world"
    assert materialized.source == "seed_audio"
    assert materialized.samples.dtype == np.float32
    assert materialized.samples.size > 0


def test_genome_serialization_roundtrip():
    genome = build_random_genome(
        persona=AUDIO_PERSONAS["fast_technical_speaker"],
        seed_audio_ref="seed.wav", reference_text="order forty two", seed=11, generation=2,
    )
    payload = genome.to_dict()
    revived = AudioGenome.from_dict(payload)
    assert revived.genome_id == genome.genome_id
    assert revived.transform_chain == genome.transform_chain
    assert revived.persona_id == genome.persona_id


# --- mutation & crossover ------------------------------------------------------------


def test_mutate_produces_child_with_lineage():
    parent = build_random_genome(
        persona=AUDIO_PERSONAS["noisy_environment_speaker"],
        seed_audio_ref="seed.wav", reference_text="hello", seed=3, generation=0,
    )
    child = mutate_genome(parent, mutation_seed=77)
    assert child.generation == parent.generation + 1
    assert parent.genome_id in child.parent_ids
    # Reproducible: same mutation seed -> same child
    child_again = mutate_genome(parent, mutation_seed=77)
    assert child.genome_id == child_again.genome_id


def test_crossover_mixes_parent_chains():
    pa = build_random_genome(
        persona=AUDIO_PERSONAS["noisy_environment_speaker"],
        seed_audio_ref="s.wav", reference_text="a", seed=1, generation=1,
    )
    pb = build_random_genome(
        persona=AUDIO_PERSONAS["fast_technical_speaker"],
        seed_audio_ref="s.wav", reference_text="a", seed=2, generation=1,
    )
    child = crossover_genomes(pa, pb, seed=5)
    assert child.generation == 2
    assert pa.genome_id in child.parent_ids and pb.genome_id in child.parent_ids
    assert child.persona_id in (pa.persona_id, pb.persona_id)


# --- fitness ---------------------------------------------------------------------------


def test_fitness_weights_sum_to_one():
    assert pytest.approx(sum(AUDIO_FITNESS_WEIGHTS.values())) == 1.0


def test_perfect_transcription_scores_zero_failure():
    metrics = compute_audio_fitness(
        wer=0.0, cer=0.0, number_accuracy=1.0, entity_accuracy=1.0,
        semantic_overlap=1.0, audio_rms=0.2, seed_duration=2.0,
        candidate_duration=2.0,
    )
    assert isinstance(metrics, AudioFitness)
    assert metrics.failure_score == pytest.approx(0.0)
    assert metrics.valid is True
    assert metrics.gates["audible"] and metrics.gates["duration_preserved"]


def test_total_failure_scores_one():
    metrics = compute_audio_fitness(
        wer=1.0, cer=1.0, number_accuracy=0.0, entity_accuracy=0.0,
        semantic_overlap=0.0, audio_rms=0.2, seed_duration=2.0,
        candidate_duration=2.0,
    )
    assert metrics.failure_score == pytest.approx(1.0)


def test_silent_audio_is_invalid_not_rewarded():
    metrics = compute_audio_fitness(
        wer=1.0, cer=1.0, number_accuracy=0.0, entity_accuracy=0.0,
        semantic_overlap=0.0, audio_rms=0.0, seed_duration=2.0,
        candidate_duration=2.0,
    )
    assert metrics.valid is False
    assert metrics.gates["audible"] is False
    assert metrics.rewarded_score == 0.0


def test_duration_blown_away_is_invalid():
    metrics = compute_audio_fitness(
        wer=0.8, cer=0.5, number_accuracy=None, entity_accuracy=None,
        semantic_overlap=0.4, audio_rms=0.2, seed_duration=2.0,
        candidate_duration=10.0,
    )
    assert metrics.valid is False
    assert metrics.gates["duration_preserved"] is False


def test_missing_optional_components_redistribute_nothing():
    # number/entity accuracy N/A -> treated as no-signal (0 failure credit),
    # but the score stays within [0, 1]
    metrics = compute_audio_fitness(
        wer=0.5, cer=0.25, number_accuracy=None, entity_accuracy=None,
        semantic_overlap=0.8, audio_rms=0.2, seed_duration=2.0,
        candidate_duration=2.1,
    )
    assert 0.0 <= metrics.failure_score <= 1.0
    assert metrics.valid is True


def test_metrics_use_configurable_normalization_flag_pass_through():
    from app.speech.metrics import compute_transcript_metrics

    report = compute_transcript_metrics(
        reference="order 25", hypothesis="order twenty five",
        normalization=NormalizationConfig(expand_numbers=True),
    )
    assert report.wer == 0.0
