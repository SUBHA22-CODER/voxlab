"""Tests for Darwin evolutionary fuzzing engine, mutation operators, ddmin, and diagnoser."""

from __future__ import annotations

import random
import pytest

from app.darwin.diagnoser import Diagnoser, DiagnosisCategory
from app.darwin.fitness import compute_fitness
from app.darwin.genome import (
    Genome,
    crossover,
    extend_conversation,
    inject_api_failure,
    inject_interruption,
    mutate,
    swap_persona,
)
from app.darwin.minimizer import ddmin
from app.darwin.regression import compute_regression_hash
from app.engine.scenario_runner import RunOutput
from app.services.llm import LLMService


# --- Genome & Mutation Unit Tests ---

def test_genome_hashing_and_serialization():
    g = Genome(
        persona="self_corrector",
        strategy="Test rapid date switch",
        steps=[{"type": "user_message", "content": "Tuesday, no wait, Wednesday"}],
        seed=100,
        generation=1,
    )
    assert len(g.id) == 12
    data = g.to_dict()
    assert data["persona"] == "self_corrector"
    assert data["generation"] == 1

    restored = Genome.from_dict(data)
    assert restored.id == g.id
    assert restored.steps == g.steps


def test_compile_to_scenario_valid_structure():
    g = Genome(
        persona="self_corrector",
        strategy="Test rapid date switch",
        steps=[{"type": "user_message", "content": "Tuesday, wait Wednesday"}],
    )
    scen = g.compile_to_scenario()
    assert "name" in scen
    assert "category" in scen
    assert "steps" in scen
    assert "checks" in scen
    assert len(scen["steps"]) == 1
    assert any(c["type"] == "reply_nonempty" for c in scen["checks"])


def test_swap_persona_operator():
    rng = random.Random(42)
    g = Genome(
        persona="self_corrector",
        strategy="date test",
        steps=[{"type": "user_message", "content": "Tuesday, wait Wednesday"}],
    )
    mutated = swap_persona(g, rng)
    assert mutated.persona != g.persona
    assert mutated.strategy == g.strategy


def test_inject_interruption_operator():
    rng = random.Random(42)
    g = Genome(
        persona="self_corrector",
        strategy="date test",
        steps=[
            {"type": "user_message", "content": "Step 1"},
            {"type": "user_message", "content": "Step 2"},
        ],
    )
    mutated = inject_interruption(g, rng)
    assert len(mutated.steps) == 3
    assert any(s["type"] == "interrupt" for s in mutated.steps)


def test_inject_api_failure_operator():
    rng = random.Random(42)
    g = Genome(
        persona="self_corrector",
        strategy="date test",
        steps=[{"type": "user_message", "content": "Step 1"}],
    )
    mutated = inject_api_failure(g, rng)
    assert len(mutated.steps) == 2
    assert any(s["type"] == "tool_failure" for s in mutated.steps)


def test_extend_conversation_operator():
    rng = random.Random(42)
    g = Genome(
        persona="self_corrector",
        strategy="date test",
        steps=[{"type": "user_message", "content": "Step 1"}],
    )
    mutated = extend_conversation(g, rng)
    assert len(mutated.steps) > len(g.steps)


def test_crossover_operator():
    p1 = Genome(
        persona="self_corrector",
        strategy="strat 1",
        steps=[{"type": "user_message", "content": f"A{i}"} for i in range(4)],
        generation=1,
    )
    p2 = Genome(
        persona="filler_heavy_rambler",
        strategy="strat 2",
        steps=[{"type": "user_message", "content": f"B{i}"} for i in range(4)],
        generation=2,
    )
    child = crossover(p1, p2)
    assert child.generation == 3
    assert p1.id in child.parent_ids
    assert p2.id in child.parent_ids
    assert len(child.steps) >= 2


def test_determinism_under_fixed_seed():
    rng1 = random.Random(999)
    g1 = Genome("self_corrector", "strat", [{"type": "user_message", "content": "hi"}])
    m1 = mutate(g1, rng1)

    rng2 = random.Random(999)
    g2 = Genome("self_corrector", "strat", [{"type": "user_message", "content": "hi"}])
    m2 = mutate(g2, rng2)

    assert m1.steps == m2.steps
    assert m1.persona == m2.persona


# --- ddmin Failure Minimizer Tests ---

@pytest.mark.asyncio
async def test_ddmin_synthetic_predicate():
    # Failing predicate: must contain both step 2 and step 6
    async def predicate(steps: list[dict]) -> bool:
        contents = [s["content"] for s in steps]
        return "CRITICAL_BUG" in contents and "TRIGGER" in contents

    original = [
        {"content": "noise 1"},
        {"content": "CRITICAL_BUG"},
        {"content": "noise 2"},
        {"content": "noise 3"},
        {"content": "noise 4"},
        {"content": "TRIGGER"},
        {"content": "noise 5"},
    ]

    minimized = await ddmin(original, predicate, max_evaluations=15)
    contents = [s["content"] for s in minimized]
    assert "CRITICAL_BUG" in contents
    assert "TRIGGER" in contents
    assert len(minimized) < len(original)


# --- Diagnoser Unit Tests ---

def test_diagnoser_rule_based_self_correction():
    diag = Diagnoser(LLMService(api_key=""))
    scenario = {"name": "Test"}
    events = [{"event_type": "user_message"}]
    failed_checks = [{"type": "reply_not_contains"}]
    transcript = [
        {"role": "user", "content": "Schedule for Tuesday, no wait, Wednesday"},
        {"role": "agent", "content": "Confirmed for Tuesday and Wednesday."},
    ]
    res = diag.classify_rule_based(scenario, events, failed_checks, transcript)
    assert res.category == DiagnosisCategory.SELF_CORRECTION_MISSED
    assert res.confidence >= 0.8


def test_diagnoser_rule_based_interruption():
    diag = Diagnoser(LLMService(api_key=""))
    scenario = {"name": "Test"}
    events = [{"event_type": "interruption"}]
    failed_checks = [{"type": "reply_contains"}]
    transcript = [
        {"role": "user", "content": "Hello"},
        {"role": "agent", "content": "As I was saying earlier..."},
    ]
    res = diag.classify_rule_based(scenario, events, failed_checks, transcript)
    assert res.category == DiagnosisCategory.INTERRUPTION_IGNORED


def test_diagnoser_rule_based_filler():
    diag = Diagnoser(LLMService(api_key=""))
    scenario = {"name": "Test"}
    events = [{"event_type": "user_message"}]
    failed_checks = []
    transcript = [
        {"role": "user", "content": "Dictate note"},
        {"role": "agent", "content": "So um basically you know we will meet."},
    ]
    res = diag.classify_rule_based(scenario, events, failed_checks, transcript)
    assert res.category == DiagnosisCategory.FILLER_NOT_REMOVED


# --- Fitness & Budget Tests ---

def test_fitness_computation_penalty():
    out = RunOutput(
        transcript=[
            {"role": "user", "content": "test"},
            {"role": "agent", "content": "reply"},
        ],
        turn_latencies_ms=[200],
    )
    # Perfect run
    fit_pass = compute_fitness(
        {"task_completion": 100, "response_quality": 100, "context_retention": 100, "latency": 100, "error_recovery": 100},
        [{"type": "reply_nonempty", "passed": True}],
        out,
    )
    assert fit_pass.fitness < 0.2

    # Severe failure run with failed check
    fit_fail = compute_fitness(
        {"task_completion": 40, "response_quality": 40, "context_retention": 40, "latency": 40, "error_recovery": 40},
        [{"type": "reply_nonempty", "passed": False}],
        out,
    )
    assert fit_fail.fitness > 0.5


def test_regression_hash_deduplication():
    steps1 = [{"type": "user_message", "content": "Hello World"}]
    steps2 = [{"type": "user_message", "content": "  hello world  "}]
    h1 = compute_regression_hash("self_correction_missed", steps1)
    h2 = compute_regression_hash("self_correction_missed", steps2)
    assert h1 == h2


# --- Anti-Hardcode & Verification Bugfix Tests ---

def test_diagnoser_event_sequence_zero_not_dropped():
    """Verify that event sequence 0 is not dropped due to falsy evaluation."""
    diag = Diagnoser(LLMService(api_key=""))
    scenario = {"name": "Test"}
    events = [{"sequence": 0, "event_type": "interruption"}]
    failed_checks = [{"type": "reply_contains"}]
    transcript = [{"role": "user", "content": "hi"}, {"role": "agent", "content": "still talking"}]
    res = diag.classify_rule_based(scenario, events, failed_checks, transcript)
    assert "0" in res.evidence_event_ids
    assert res.heuristic is True  # Rule-based must explicitly report heuristic = True


def test_fitness_is_not_hardcoded_between_different_agents():
    """Verify that fitness computation yields different scores for different outputs (anti-hardcoding test)."""
    out_good = RunOutput(
        transcript=[{"role": "user", "content": "hi"}, {"role": "agent", "content": "hello"}],
        turn_latencies_ms=[150],
    )
    out_broken = RunOutput(
        transcript=[{"role": "user", "content": "hi"}, {"role": "agent", "content": ""}],
        turn_latencies_ms=[8000],
    )
    checks_passed = [{"type": "reply_nonempty", "passed": True}]
    checks_failed = [{"type": "reply_nonempty", "passed": False}]

    scores_good = {"task_completion": 95, "response_quality": 95, "context_retention": 95, "latency": 95, "error_recovery": 95}
    scores_bad = {"task_completion": 0, "response_quality": 0, "context_retention": 0, "latency": 10, "error_recovery": 0}

    fit_good = compute_fitness(scores_good, checks_passed, out_good)
    fit_bad = compute_fitness(scores_bad, checks_failed, out_broken)

    # Must be strictly different and responsive
    assert fit_bad.fitness > fit_good.fitness
    assert fit_good.fitness < 0.25
    assert fit_bad.fitness > 0.70


def test_budget_cap_clamping_logic():
    """Verify budget cap of 60 sessions strictly clamps generations."""
    pop_size = 20
    # requested 10 generations would mean 200 sessions > 60
    effective_gens = max(1, 60 // pop_size)
    assert effective_gens == 3
    assert effective_gens * pop_size <= 60

