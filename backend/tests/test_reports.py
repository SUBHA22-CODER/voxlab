"""Tests for benchmark report aggregation and the scoring formula."""

from app.engine.reports import compare_reports, generate_report_summary


def make_scores(**overrides) -> dict:
    base = {
        "task_completion": 90.0,
        "response_quality": 85.0,
        "context_retention": 92.0,
        "latency": 78.0,
        "error_recovery": 88.0,
    }
    base.update(overrides)
    return base


def make_session(session_id=1, name="Interruption Test", category="interruption",
                 status="completed", scores=None, failed_checks=None) -> dict:
    return {
        "session_id": session_id,
        "scenario_name": name,
        "category": category,
        "status": status,
        "scores": scores if scores is not None else make_scores(),
        "feedback": {"checks": failed_checks or [], "judge": {"mode": "heuristic", "notes": "ok"}},
    }


class TestReportGeneration:
    def test_spec_example_score(self):
        # Spec §10 weights: 0.30*90 + 0.25*85 + 0.20*92 + 0.15*78 + 0.10*88.
        # (The spec text prints 86.65, but its own weights sum to 87.15.)
        summary = generate_report_summary({}, [make_session()])
        assert summary["score"] == 87.15

    def test_weights_override_changes_score(self):
        sessions = [make_session()]
        default = generate_report_summary({}, sessions)
        custom = generate_report_summary(
            {"weights": {"T": 1.0, "Q": 0.0, "R": 0.0, "L": 0.0, "E": 0.0}}, sessions
        )
        assert custom["score"] == 90.0
        assert custom["score"] != default["score"]
        assert custom["weights"]["T"] == 1.0

    def test_context_score_uses_context_heavy_sessions_only(self):
        sessions = [
            make_session(1, "Context Retention", "context_retention",
                         scores=make_scores(context_retention=100.0)),
            make_session(2, "Interruption", "interruption",
                         scores=make_scores(context_retention=0.0)),
        ]
        summary = generate_report_summary({}, sessions)
        assert summary["components"]["R"] == 100.0

    def test_failing_checks_mark_session_failed(self):
        failed_check = {"type": "reply_nonempty", "params": {}, "passed": False, "detail": "empty"}
        summary = generate_report_summary({}, [make_session(failed_checks=[failed_check])])
        assert summary["totals"]["failed"] == 1
        assert summary["failures"][0]["failed_checks"] == [failed_check]

    def test_failed_session_status_excluded_from_component_means(self):
        summary = generate_report_summary(
            {},
            [
                make_session(1, status="failed", scores={}),
                make_session(2, category="context_retention"),
            ],
        )
        assert summary["components"]["T"] == 90.0
        assert summary["totals"]["completed"] == 1

    def test_no_scored_sessions_gives_zero_score(self):
        summary = generate_report_summary({}, [make_session(1, status="failed", scores={})])
        assert summary["score"] == 0.0

    def test_methodology_is_surfaced(self):
        summary = generate_report_summary({}, [make_session()])
        assert "formula" in summary["methodology"] or summary.get("formula")
        assert summary["formula"].startswith("Score =")
        assert "heuristic" in summary["methodology"]["heuristic_note"].lower()


class TestComparison:
    def test_delta_math(self):
        baseline = generate_report_summary({}, [make_session()])
        improved = generate_report_summary(
            {}, [make_session(scores=make_scores(task_completion=100.0, latency=88.0))]
        )
        result = compare_reports(baseline, improved)
        assert result["deltas"]["T"] == 10.0
        assert result["deltas"]["score"] == pytest_delta(result)
        assert result["baseline"]["score"] < result["candidate"]["score"]


def pytest_delta(result) -> float:
    return round(result["candidate"]["score"] - result["baseline"]["score"], 2)
