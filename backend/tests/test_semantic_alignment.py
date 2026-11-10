# test_semantic_alignment.py
# VoxLab 2.5 Phase 3+4: deterministic semantic error detection and word-level
# alignment. Fully offline; the LLM judge is tested with a stubbed LLMService
# so provenance fields are verified without any network call.

from __future__ import annotations

import pytest

from app.speech.alignment import (
    OP_CORRECT,
    OP_DELETION,
    OP_INSERTION,
    OP_SUBSTITUTION,
    WordTiming,
    align_words,
)
from app.speech.semantic import analyze_semantic_errors
from app.speech.semantic_llm import judge_semantics_with_llm
from app.services.llm import LLMService


# --- word-level alignment (Phase 4) ----------------------------------------------


def test_alignment_identical_text_all_correct():
    result = align_words("deploy the service now", "deploy the service now")
    assert all(t.operation == OP_CORRECT for t in result.tokens)
    assert result.correct == 4 and result.substitutions == 0


def test_alignment_substitution_pins_words():
    result = align_words("deploy version two", "deploy version three")
    subs = [t for t in result.tokens if t.operation == OP_SUBSTITUTION]
    assert len(subs) == 1
    assert subs[0].ref_word == "two" and subs[0].hyp_word == "three"
    assert subs[0].severity == "major"  # content word


def test_alignment_insertion_and_deletion():
    result = align_words("deploy the service", "deploy the big service")
    inserts = [t for t in result.tokens if t.operation == OP_INSERTION]
    assert len(inserts) == 1 and inserts[0].hyp_word == "big"

    result2 = align_words("deploy the big service", "deploy the service")
    deletions = [t for t in result2.tokens if t.operation == OP_DELETION]
    assert len(deletions) == 1 and deletions[0].ref_word == "big"


def test_alignment_is_case_and_punctuation_insensitive():
    result = align_words("Hello, World!", "hello world")
    assert all(t.operation == OP_CORRECT for t in result.tokens)


def test_alignment_attaches_timings_only_when_provided():
    timings = [WordTiming(start_seconds=i * 0.5, end_seconds=i * 0.5 + 0.4) for i in range(3)]
    result = align_words("one two three", "one two three", timings)
    timed = [t for t in result.tokens if t.timing is not None]
    assert len(timed) == 3
    assert timed[0].timing.start_seconds == 0.0

    without = align_words("one two three", "one two three")
    assert all(t.timing is None for t in without.tokens)


def test_alignment_counts_match_metrics_wer():
    from app.speech.metrics import word_error_rate

    ref, hyp = "the quick brown fox", "the fast brown dog jumps"
    result = align_words(ref, hyp)
    _wer, detail = word_error_rate(ref, hyp)
    assert result.substitutions == detail["substitutions"]
    assert result.insertions == detail["insertions"]
    assert result.deletions == detail["deletions"]


# --- semantic intelligence (Phase 3, deterministic) ---------------------------------


def test_semantic_clean_text_preserved():
    analysis = analyze_semantic_errors(
        "Schedule the kubernetes deployment for order forty two",
        "Schedule the kubernetes deployment for order forty two",
    )
    assert analysis.meaning_preserved is True
    assert analysis.error_count == 0


def test_semantic_number_error_is_critical():
    analysis = analyze_semantic_errors("deploy version two", "deploy version three")
    types = [e.error_type for e in analysis.errors]
    assert "number_error" in types
    assert any(e.severity == "critical" for e in analysis.errors)
    assert analysis.meaning_preserved is False


def test_semantic_digit_vs_words_not_flagged():
    # "two" and "2" are the same quantity — no number error
    analysis = analyze_semantic_errors("deploy version 2", "deploy version two")
    assert not any(e.error_type == "number_error" for e in analysis.errors)


def test_semantic_negation_error():
    analysis = analyze_semantic_errors("do not restart the server", "do now restart the server")
    assert any(e.error_type == "negation_error" for e in analysis.errors)
    assert analysis.meaning_preserved is False


def test_semantic_date_error():
    analysis = analyze_semantic_errors(
        "deploy on monday to staging", "deploy on sunday to staging"
    )
    assert any(e.error_type == "date_error" for e in analysis.errors)


def test_semantic_missing_instruction():
    analysis = analyze_semantic_errors(
        "schedule the deployment for friday", "the deployment for friday"
    )
    assert any(e.error_type == "missing_instruction" for e in analysis.errors)


def test_semantic_entity_and_terminology():
    analysis = analyze_semantic_errors(
        "push the kubernetes config to voxlab",
        "push the cubernetes config to vox lab",
        entities=["voxlab"],
        technical_vocab=["kubernetes"],
    )
    types = [e.error_type for e in analysis.errors]
    assert "entity_error" in types or "terminology_error" in types


def test_semantic_intent_change():
    analysis = analyze_semantic_errors(
        "can you deploy the service", "you deployed the service"
    )
    assert any(e.error_type == "intent_change" for e in analysis.errors)


def test_semantic_is_deterministic():
    a = analyze_semantic_errors("order forty two ships on friday", "order fifteen ships on friday")
    b = analyze_semantic_errors("order forty two ships on friday", "order fifteen ships on friday")
    assert a.to_dict() == b.to_dict()


def test_semantic_includes_alignment_result():
    analysis = analyze_semantic_errors("hello world", "hello there")
    assert analysis.alignment is not None
    assert analysis.alignment.substitutions >= 1


# --- LLM judgment layer provenance (stubbed LLM, no network) --------------------------


class StubLLM(LLMService):
    def __init__(self, raw_output):
        # skip LLMService.__init__ entirely: no client, no network
        self.model = "stub-model-1"
        self._raw = raw_output

    @property
    def available(self) -> bool:
        return True

    async def complete(self, messages, json_mode=False, max_tokens=700, temperature=0.2):
        return self._raw


@pytest.mark.asyncio
async def test_llm_judgment_full_provenance():
    raw_output = (
        '{"meaning_preserved": false, "confidence": 0.8, "errors": '
        '[{"type": "number_error", "description": "quantity changed", '
        '"reference_text": "two", "hypothesis_text": "three"}]}'
    )
    judgment = await judge_semantics_with_llm(
        StubLLM(raw_output), "deploy version two", "deploy version three"
    )
    body = judgment.to_dict()
    assert body["layer"] == "llm"  # never confusable with ground truth
    assert body["available"] is True
    assert body["meaning_preserved"] is False
    assert body["confidence"] == 0.8
    prov = body["provenance"]
    assert prov["model"] == "stub-model-1"
    assert prov["prompt_version"] == "v1"
    assert prov["temperature"] == 0.0
    assert prov["input_reference"] == "deploy version two"
    assert prov["input_hypothesis"] == "deploy version three"
    assert prov["raw_output"] == raw_output
    assert "evaluated_at" in prov and "prompt_hash" in prov
    assert "advisory" in prov["note"]


@pytest.mark.asyncio
async def test_llm_judgment_unavailable_without_key():
    judgment = await judge_semantics_with_llm(
        LLMService(api_key=""), "reference", "hypothesis"
    )
    assert judgment.available is False
    assert judgment.meaning_preserved is None
    assert judgment.provenance["reason"] == "no_llm_key"


@pytest.mark.asyncio
async def test_llm_judgment_invalid_json_reports_honestly():
    judgment = await judge_semantics_with_llm(
        StubLLM("this is not json at all"), "a", "b"
    )
    assert judgment.available is True
    assert judgment.meaning_preserved is None
    assert judgment.provenance["parse_status"] == "invalid_json"  # model spoke, output was not JSON


@pytest.mark.asyncio
async def test_llm_judgment_out_of_range_confidence_is_null():
    raw_output = '{"meaning_preserved": true, "confidence": 7.5, "errors": []}'
    judgment = await judge_semantics_with_llm(StubLLM(raw_output), "a", "a")
    assert judgment.confidence is None  # never guessed, never clamped silently
