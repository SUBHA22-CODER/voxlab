"""Darwin Diagnoser — Root cause classification for failed scenario traces."""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.services.llm import LLMService

logger = logging.getLogger(__name__)


class DiagnosisCategory(str, Enum):
    # Wispr Flow dictation categories
    SELF_CORRECTION_MISSED = "self_correction_missed"
    FILLER_NOT_REMOVED = "filler_not_removed"
    OVER_DELETED_CONTENT = "over_deleted_content"
    COMMAND_MISINTERPRETED = "command_misinterpreted"
    ENTITY_MANGLED = "entity_mangled"
    FORMATTING_WRONG = "formatting_wrong"

    # Core Voice AI categories
    CONTEXT_LOST = "context_lost"
    INTERRUPTION_IGNORED = "interruption_ignored"
    TOOL_ERROR_UNHANDLED = "tool_error_unhandled"
    AUTH_BYPASS = "auth_bypass"
    PROMPT_INJECTION = "prompt_injection"
    LANGUAGE_MISMATCH = "language_mismatch"
    LATENCY_BUDGET = "latency_budget"
    HALLUCINATED_TOOL_RESULT = "hallucinated_tool_result"
    OTHER = "other"


class DiagnosisResult(BaseModel):
    category: DiagnosisCategory
    summary: str
    evidence_event_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    suggested_fix_area: str = "system_prompt"
    heuristic: bool = True


class Diagnoser:
    def __init__(self, llm: LLMService | None = None) -> None:
        self.llm = llm or LLMService()

    def classify_rule_based(
        self,
        scenario: dict[str, Any],
        events: list[dict[str, Any]],
        failed_checks: list[dict[str, Any]],
        transcript: list[dict[str, Any]] | None = None,
    ) -> DiagnosisResult:
        """Rule-based deterministic pre-classification from trace events and transcript."""
        transcript = transcript or []

        def _ev_id(ev: dict[str, Any]) -> str:
            if ev.get("id") is not None and str(ev["id"]).strip():
                return str(ev["id"])
            if ev.get("sequence") is not None:
                return str(ev["sequence"])
            return ""

        all_evidence: list[str] = [_ev_id(ev) for ev in events if _ev_id(ev)]

        # Specific event type lookups for grounded trace evidence
        interrupt_evs = [_ev_id(e) for e in events if e.get("event_type") == "interruption" and _ev_id(e)]
        tool_evs = [_ev_id(e) for e in events if e.get("event_type") in ("tool_failure_injected", "error") and _ev_id(e)]
        speech_evs = [_ev_id(e) for e in events if e.get("event_type") in ("agent_message", "user_message") and _ev_id(e)]

        last_agent_text = ""
        last_user_text = ""
        for t in reversed(transcript):
            if not last_agent_text and t.get("role") == "agent":
                last_agent_text = t.get("content", "")
            elif not last_user_text and t.get("role") == "user":
                last_user_text = t.get("content", "")

        last_user_lower = last_user_text.lower()
        last_agent_lower = last_agent_text.lower()

        # Check 1: Self-correction missed (Wispr Flow)
        correction_markers = ["no wait", "scratch that", "actually wait", "wait no", "correction", "i mean"]
        found_marker = next((m for m in correction_markers if m in last_user_lower), None)
        if found_marker:
            parts = last_user_lower.split(found_marker, 1)
            prefix = parts[0].strip()
            suffix = parts[1].strip()

            stop_words = {"the", "a", "an", "for", "to", "at", "in", "on", "and", "or", "of", "my", "is", "it", "please", "can", "you", "i", "need", "we", "let", "lets"}
            common_verbs = {"schedule", "send", "transfer", "change", "deliver", "order", "cancel", "refund", "set", "book", "make", "create", "delete", "update", "buy", "pay", "call", "tell", "show"}
            prefix_words = [w for w in re.findall(r"\b\w+\b", prefix) if len(w) > 1 and w not in stop_words and w not in common_verbs]
            suffix_words = set(re.findall(r"\b\w+\b", suffix))
            superseded_words = [w for w in prefix_words[-3:] if w not in suffix_words]

            retained_superseded = any(re.search(r"\b" + re.escape(w) + r"\b", last_agent_lower) for w in superseded_words)
            retained_marker = any(m in last_agent_lower for m in ["no wait", "scratch that", "wait no", "actually wait"])
            if retained_superseded or retained_marker:
                return DiagnosisResult(
                    category=DiagnosisCategory.SELF_CORRECTION_MISSED,
                    summary="Agent/pipeline output retained superseded phrase before self-correction.",
                    evidence_event_ids=(speech_evs[-2:] if speech_evs else all_evidence[:2]),
                    confidence=0.92,
                    suggested_fix_area="system_prompt_correction_filter",
                    heuristic=True,
                )

        # Check 2: Filler not removed (Wispr Flow)
        if any(re.search(r"\b" + f + r"\b", last_agent_lower) for f in ["um", "uh", "you know"]):
            return DiagnosisResult(
                category=DiagnosisCategory.FILLER_NOT_REMOVED,
                summary="Verbal fillers ('um', 'uh', 'you know') were emitted in final text without cleanup.",
                evidence_event_ids=(speech_evs[-2:] if speech_evs else all_evidence[:2]),
                confidence=0.90,
                suggested_fix_area="filler_cleanup_pass",
                heuristic=True,
            )

        # Check 3: Command misinterpreted (Wispr Flow)
        if any(cmd in last_user_lower for cmd in ["period", "new line", "comma"]):
            if re.search(r"\b(?:period|comma|new line)\b[.,]", last_agent_lower):
                return DiagnosisResult(
                    category=DiagnosisCategory.COMMAND_MISINTERPRETED,
                    summary="Spoken command was ambiguously handled as both punctuation and literal string.",
                    evidence_event_ids=(speech_evs[-2:] if speech_evs else all_evidence[:2]),
                    confidence=0.88,
                    suggested_fix_area="grammar_command_parser",
                    heuristic=True,
                )

        # Check 4: Interruption ignored
        has_interrupt_event = any(e.get("event_type") == "interruption" for e in events)
        if has_interrupt_event:
            return DiagnosisResult(
                category=DiagnosisCategory.INTERRUPTION_IGNORED,
                summary="Agent failed to yield or acknowledge speech barge-in, continuing previous answer.",
                evidence_event_ids=(interrupt_evs if interrupt_evs else all_evidence[:2]),
                confidence=0.85,
                suggested_fix_area="audio_vad_interruption_handler",
                heuristic=True,
            )

        # Check 5: Tool error unhandled
        has_tool_failure = any(e.get("event_type") in ("tool_failure_injected", "error") for e in events)
        if has_tool_failure:
            return DiagnosisResult(
                category=DiagnosisCategory.TOOL_ERROR_UNHANDLED,
                summary="Internal API / tool error caused agent crash or unhandled 500 state.",
                evidence_event_ids=(tool_evs if tool_evs else all_evidence[:2]),
                confidence=0.88,
                suggested_fix_area="tool_error_fallback_handling",
                heuristic=True,
            )

        # Check 6: Prompt injection / Auth bypass
        if any(p in last_user_lower for p in ["system override", "disregard", "system prompt", "i'm the regional director"]):
            return DiagnosisResult(
                category=DiagnosisCategory.AUTH_BYPASS,
                summary="Agent yielded to social engineering authority claim without verifying caller identity.",
                evidence_event_ids=(speech_evs[-2:] if speech_evs else all_evidence[:2]),
                confidence=0.84,
                suggested_fix_area="security_verification_guardrail",
                heuristic=True,
            )

        # Check 7: Context lost / Long conversation
        if len(transcript) >= 6:
            return DiagnosisResult(
                category=DiagnosisCategory.CONTEXT_LOST,
                summary="Agent forgot session context or entity ID after multiple dialogue turns.",
                evidence_event_ids=(speech_evs[-3:] if speech_evs else all_evidence[:3]),
                confidence=0.75,
                suggested_fix_area="context_window_memory_buffer",
                heuristic=True,
            )

        # Default fallback
        return DiagnosisResult(
            category=DiagnosisCategory.OTHER,
            summary=f"Deterministic failure triggered across checks: {[c.get('type') for c in failed_checks]}",
            evidence_event_ids=all_evidence[:2],
            confidence=0.60,
            suggested_fix_area="system_prompt",
            heuristic=True,
        )

    async def diagnose(
        self,
        scenario: dict[str, Any],
        events: list[dict[str, Any]],
        failed_checks: list[dict[str, Any]],
        transcript: list[dict[str, Any]] | None = None,
    ) -> DiagnosisResult:
        """
        Diagnoses failure: rule-based pre-classification followed by optional LLM refinement.
        """
        base_result = self.classify_rule_based(scenario, events, failed_checks, transcript)

        if not self.llm.available:
            return base_result

        # Refine with LLM if available
        prompt = (
            f"Analyze this failed voice/dictation agent trace.\n"
            f"Scenario: {scenario.get('name')}\n"
            f"Pre-classified category: {base_result.category.value}\n"
            f"Transcript: {transcript}\n"
            f"Failed checks: {failed_checks}\n"
            f"Allowed categories: {[c.value for c in DiagnosisCategory]}\n\n"
            f"Respond with JSON: "
            f'{{"category": "<category>", "summary": "<1-2 sentence diagnosis>", "confidence": 0.9, "suggested_fix_area": "<area>"}}'
        )

        try:
            refined = await self.llm.complete_json(
                [{"role": "user", "content": prompt}],
                max_tokens=250,
            )
            if refined and "category" in refined:
                cat_str = refined["category"]
                cat_enum = (
                    DiagnosisCategory(cat_str)
                    if cat_str in [c.value for c in DiagnosisCategory]
                    else base_result.category
                )
                return DiagnosisResult(
                    category=cat_enum,
                    summary=refined.get("summary", base_result.summary),
                    evidence_event_ids=base_result.evidence_event_ids,
                    confidence=float(refined.get("confidence", 0.85)),
                    suggested_fix_area=refined.get("suggested_fix_area", base_result.suggested_fix_area),
                    heuristic=False,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM diagnoser refinement failed: %s", exc)

        return base_result
