"""Tests for deterministic checks, heuristic scoring, and LLM-judge fallback."""

import pytest

from app.engine.evaluation_engine import EvaluationEngine
from app.engine.scenario_runner import RunOutput
from app.services.llm import LLMService


def make_output(**overrides) -> RunOutput:
    base = dict(
        transcript=[
            {"role": "user", "content": "check my order", "turn": 1, "kind": "user_message"},
            {"role": "agent", "content": "Your order is shipped.", "turn": 1, "latency_ms": 300},
        ],
        tool_calls=[{"turn": 1, "name": "check_order_status", "status": "success", "duration_ms": 40}],
        final_state={"turns": 1},
        turn_latencies_ms=[300],
        injected_tool_failures=0,
        error_turns=[],
        agent_error=None,
    )
    base.update(overrides)
    return RunOutput(**base)


def make_engine() -> EvaluationEngine:
    return EvaluationEngine(LLMService(api_key=""), default_latency_budget_ms=1000)


class TestDeterministicChecks:
    async def test_tool_called_passes_when_present(self):
        engine = make_engine()
        checks = engine._deterministic_checks(
            {"checks": [{"type": "tool_called", "name": "check_order_status"}]}, make_output()
        )
        assert checks[0]["passed"] is True

    async def test_tool_called_fails_when_missing(self):
        engine = make_engine()
        checks = engine._deterministic_checks(
            {"checks": [{"type": "tool_called", "name": "cancel_order"}]}, make_output()
        )
        assert checks[0]["passed"] is False

    async def test_reply_contains_any_of(self):
        engine = make_engine()
        checks = engine._deterministic_checks(
            {"checks": [{"type": "reply_contains", "any_of": ["shipped", "lost"]}]}, make_output()
        )
        assert checks[0]["passed"] is True

    async def test_reply_not_contains_detects_failure_text(self):
        engine = make_engine()
        output = make_output(
            transcript=[
                {"role": "user", "content": "hi", "turn": 1, "kind": "user_message"},
                {"role": "agent", "content": "I can only understand English.", "turn": 1, "latency_ms": 100},
            ]
        )
        checks = engine._deterministic_checks(
            {"checks": [{"type": "reply_not_contains", "any_of": ["only understand english"]}]}, output
        )
        assert checks[0]["passed"] is False

    async def test_latency_under_fails_on_slow_turn(self):
        engine = make_engine()
        output = make_output(turn_latencies_ms=[300, 9000])
        checks = engine._deterministic_checks(
            {"checks": [{"type": "latency_under", "ms": 1000, "per_turn": True}]}, output
        )
        assert checks[0]["passed"] is False

    async def test_state_equals(self):
        engine = make_engine()
        checks = engine._deterministic_checks(
            {"checks": [{"type": "state_equals", "key": "turns", "value": 1}]}, make_output()
        )
        assert checks[0]["passed"] is True

    async def test_transcript_similarity_check(self):
        engine = make_engine()
        output = make_output(
            transcript=[
                {"role": "user", "content": "Mera order kab aayega? Order ID hai", "turn": 1, "kind": "user_message"},
            ]
        )
        checks = engine._deterministic_checks(
            {
                "checks": [
                    {"type": "transcript_similarity", "expected": "mera order kab aayega", "min_ratio": 0.6},
                    {"type": "transcript_similarity", "expected": "completely different sentence here", "min_ratio": 0.95},
                ]
            },
            output,
        )
        assert checks[0]["passed"] is True
        assert checks[1]["passed"] is False

    async def test_task_completion_math(self):
        engine = make_engine()
        checks = [
            {"type": "a", "passed": True, "detail": "", "params": {}},
            {"type": "b", "passed": True, "detail": "", "params": {}},
            {"type": "c", "passed": False, "detail": "", "params": {}},
        ]
        assert engine._task_completion(checks, make_output()) == pytest.approx(66.67, abs=0.01)


class TestScores:
    async def test_latency_score_is_budget_over_actual(self):
        engine = make_engine()  # budget 1000ms
        output = make_output(turn_latencies_ms=[1000, 2000])
        # min(100, 100*1000/1000)=100, min(100, 100*1000/2000)=50 → mean 75
        assert engine._latency_score(output, 1000) == 75.0

    async def test_error_recovery_zero_on_agent_error(self):
        engine = make_engine()
        output = make_output(injected_tool_failures=1, error_turns=[1], agent_error="mock_api_failure")
        assert engine._error_recovery(output, {}) == 0.0

    async def test_error_recovery_full_on_graceful_reply(self):
        engine = make_engine()
        output = make_output(injected_tool_failures=1)
        assert engine._error_recovery(output, {}) == 100.0

    async def test_heuristic_quality_penalizes_empty_and_repetition(self):
        engine = make_engine()
        clean = make_output()
        dirty = make_output(
            transcript=[
                {"role": "user", "content": "a", "turn": 1, "kind": "user_message"},
                {"role": "agent", "content": "", "turn": 1, "latency_ms": 10},
            ],
            error_turns=[1],
        )
        assert engine._heuristic_quality(dirty) < engine._heuristic_quality(clean)

    async def test_heuristic_context_penalizes_repeated_clarification(self):
        engine = make_engine()
        fumbling = make_output(
            transcript=[
                {"role": "user", "content": "check my order", "turn": 1, "kind": "user_message"},
                {"role": "agent", "content": "Could you share your order ID?", "turn": 1, "latency_ms": 100},
                {"role": "user", "content": "it's ORD-1001", "turn": 2, "kind": "user_message"},
                {"role": "agent", "content": "Which order is it? Could you share the order ID?", "turn": 2, "latency_ms": 100},
            ]
        )
        healthy = make_output()
        assert engine._heuristic_context(fumbling) < engine._heuristic_context(healthy)

    async def test_heuristic_context_ignores_polite_offers(self):
        engine = make_engine()
        offer_twice = make_output(
            transcript=[
                {"role": "user", "content": "a", "turn": 1, "kind": "user_message"},
                {"role": "agent", "content": "Your order is shipped. Anything else I can help with?", "turn": 1, "latency_ms": 100},
                {"role": "user", "content": "b", "turn": 2, "kind": "user_message"},
                {"role": "agent", "content": "Your order is shipped. Anything else I can help with?", "turn": 2, "latency_ms": 100},
            ]
        )
        assert engine._heuristic_context(offer_twice) == 85.0

    async def test_full_evaluation_uses_heuristic_mode_without_llm(self):
        engine = make_engine()
        assert engine.llm.available is False
        scores, feedback = await engine.evaluate(
            {
                "name": "t",
                "category": "conversation",
                "expected_behavior": "replies",
                "checks": [{"type": "reply_nonempty", "turn": -1}],
            },
            make_output(),
        )
        assert feedback["judge"]["mode"] == "heuristic"
        assert 0 <= scores["task_completion"] <= 100
        assert 0 <= scores["response_quality"] <= 100
        assert 0 <= scores["context_retention"] <= 100
        assert 0 <= scores["latency"] <= 100
        assert 0 <= scores["error_recovery"] <= 100
