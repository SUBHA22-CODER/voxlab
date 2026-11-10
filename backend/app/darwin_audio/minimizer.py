# minimizer.py
# Delta debugging over audio transformation chains (Phase 5).
#
# When Darwin discovers a failing candidate (engine mis-transcribes it), the
# chain that produced the failure often contains redundant steps. This module
# shrinks the chain to the smallest subset that still reproduces the failure.
#
# Contract (per the master spec): a minimized candidate is ONLY accepted when
# the failure was actually reproduced through the real evaluation function —
# never assumed. `max_evaluations` bounds the cost; evaluations are expensive
# (each is a real transcription).

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from .genome import AudioGenome
from .personas import AUDIO_PERSONAS

logger = logging.getLogger(__name__)


@dataclass
class MinimizationResult:
    minimized_genome: AudioGenome | None
    original_steps: int
    minimized_steps: int
    evaluations_used: int
    failure_reproduced: bool
    history: list[str] = field(default_factory=list)


async def minimize_audio_finding(
    genome: AudioGenome,
    evaluate: Callable[[AudioGenome], Awaitable[float]],
    *,
    max_evaluations: int = 12,
) -> MinimizationResult:
    """Shrink genome.transform_chain while the failure still reproduces.

    evaluate: async (genome) -> rewarded failure score in [0, 1]. The failure
    "persists" when the score is >= the original's (strictly-greater would be
    simpler but selection uses >= to tolerate stochastic engines; the score
    used for comparison is captured from the first reproduction run).
    """
    original_steps = len(genome.transform_chain)
    history: list[str] = []
    if original_steps <= 1:
        return MinimizationResult(
            minimized_genome=genome if original_steps == 1 else None,
            original_steps=original_steps,
            minimized_steps=original_steps,
            evaluations_used=0,
            failure_reproduced=original_steps == 1,
            history=history,
        )

    evaluations = 0

    async def persists(chain: list) -> bool | None:
        nonlocal evaluations
        if evaluations >= max_evaluations:
            return None
        evaluations += 1
        candidate = AudioGenome(
            persona_id=genome.persona_id,
            seed_audio_ref=genome.seed_audio_ref,
            seed_transcript=genome.seed_transcript,
            seed_language=genome.seed_language,
            transform_chain=list(chain),
            content_mutations=list(genome.content_mutations),
            generation=genome.generation,
            parent_ids=list(genome.parent_ids),
            seed=genome.seed,
        )
        try:
            score = await evaluate(candidate)
        except Exception as exc:  # noqa: BLE001 - any failure = cannot confirm
            logger.debug("minimize evaluation failed: %s", exc)
            return False
        return score >= baseline_score

    baseline_score = await evaluate(genome)
    evaluations += 1  # baseline counted (evaluate() above incremented too)

    # No failure at baseline -> nothing to minimize (0 >= 0 would trivially
    # "persist" and fabricate a minimization).
    if baseline_score <= 0.0:
        return MinimizationResult(
            minimized_genome=None,
            original_steps=original_steps,
            minimized_steps=original_steps,
            evaluations_used=evaluations,
            failure_reproduced=False,
            history=["baseline score is zero; no failure to minimize"],
        )

    current = list(genome.transform_chain)
    if not await persists(current):
        return MinimizationResult(
            minimized_genome=None,
            original_steps=original_steps,
            minimized_steps=original_steps,
            evaluations_used=evaluations,
            failure_reproduced=False,
            history=["baseline failure not reproduced; nothing minimized"],
        )

    # ddmin: granularity-guided removal of subsets.
    granularity = 2
    while granularity <= len(current) and evaluations < max_evaluations:
        chunk = max(1, len(current) // granularity)
        removed_any = False
        offset = 0
        while offset < len(current) and evaluations < max_evaluations:
            subset = current[:offset] + current[offset + chunk:]
            if not subset:
                offset += chunk
                continue
            outcome = await persists(subset)
            if outcome:
                history.append(f"removed steps [{offset}:{offset + chunk}] (n={chunk})")
                current = subset
                removed_any = True
                # do not advance offset — same position, smaller list
            else:
                offset += chunk
        if removed_any:
            granularity = max(2, granularity - 1)  # re-test smaller chunks
        else:
            granularity *= 2
        if len(current) <= 1:
            break

    # Final verification: the failure must reproduce on the minimized chain
    # (product rule: a minimized test is only accepted when reproduced).
    if current and evaluations < max_evaluations:
        failure_reproduced = bool(await persists(current))
    else:
        failure_reproduced = bool(current)
    minimized = (
        AudioGenome(
            persona_id=genome.persona_id,
            seed_audio_ref=genome.seed_audio_ref,
            seed_transcript=genome.seed_transcript,
            seed_language=genome.seed_language,
            transform_chain=current,
            content_mutations=list(genome.content_mutations),
            generation=genome.generation,
            parent_ids=list(genome.parent_ids),
            seed=genome.seed,
        )
        if current
        else None
    )
    return MinimizationResult(
        minimized_genome=minimized,
        original_steps=original_steps,
        minimized_steps=len(current),
        evaluations_used=evaluations,
        failure_reproduced=failure_reproduced,
        history=history,
    )


def persona_label(persona_id: str) -> str:
    persona = AUDIO_PERSONAS.get(persona_id)
    return persona.name if persona else persona_id
