# test_speech_metrics.py
# Unit tests for the transcription evaluation engine (WER/CER/normalization).
# These metrics are the ground-truth layer of VoxLab 2.0, so the tests pin the
# exact definitions: counts, normalization toggles, and honest N/A behavior.

from __future__ import annotations

import pytest

from app.speech.metrics import (
    NormalizationConfig,
    char_error_rate,
    compute_transcript_metrics,
    normalize_text,
    number_accuracy,
    number_to_words,
    punctuation_accuracy,
    semantic_overlap_proxy,
    timestamp_alignment_error_seconds,
    word_error_rate,
)


# --- WER definition pins -------------------------------------------------------


def test_wer_identical_text_is_zero():
    wer, detail = word_error_rate("hello world", "hello world")
    assert wer == 0.0
    assert detail == {
        "substitutions": 0, "deletions": 0, "insertions": 0,
        "reference_words": 2,
    }


def test_wer_substitution_counts():
    wer, detail = word_error_rate("hello world", "hello there")
    assert wer == pytest.approx(0.5)
    assert detail["substitutions"] == 1


def test_wer_deletion_and_insertion():
    _, detail_del = word_error_rate("hello big world", "hello world")
    assert detail_del["deletions"] == 1
    _, detail_ins = word_error_rate("hello world", "hello big world")
    assert detail_ins["insertions"] == 1
    # WER exceeds 1.0 on insertions (definition, documented)
    wer, _ = word_error_rate("hello", "a b c hello")
    assert wer == 3.0


def test_wer_empty_reference_is_total_or_zero():
    assert word_error_rate("", "some words")[0] == 1.0
    assert word_error_rate("", "")[0] == 0.0


def test_cer_basic_and_empty_reference():
    assert char_error_rate("cat", "cat") == 0.0
    assert char_error_rate("cat", "cap") == pytest.approx(1 / 3)
    assert char_error_rate("", "hi") == 1.0


# --- normalization ---------------------------------------------------------------


def test_number_to_words_basics():
    assert number_to_words(25) == "twenty five"
    assert number_to_words(42) == "forty two"
    assert number_to_words(100) == "one hundred"
    assert number_to_words(2026) == "two thousand twenty six"
    assert number_to_words(2.5) == "two point five"
    assert number_to_words(0) == "zero"


def test_number_normalization_is_configurable_not_automatic():
    config_off = NormalizationConfig()  # expand_numbers defaults False
    config_on = NormalizationConfig(expand_numbers=True)
    # Off: "25" (1 word) vs "twenty five" (2 words) -> 1 sub + 1 ins = 2/2
    wer_off, _ = word_error_rate(
        normalize_text("order 25", config_off),
        normalize_text("order twenty five", config_off),
    )
    assert wer_off == pytest.approx(1.0)
    # On: they are equal
    wer_on, _ = word_error_rate(
        normalize_text("order 25", config_on),
        normalize_text("order twenty five", config_on),
    )
    assert wer_on == 0.0


def test_contractions_expand():
    out = normalize_text("I'm ready, can't stop", NormalizationConfig())
    assert "i am" in out
    assert "cannot" in out


def test_lowercase_and_punctuation_strip():
    out = normalize_text("Hello, World!", NormalizationConfig())
    assert out == "hello world"


def test_unicode_fold():
    out = normalize_text("café naïve", NormalizationConfig())
    assert out == "cafe naive"


# --- component accuracies ----------------------------------------------------------


def test_punctuation_accuracy_detects_missing_comma():
    assert punctuation_accuracy("Hello, world.", "Hello, world.") == 1.0
    acc = punctuation_accuracy("Hello, world.", "Hello world")
    assert acc is not None and acc < 1.0
    # No reference punctuation -> honest N/A
    assert punctuation_accuracy("hello world", "hello world") is None


def test_number_accuracy_matches_words_or_digits():
    # words vs digits
    acc = number_accuracy("order number 42", "order number forty two")
    assert acc == 1.0
    # missing number
    acc2 = number_accuracy("order 42 and 7", "order forty two")
    assert acc2 == 0.5
    # no numbers in reference -> N/A
    assert number_accuracy("no numbers here", "no numbers here") is None


def test_semantic_overlap_proxy_is_heuristic_and_sane():
    same = semantic_overlap_proxy("deploy the kubernetes cluster", "deploy the kubernetes cluster")
    assert same == 1.0
    partial = semantic_overlap_proxy(
        "deploy the kubernetes cluster now", "deploy the kubernetes cluster"
    )
    assert 0.0 < partial < 1.0
    unrelated = semantic_overlap_proxy("deploy kubernetes", "schedule dentist appointment")
    assert unrelated == 0.0


def test_timestamp_alignment_none_without_references():
    assert timestamp_alignment_error_seconds([], [{"start": 0.1}]) is None
    err = timestamp_alignment_error_seconds(
        [{"start": 0.0}, {"start": 2.0}], [{"start": 0.1}, {"start": 2.05}]
    )
    assert err == pytest.approx(0.075, abs=1e-6)


# --- full report ----------------------------------------------------------------------


def test_compute_transcript_metrics_full_report():
    report = compute_transcript_metrics(
        reference="Schedule the kubernetes deployment for order 42, please.",
        hypothesis="Schedule the kubernetes deployment for order 42 please",
        entities=["kubernetes"],
        technical_vocab=["kubernetes", "deployment"],
        reference_language="en",
        hypothesis_language="en",
        processing_time_seconds=0.5,
        audio_duration_seconds=2.0,
    )
    payload = report.to_dict()
    gt = payload["ground_truth"]
    assert gt["wer"] == 0.0  # punctuation-only difference
    assert gt["number_accuracy"] == 1.0
    assert gt["entity_accuracy"] == 1.0
    assert gt["technical_vocab_accuracy"] == 1.0
    assert gt["language_correct"] is True
    assert gt["realtime_factor"] == 0.25
    assert gt["punctuation_accuracy"] is not None and gt["punctuation_accuracy"] < 1.0
    # heuristic layer is separate and labeled
    assert payload["heuristic"]["semantic_overlap_proxy"] == 1.0
    assert "definitions" in payload
    assert payload["normalization"]["strip_punctuation"] is True


def test_compute_transcript_metrics_wer_case():
    report = compute_transcript_metrics(
        reference="the quick brown fox",
        hypothesis="the quick brown dog jumps",
    )
    # 1 substitution (fox->dog) + 1 insertion (jumps) / 4 ref words
    assert report.wer == pytest.approx(0.5)
    assert report.wer_detail["substitutions"] == 1
    assert report.wer_detail["insertions"] == 1


def test_entity_accuracy_none_when_no_entities():
    report = compute_transcript_metrics("hello world", "hello world")
    assert report.entity_accuracy is None
    assert report.technical_vocab_accuracy is None
    assert report.number_accuracy is None
    assert report.language_correct is None  # no languages provided
    assert report.realtime_factor is None  # no timing provided
