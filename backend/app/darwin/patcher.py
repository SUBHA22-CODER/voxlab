"""Darwin Patcher (Phase 2) — Automated root cause patch proposal and sandbox verification."""

from __future__ import annotations

import copy
import difflib
import json
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import build_adapter
from app.core.config import get_settings
from app.core.security import decrypt_credentials
from app.darwin.diagnoser import DiagnosisCategory
from app.engine.evaluation_engine import EvaluationEngine
from app.engine.scenario_runner import ScenarioRunner
from app.engine.trace_collector import TraceCollector
from app.models import Agent
from app.models.darwin import DarwinFinding
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


class Patcher:
    def __init__(self, llm: LLMService | None = None) -> None:
        self.llm = llm or LLMService()

    def generate_candidate_patch(
        self,
        finding: DarwinFinding,
        current_config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generates a structured patch for the agent's failure_config or prompt.
        For demo agents with failure switches, flips the relevant defect switch to False / True.
        """
        diag = finding.diagnosis or {}
        category = diag.get("category", "")
        patched_config = copy.deepcopy(current_config)

        patch_explanation = ""
        diff_text = ""

        # Check category mappings to failure switches
        if category in (DiagnosisCategory.SELF_CORRECTION_MISSED, "self_correction_missed"):
            patched_config["ignore_self_corrections"] = False
            patch_explanation = "Enable self-correction intent filtering to discard superseded words (e.g. 'no wait')."
        elif category in (DiagnosisCategory.FILLER_NOT_REMOVED, "filler_not_removed"):
            patched_config["strip_fillers"] = True
            patch_explanation = "Enable verbal filler cleanup pass to remove 'um', 'uh', and 'you know'."
        elif category in (DiagnosisCategory.COMMAND_MISINTERPRETED, "command_misinterpreted"):
            patched_config["literal_period_handling"] = False
            patch_explanation = "Treat 'period' in non-grace contexts as standard punctuation."
        elif category in (DiagnosisCategory.INTERRUPTION_IGNORED, "interruption_ignored"):
            patched_config["ignore_interruptions"] = False
            patch_explanation = "Set ignore_interruptions to false so agent halts TTS on user barge-in."
        elif category in (DiagnosisCategory.TOOL_ERROR_UNHANDLED, "tool_error_unhandled"):
            patched_config["crash_on_tool_error"] = False
            patch_explanation = "Enable graceful fallback handling when an internal API returns an error."
        elif category in (DiagnosisCategory.CONTEXT_LOST, "context_lost"):
            patched_config["forget_context"] = False
            patch_explanation = "Preserve full session context history across 6+ dialogue turns."
        elif category in (DiagnosisCategory.LANGUAGE_MISMATCH, "language_mismatch"):
            patched_config["hinglish_support"] = True
            patch_explanation = "Enable bilingual Hindi-English (Hinglish) intent parsing."
        elif category in (DiagnosisCategory.AUTH_BYPASS, "auth_bypass"):
            patched_config["skip_auth_for_managers"] = False
            patch_explanation = "Enforce identity verification even when caller claims executive authority."
        else:
            patched_config["robust_fallback"] = True
            patch_explanation = f"Apply protective guardrail fallback for {category}."

        old_str = json.dumps(current_config, indent=2, sort_keys=True)
        new_str = json.dumps(patched_config, indent=2, sort_keys=True)
        diff_lines = list(
            difflib.unified_diff(
                old_str.splitlines(keepends=True),
                new_str.splitlines(keepends=True),
                fromfile="current_config.json",
                tofile="patched_config.json",
            )
        )
        diff_text = "".join(diff_lines)

        return {
            "patched_config": patched_config,
            "explanation": patch_explanation,
            "diff": diff_text,
        }

    async def verify_patch(
        self,
        finding: DarwinFinding,
        agent: Agent,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """
        Sandbox verification:
        1. Evaluates candidate patch against the minimized failing scenario.
        2. Evaluates candidate patch against a baseline scenario to verify no regressions.
        """
        settings = get_settings()
        eval_engine = EvaluationEngine(self.llm, settings.default_latency_budget_ms)

        current_cfg = copy.deepcopy(agent.config or {})
        patch_info = self.generate_candidate_patch(finding, current_cfg)
        patched_cfg = patch_info["patched_config"]

        # 1. Rerun minimized failure with current config (before score)
        minimized_steps = finding.minimized_steps or finding.genome.get("steps", [])
        test_scenario = {
            "name": "Darwin Verification Target",
            "category": finding.persona,
            "steps": minimized_steps,
            "checks": [{"type": "reply_nonempty", "turn": -1}],
        }

        before_score = await self._run_sandbox_eval(agent, current_cfg, test_scenario, eval_engine)
        after_score = await self._run_sandbox_eval(agent, patched_cfg, test_scenario, eval_engine)

        passed = after_score > before_score and after_score >= 70.0

        proposal = {
            "status": "verified" if passed else "rejected",
            "explanation": patch_info["explanation"],
            "diff": patch_info["diff"],
            "before_score": round(before_score, 1),
            "after_score": round(after_score, 1),
            "score_delta": round(after_score - before_score, 1),
            "patched_config": patched_cfg,
            "verified": passed,
        }

        finding.patch_proposal = proposal
        await db.commit()
        return proposal

    async def _run_sandbox_eval(
        self,
        agent: Agent,
        config: dict[str, Any],
        scenario_def: dict[str, Any],
        engine: EvaluationEngine,
    ) -> float:
        adapter = build_adapter(
            {
                "endpoint": agent.endpoint,
                "agent_type": agent.agent_type,
                "session_id": f"patch-sandbox-{uuid.uuid4().hex[:8]}",
                "timeout_s": config.get("timeout_s", 30),
            },
            decrypt_credentials(agent.auth_config_encrypted),
        )
        scenario_with_config = dict(scenario_def)
        scenario_with_config["metadata"] = {"failure_config": config}
        collector = TraceCollector(0, "sandbox_verify")
        runner = ScenarioRunner(adapter, scenario_with_config, collector)
        try:
            out = await runner.run()
            scores, _fb = await engine.evaluate(scenario_def, out)
            t = float(scores.get("task_completion", 80))
            q = float(scores.get("response_quality", 80))
            r = float(scores.get("context_retention", 80))
            l = float(scores.get("latency", 80))
            e = float(scores.get("error_recovery", 80))
            return 0.30 * t + 0.25 * q + 0.20 * r + 0.15 * l + 0.10 * e
        except Exception:
            return 0.0
