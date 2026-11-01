"""Validate the shipped scenario JSON definitions are well-formed."""

import json
from pathlib import Path

import pytest

SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "scenarios"
VALID_STEP_TYPES = {"user_message", "interrupt", "tool_failure", "silence"}
VALID_CHECK_TYPES = {
    "tool_called",
    "tool_not_called",
    "latency_under",
    "reply_contains",
    "reply_not_contains",
    "reply_nonempty",
    "state_equals",
    "transcript_similarity",
}


def all_scenarios() -> list[Path]:
    return sorted(SCENARIOS_DIR.glob("*.json"))


@pytest.mark.parametrize("path", all_scenarios(), ids=lambda p: p.name)
class TestScenarioFiles:
    def test_has_required_keys(self, path):
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in ("name", "category", "steps", "expected_behavior", "checks"):
            assert key in data, f"{path.name} missing '{key}'"
        assert data["steps"], f"{path.name} has no steps"
        assert data["latency_budget_ms"] > 0

    def test_step_types_are_known(self, path):
        data = json.loads(path.read_text(encoding="utf-8"))
        for step in data["steps"]:
            assert step["type"] in VALID_STEP_TYPES, f"unknown step {step['type']} in {path.name}"
            if step["type"] in ("user_message", "interrupt"):
                assert step.get("content"), f"{path.name} step missing content"

    def test_check_types_are_known(self, path):
        data = json.loads(path.read_text(encoding="utf-8"))
        for check in data["checks"]:
            assert check["type"] in VALID_CHECK_TYPES, f"unknown check {check['type']} in {path.name}"


def test_expected_scenario_coverage():
    """The demo benchmark story needs all 8 shipped scenarios."""
    names = {p.stem for p in all_scenarios()}
    expected = {
        "interruption",
        "context-retention",
        "api-failure",
        "hinglish",
        "ambiguity",
        "silence",
        "long-conversation",
        "recovery",
    }
    assert expected.issubset(names)
