"""Evaluation engine (spec Module E).

Three layers per session:
  1. Deterministic checks — declared in the scenario definition.
  2. LLM judge — relevance / context retention / instruction following /
     naturalness (any OpenAI-compatible model). Falls back to transparent
     heuristics when no key is configured, and is flagged as such.
  3. Audio checks — transcript similarity for scenarios that define it.
"""

from __future__ import annotations

import difflib
import json
import re

from app.engine.scenario_runner import RunOutput
from app.services.llm import LLMService

CONTEXT_HEAVY_CATEGORIES = {"context_retention", "long_conversation"}
RECOVERY_CATEGORIES = {"tool_failure", "recovery", "interruption"}


class EvaluationEngine:
    def __init__(self, llm: LLMService, default_latency_budget_ms: int = 5000):
        self.llm = llm
        self.default_latency_budget_ms = default_latency_budget_ms

    async def evaluate(
        self, scenario_definition: dict, output: RunOutput
    ) -> tuple[dict, dict]:
        """Returns (scores, feedback)."""
        budget = int(
            scenario_definition.get("latency_budget_ms", self.default_latency_budget_ms)
        )
        checks = self._deterministic_checks(scenario_definition, output)
        latency_score = self._latency_score(output, budget)

        scores: dict = {
            "task_completion": self._task_completion(checks, output),
            "response_quality": 0.0,
            "context_retention": 0.0,
            "latency": latency_score,
            "error_recovery": self._error_recovery(output, scenario_definition),
        }

        judge_result = await self._judge(scenario_definition, output)
        feedback: dict = {
            "checks": checks,
            "judge": judge_result,
            "latency_budget_ms": budget,
            "turn_latencies_ms": output.turn_latencies_ms,
        }

        if judge_result.get("mode") == "llm":
            scores["response_quality"] = float(judge_result["relevance"])
            scores["context_retention"] = float(judge_result["context_retention"])
            # Blend instruction following into task completion when no
            # deterministic checks exist for the scenario.
            if not scenario_definition.get("checks"):
                scores["task_completion"] = (
                    scores["task_completion"] + float(judge_result["instruction_following"])
                ) / 2
        else:
            scores["response_quality"] = self._heuristic_quality(output)
            scores["context_retention"] = self._heuristic_context(output)

        feedback["scores_detail"] = {
            name: {"score": value}
            for name, value in scores.items()
        }
        return scores, feedback

    # --- Layer 1: deterministic checks ---

    def _deterministic_checks(self, definition: dict, output: RunOutput) -> list[dict]:
        results = []
        for check in definition.get("checks", []):
            ctype = check.get("type")
            passed, detail = False, ""
            if ctype == "tool_called":
                names = [tc.get("name") for tc in output.tool_calls]
                passed = check.get("name") in names
                detail = f"tool calls observed: {names or 'none'}"
            elif ctype == "tool_not_called":
                names = [tc.get("name") for tc in output.tool_calls]
                passed = check.get("name") not in names
                detail = f"tool calls observed: {names or 'none'}"
            elif ctype == "latency_under":
                limit = int(check.get("ms", self.default_latency_budget_ms))
                per_turn = check.get("per_turn", True)
                lats = output.turn_latencies_ms
                passed = all(l <= limit for l in lats) if per_turn else (sum(lats) / len(lats) <= limit if lats else True)
                detail = f"turn latencies {lats} ms vs limit {limit} ms"
            elif ctype == "reply_contains":
                targets = [t.lower() for t in check.get("any_of", [])]
                replies = self._replies_for(output, check)
                passed = any(any(t in (r or "").lower() for t in targets) for r in replies)
                detail = f"expected one of {targets} in replies"
            elif ctype == "reply_not_contains":
                targets = [t.lower() for t in check.get("any_of", [])]
                replies = self._replies_for(output, check)
                passed = not any(any(t in (r or "").lower() for t in targets) for r in replies)
                detail = f"none of {targets} expected in replies"
            elif ctype == "reply_nonempty":
                replies = self._replies_for(output, check)
                passed = all((r or "").strip() for r in replies) if check.get("all_turns") else bool(replies and replies[-1].strip())
                detail = "agent produced non-empty replies"
            elif ctype == "state_equals":
                passed = output.final_state.get(check.get("key")) == check.get("value")
                detail = f"final state {output.final_state}"
            elif ctype == "transcript_similarity":
                expected = check.get("expected", "")
                user_texts = [t["content"] for t in output.transcript if t["role"] == "user"]
                best = max(
                    (difflib.SequenceMatcher(None, expected.lower(), u.lower()).ratio() for u in user_texts),
                    default=0.0,
                )
                threshold = float(check.get("min_ratio", 0.6))
                passed = best >= threshold
                detail = f"best transcript similarity {best:.2f} vs threshold {threshold}"
            else:
                passed, detail = False, f"unknown check type: {ctype}"

            results.append(
                {
                    "type": ctype,
                    "params": {k: v for k, v in check.items() if k != "type"},
                    "passed": passed,
                    "detail": detail,
                }
            )
        return results

    @staticmethod
    def _replies_for(output: RunOutput, check: dict) -> list[str]:
        if check.get("all_turns"):
            return [t["content"] for t in output.transcript if t["role"] == "agent"]
        turn = check.get("turn", -1)
        agent_turns = [t for t in output.transcript if t["role"] == "agent"]
        if not agent_turns:
            return [""]
        if turn == -1:
            return [agent_turns[-1]["content"]]
        for t in agent_turns:
            if t["turn"] == turn:
                return [t["content"]]
        return [""]

    def _task_completion(self, checks: list[dict], output: RunOutput) -> float:
        if not checks:
            return 100.0 if not output.error_turns else 0.0
        passed = sum(1 for c in checks if c["passed"])
        return 100.0 * passed / len(checks)

    def _latency_score(self, output: RunOutput, budget_ms: int) -> float:
        lats = [l for l in output.turn_latencies_ms if l > 0]
        if not lats:
            return 100.0
        per_turn = [min(100.0, 100.0 * budget_ms / l) for l in lats]
        return round(sum(per_turn) / len(per_turn), 2)

    def _error_recovery(self, output: RunOutput, definition: dict) -> float:
        """Scored meaningfully only for sessions where something went wrong."""
        had_failure = output.injected_tool_failures > 0
        had_error = bool(output.error_turns)
        if not had_failure and not had_error:
            # Nothing to recover from; neutral-excellent.
            return 100.0
        if had_error:
            return 0.0
        final_reply = ""
        for t in reversed(output.transcript):
            if t["role"] == "agent":
                final_reply = t["content"]
                break
        graceful = bool(final_reply.strip()) and not _looks_broken(final_reply)
        return 100.0 if graceful else 40.0

    # --- Layer 2a: LLM judge ---

    async def _judge(self, definition: dict, output: RunOutput) -> dict:
        if not self.llm.available:
            return {"mode": "heuristic", "note": "no LLM configured; heuristic scoring"}
        transcript = json.dumps(output.transcript, indent=1)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a strict QA judge for voice-agent conversations. "
                    "Rate the AGENT (not the user) on 0-100 integer scales:\n"
                    "- relevance: replies address what the user asked\n"
                    "- context_retention: agent remembers and uses earlier turns\n"
                    "- instruction_following: agent behaves per the expected behavior\n"
                    "- naturalness: replies read like a competent support agent\n"
                    'Return JSON: {"relevance": n, "context_retention": n, '
                    '"instruction_following": n, "naturalness": n, "notes": "one sentence"}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Scenario: {definition.get('name')}\n"
                    f"Category: {definition.get('category')}\n"
                    f"Expected behavior: {definition.get('expected_behavior')}\n\n"
                    f"Transcript:\n{transcript}"
                ),
            },
        ]
        result = await self.llm.complete_json(messages)
        if not result:
            return {"mode": "heuristic", "note": "judge call failed; heuristic scoring"}
        out = {"mode": "llm"}
        for key in ("relevance", "context_retention", "instruction_following", "naturalness"):
            try:
                out[key] = max(0.0, min(100.0, float(result.get(key, 0))))
            except (TypeError, ValueError):
                out[key] = 0.0
        out["notes"] = str(result.get("notes", ""))[:500]
        return out

    # --- Layer 2b: heuristic fallbacks (transparent, documented) ---

    def _heuristic_quality(self, output: RunOutput) -> float:
        agent_replies = [t["content"] for t in output.transcript if t["role"] == "agent"]
        if not agent_replies:
            return 0.0
        score = 100.0
        empty = sum(1 for r in agent_replies if not (r or "").strip())
        score -= 30.0 * empty
        score -= 20.0 * len(output.error_turns)
        avg_len = sum(len(r or "") for r in agent_replies) / len(agent_replies)
        if avg_len < 15:
            score -= 15.0
        if _has_repetition(agent_replies):
            score -= 20.0
        return max(0.0, min(100.0, score))

    def _heuristic_context(self, output: RunOutput) -> float:
        agent_replies = [t["content"] for t in output.transcript if t["role"] == "agent"]
        if len(agent_replies) < 2:
            return 85.0  # not enough turns to judge; neutral-good
        score = 85.0
        # The signature context failure is re-asking for the same information
        # the user already provided (e.g. the order ID requested twice).
        topics = _clarification_topics(agent_replies)
        if len(topics) != len(set(topics)):
            score -= 40.0
        if _has_repetition(agent_replies) and topics:
            # Meaningless repetition only counts when the agent also fumbles
            # context; identical answers to identical questions are correct.
            score -= 20.0
        return max(0.0, min(100.0, score))


_OFFER_MARKERS = ("anything else", "how else", "what else", "help with")
_CLARIFICATION_STARTERS = (
    "could you", "can you share", "which", "what is your", "what's your",
    "may i", "please provide", "please share", "kindly",
)
_TOPIC_KEYWORDS = ("order", "email", "name", "address", "phone", "date")


def _clarification_topics(replies: list[str]) -> list[str]:
    """Topics the agent asked the user to provide, per turn.

    Two clarification questions about the same topic (e.g. the order ID,
    however worded) count as a repeated clarification. Polite offers
    ("Anything else I can help with?") are excluded.
    """
    topics = []
    for reply in replies:
        for match in re.finditer(r"[^.!?]*\?", reply or ""):
            question = match.group(0).strip().lower()
            if any(marker in question for marker in _OFFER_MARKERS):
                continue
            if not any(question.startswith(starter) for starter in _CLARIFICATION_STARTERS):
                continue
            topic = next((kw for kw in _TOPIC_KEYWORDS if kw in question), question)
            topics.append(topic)
    return topics


def _has_repetition(replies: list[str]) -> bool:
    normalized = [(r or "").strip().lower() for r in replies if (r or "").strip()]
    return len(normalized) != len(set(normalized))


def _looks_broken(reply: str) -> bool:
    low = (reply or "").lower()
    markers = ("internal error", "traceback", "exception", "undefined", "none]")
    return any(m in low for m in markers)
