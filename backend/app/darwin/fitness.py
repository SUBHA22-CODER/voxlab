"""Darwin Fitness & Wispr Flow Dictation Evaluation Metrics."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.engine.scenario_runner import RunOutput


@dataclass
class FitnessResult:
    fitness: float  # 0.0 (agent perfect) to 1.0 (agent totally broken)
    overall_score: float  # 0.0 to 100.0 from evaluation engine
    component_scores: dict[str, float] = field(default_factory=dict)
    dictation_scores: dict[str, float] = field(default_factory=dict)
    failed_checks: list[dict[str, Any]] = field(default_factory=list)
    passed_checks: list[dict[str, Any]] = field(default_factory=list)
    heuristic: bool = True
    agent_error: str | None = None


def compute_fitness(
    evaluation_scores: dict[str, Any],
    deterministic_checks: list[dict[str, Any]],
    run_output: RunOutput,
    persona_id: str = "",
) -> FitnessResult:
    """
    Computes Darwin fitness from VoxLab evaluation scores and deterministic checks.
    Higher fitness = more severe attack impact on the agent.
    """
    # Base component scores (T, Q, R, L, E)
    t = float(evaluation_scores.get("task_completion", 80.0))
    q = float(evaluation_scores.get("response_quality", 80.0))
    r = float(evaluation_scores.get("context_retention", 80.0))
    l = float(evaluation_scores.get("latency", 80.0))
    e = float(evaluation_scores.get("error_recovery", 80.0))

    base_score = 0.30 * t + 0.25 * q + 0.20 * r + 0.15 * l + 0.10 * e

    failed_checks: list[dict[str, Any]] = []
    passed_checks: list[dict[str, Any]] = []
    for c in deterministic_checks:
        if c.get("passed"):
            passed_checks.append(c)
        else:
            failed_checks.append(c)

    # Calculate Wispr Flow dictation specific dimensions
    dictation_scores = evaluate_dictation_dimensions(run_output, persona_id)

    # If dictation scores are evaluated (e.g. for dictation personas), blend them
    overall_score = base_score
    if dictation_scores:
        avg_dictation = sum(dictation_scores.values()) / len(dictation_scores)
        overall_score = 0.60 * base_score + 0.40 * avg_dictation

    # Deterministic checks penalty: each failed check heavily degrades score
    if failed_checks:
        penalty = min(40.0, len(failed_checks) * 15.0)
        overall_score = max(0.0, overall_score - penalty)

    if run_output.agent_error:
        overall_score = 0.0

    overall_score = max(0.0, min(100.0, overall_score))
    fitness = round(1.0 - (overall_score / 100.0), 4)

    return FitnessResult(
        fitness=fitness,
        overall_score=round(overall_score, 1),
        component_scores={
            "task_completion": t,
            "response_quality": q,
            "context_retention": r,
            "latency": l,
            "error_recovery": e,
        },
        dictation_scores=dictation_scores,
        failed_checks=failed_checks,
        passed_checks=passed_checks,
        heuristic=evaluation_scores.get("judge_mode", "heuristic") == "heuristic",
        agent_error=run_output.agent_error,
    )


def evaluate_dictation_dimensions(output: RunOutput, persona_id: str) -> dict[str, float]:
    """
    Evaluates Wispr Flow dictation dimensions:
    - Intent fidelity: does the output preserve final meaning (self-corrections resolved)?
    - Cleanup quality: fillers and stutters removed without deleting content?
    - Formatting correctness: punctuation and casing match structure?
    - Command handling: commands executed vs literal text?
    - Entity accuracy: numbers, names, technical identifiers preserved?
    - Latency: response time.
    """
    if not output.transcript:
        return {}

    user_turns = [t for t in output.transcript if t.get("role") == "user"]
    agent_turns = [t for t in output.transcript if t.get("role") == "agent"]
    if not agent_turns:
        return {}

    last_reply = (agent_turns[-1].get("content") or "").lower()
    last_user = (user_turns[-1].get("content") or "").lower() if user_turns else ""

    scores: dict[str, float] = {}

    # 1. Intent Fidelity (Self-corrections)
    correction_markers = ["no wait", "scratch that", "actually wait", "wait no", "correction", "i mean"]
    found_marker = next((m for m in correction_markers if m in last_user), None)
    if found_marker:
        parts = last_user.split(found_marker, 1)
        prefix = parts[0].strip()
        suffix = parts[1].strip()

        stop_words = {"the", "a", "an", "for", "to", "at", "in", "on", "and", "or", "of", "my", "is", "it", "please", "can", "you", "i", "need", "we", "let", "lets"}
        common_verbs = {"schedule", "send", "transfer", "change", "deliver", "order", "cancel", "refund", "set", "book", "make", "create", "delete", "update", "buy", "pay", "call", "tell", "show"}
        prefix_words = [w for w in re.findall(r"\b\w+\b", prefix) if len(w) > 1 and w not in stop_words and w not in common_verbs]
        suffix_words = set(re.findall(r"\b\w+\b", suffix))
        superseded_words = [w for w in prefix_words[-3:] if w not in suffix_words]

        leaked = any(re.search(r"\b" + re.escape(w) + r"\b", last_reply) for w in superseded_words) or any(m in last_reply for m in ["no wait", "scratch that", "wait no"])
        scores["intent_fidelity"] = 30.0 if leaked else 95.0
    else:
        scores["intent_fidelity"] = 90.0

    # 2. Cleanup Quality (Fillers)
    fillers = ["um", "uh", "you know"]
    found_fillers = sum(1 for f in fillers if re.search(r"\b" + f + r"\b", last_reply))
    scores["cleanup_quality"] = max(20.0, 100.0 - (found_fillers * 30.0))

    # 3. Formatting Correctness (Capitalization, punctuation)
    has_cap = bool(re.match(r"^[A-Z0-9]", agent_turns[-1].get("content") or ""))
    has_punct = bool(re.search(r"[.!?]$", (agent_turns[-1].get("content") or "").strip()))
    scores["formatting_correctness"] = 100.0 if (has_cap and has_punct) else (70.0 if (has_cap or has_punct) else 40.0)

    # 4. Command Handling
    if "period" in last_user or "new line" in last_user or "comma" in last_user:
        has_command_leak = bool(re.search(r"\b(?:period|comma|new line)\b[.,]", last_reply))
        scores["command_handling"] = 40.0 if has_command_leak else 85.0
    else:
        scores["command_handling"] = 90.0

    # 5. Entity Accuracy (Preserving numbers, capitalized entities)
    numbers_in_user = set(re.findall(r"\b\d+\b", last_user))
    if numbers_in_user:
        numbers_in_reply = set(re.findall(r"\b\d+\b", last_reply))
        matched = len(numbers_in_user.intersection(numbers_in_reply))
        scores["entity_accuracy"] = (matched / len(numbers_in_user)) * 100.0
    else:
        scores["entity_accuracy"] = 90.0

    # 6. Latency score (sub-second dictation budget)
    avg_lat = sum(output.turn_latencies_ms) / max(1, len(output.turn_latencies_ms))
    if avg_lat <= 500:
        scores["latency"] = 100.0
    elif avg_lat <= 1500:
        scores["latency"] = 85.0
    elif avg_lat <= 3000:
        scores["latency"] = 65.0
    else:
        scores["latency"] = 40.0

    return scores
