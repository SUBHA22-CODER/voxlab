"""Benchmark report generation (spec §10 — transparent scoring)."""

from __future__ import annotations

from statistics import mean

DEFAULT_WEIGHTS = {"T": 0.30, "Q": 0.25, "R": 0.20, "L": 0.15, "E": 0.10}

CONTEXT_HEAVY_CATEGORIES = {"context_retention", "long_conversation"}
RECOVERY_CATEGORIES = {"tool_failure", "recovery", "interruption"}


def generate_report_summary(run_config: dict, sessions: list[dict]) -> dict:
    """Build the full report summary from per-session evaluation rows.

    Each session dict: {session_id, scenario_name, category, status,
    scores: {...}, feedback: {...}}
    """
    weights = {**DEFAULT_WEIGHTS, **(run_config.get("weights") or {})}

    completed = [s for s in sessions if s.get("status") == "completed"]
    scored = [s for s in completed if s.get("scores")]

    per_session = []
    for s in sessions:
        scores = s.get("scores") or {}
        feedback = s.get("feedback") or {}
        failed_checks = [c for c in feedback.get("checks", []) if not c.get("passed")]
        passed = s.get("status") == "completed" and not failed_checks and not scores.get("_error")
        per_session.append(
            {
                "session_id": s.get("session_id"),
                "scenario_name": s.get("scenario_name"),
                "category": s.get("category"),
                "status": s.get("status"),
                "passed": passed,
                "overall": round(
                    _session_weighted(scores, weights), 2
                )
                if scores
                else None,
                "scores": scores,
                "failed_checks": failed_checks,
                "judge_notes": (feedback.get("judge") or {}).get("notes", ""),
                "judge_mode": (feedback.get("judge") or {}).get("mode"),
            }
        )

    if scored:
        t = mean(s["scores"].get("task_completion", 0) for s in scored)
        q = mean(s["scores"].get("response_quality", 0) for s in scored)

        context_sessions = [s for s in scored if s.get("category") in CONTEXT_HEAVY_CATEGORIES]
        r_pool = context_sessions or scored
        r = mean(s["scores"].get("context_retention", 0) for s in r_pool)

        l = mean(s["scores"].get("latency", 0) for s in scored)

        recovery_sessions = [s for s in scored if s.get("category") in RECOVERY_CATEGORIES]
        if recovery_sessions:
            e = mean(s["scores"].get("error_recovery", 0) for s in recovery_sessions)
        else:
            # No dedicated failure scenarios: use each session's own
            # error_recovery score (100 when nothing went wrong, 0 on errors).
            e = mean(s["scores"].get("error_recovery", 0) for s in scored)
    else:
        t = q = r = l = e = 0.0

    components = {"T": round(t, 2), "Q": round(q, 2), "R": round(r, 2), "L": round(l, 2), "E": round(e, 2)}
    score = round(sum(weights[k] * components[k] for k in components), 2)

    failures = [
        {
            "session_id": p["session_id"],
            "scenario_name": p["scenario_name"],
            "category": p["category"],
            "failed_checks": p["failed_checks"],
            "judge_notes": p["judge_notes"],
        }
        for p in per_session
        if not p["passed"]
    ]

    judge_modes = {p["judge_mode"] for p in per_session if p.get("judge_mode")}
    return {
        "score": score,
        "components": components,
        "weights": weights,
        "formula": "Score = 0.30·T + 0.25·Q + 0.20·R + 0.15·L + 0.10·E (weights configurable)",
        "legend": {
            "T": "Task completion (deterministic checks)",
            "Q": "Response quality (LLM judge / heuristics)",
            "R": "Context retention (context-heavy scenarios)",
            "L": "Latency (per-turn vs budget)",
            "E": "Error recovery (failure scenarios)",
        },
        "judge_mode": "llm" if "llm" in judge_modes else ("heuristic" if judge_modes else None),
        "totals": {
            "sessions": len(sessions),
            "completed": len(completed),
            "passed": sum(1 for p in per_session if p["passed"]),
            "failed": sum(1 for p in per_session if not p["passed"]),
        },
        "per_session": per_session,
        "failures": failures,
        "methodology": {
            "weights_note": "Weights are configurable per test run and shown above.",
            "latency_note": "Per-turn score = min(100, 100 × budget / actual), averaged across turns.",
            "heuristic_note": (
                "Heuristic mode: quality/context scores come from transparent rules "
                "(empty replies, error turns, repetition, repeated questions), not an LLM."
            ),
        },
    }


def _session_weighted(scores: dict, weights: dict) -> float:
    return (
        weights["T"] * scores.get("task_completion", 0)
        + weights["Q"] * scores.get("response_quality", 0)
        + weights["R"] * scores.get("context_retention", 0)
        + weights["L"] * scores.get("latency", 0)
        + weights["E"] * scores.get("error_recovery", 0)
    )


def compare_reports(baseline_summary: dict, candidate_summary: dict) -> dict:
    deltas = {}
    for key in ("score",):
        deltas[key] = round(candidate_summary.get(key, 0) - baseline_summary.get(key, 0), 2)
    for key in ("T", "Q", "R", "L", "E"):
        deltas[key] = round(
            candidate_summary.get("components", {}).get(key, 0)
            - baseline_summary.get("components", {}).get(key, 0),
            2,
        )
    return {
        "baseline": _compact(baseline_summary),
        "candidate": _compact(candidate_summary),
        "deltas": deltas,
    }


def _compact(summary: dict) -> dict:
    return {
        "score": summary.get("score"),
        "components": summary.get("components"),
        "totals": summary.get("totals"),
        "failures": summary.get("failures"),
    }
