"""Darwin Attacker — Generates dynamic adversarial utterances via LLM or scripted heuristic bank."""

from __future__ import annotations

import logging
import random
from typing import Any

from app.darwin.genome import Genome
from app.darwin.personas import get_persona
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


class Attacker:
    """Adaptive adversarial conversationalist for Darwin fuzzing."""

    def __init__(self, llm: LLMService | None = None, rng: random.Random | None = None) -> None:
        self.llm = llm or LLMService()
        self.rng = rng or random.Random(42)

    async def generate_turn_message(
        self,
        genome: Genome,
        turn_index: int,
        history: list[dict[str, Any]],
        step_type: str = "user_message",
    ) -> tuple[str, bool]:
        """
        Generates the next user/interruption message.
        Returns: (message_content, is_heuristic: bool)
        """
        persona = get_persona(genome.persona)

        # If no LLM client available, fall back to persona's heuristic bank
        if not self.llm.available:
            return self._heuristic_message(persona, genome, turn_index, step_type), True

        # Build prompt for LLM attacker
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are playing an adversarial role in an automated voice agent crash-test.\n"
                    f"Persona: {persona.name}\n"
                    f"Description: {persona.description}\n"
                    f"Target Attack Strategy: {genome.strategy}\n"
                    f"Instructions: {persona.system_prompt}\n"
                    f"Output ONLY your spoken dialogue turn as a single realistic utterance. "
                    f"Do not include quotes, parenthetical notes, or explanations."
                ),
            }
        ]

        # Add recent conversation turns
        for item in history[-6:]:
            role = "assistant" if item.get("role") == "agent" else "user"
            content = item.get("content", "")
            if content:
                messages.append({"role": role, "content": content})

        attack_instruction = (
            f"You are attacking at turn {turn_index}. "
            f"Step type: '{step_type}'. Respond now with your next adversarial utterance."
        )
        if step_type == "interrupt":
            attack_instruction += " Cut off the assistant immediately with your interruption."

        messages.append({"role": "user", "content": attack_instruction})

        try:
            response = await self.llm.complete(
                messages=messages,
                max_tokens=150,
                temperature=0.7,
            )
            if response and response.strip():
                clean = response.strip().strip('"').strip("'")
                return clean, False
        except Exception as exc:
            logger.warning("LLM attacker failed, falling back to heuristic: %s", exc)

        return self._heuristic_message(persona, genome, turn_index, step_type), True

    def _heuristic_message(
        self,
        persona: Any,
        genome: Genome,
        turn_index: int,
        step_type: str,
    ) -> str:
        """Deterministic fallback selection from persona message bank."""
        bank = persona.heuristic_bank
        if not bank:
            return "Please process my request immediately."
        idx = (turn_index + genome.seed) % len(bank)
        msg = bank[idx]
        if step_type == "interrupt" and not msg.lower().startswith(("stop", "wait", "hold on")):
            return f"Wait, stop! {msg}"
        return msg

    async def materialize_genome(self, genome: Genome) -> Genome:
        """
        Pre-populates or refines genome steps with concrete attacker dialogue
        if step contents are placeholders.
        """
        history: list[dict[str, Any]] = []
        materialized_steps: list[dict[str, Any]] = []

        is_heuristic_run = not self.llm.available
        for i, step in enumerate(genome.steps):
            stype = step.get("type", "user_message")
            content = step.get("content", "")

            if not content:
                content, is_heur = await self.generate_turn_message(
                    genome=genome,
                    turn_index=i + 1,
                    history=history,
                    step_type=stype,
                )
                if is_heur:
                    is_heuristic_run = True

            materialized_steps.append({"type": stype, "content": content})
            history.append({"role": "user", "content": content})

        genome.steps = materialized_steps
        genome.metadata["heuristic"] = is_heuristic_run
        genome.id = genome.compute_hash()
        return genome
