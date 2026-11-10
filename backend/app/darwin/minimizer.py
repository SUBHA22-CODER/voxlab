"""Darwin Minimizer — Delta Debugging (ddmin) over scenario steps."""

from __future__ import annotations

import copy
import logging
from typing import Any
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


async def ddmin(
    steps: list[dict[str, Any]],
    test_fn: Callable[[list[dict[str, Any]]], Awaitable[bool]],
    max_evaluations: int = 20,
) -> list[dict[str, Any]]:
    """
    Classic Delta Debugging (ddmin) algorithm adapted for scenario steps.
    Finds a 1-minimal subset of steps that still triggers the failure predicate.

    test_fn returns True if the candidate step sequence reproduces the failure.
    Capped at max_evaluations to respect the budget model.
    """
    if len(steps) <= 1:
        return steps

    n = 2  # initial granularity
    current_steps = copy.deepcopy(steps)
    evaluations_used = 0

    while len(current_steps) >= 2 and evaluations_used < max_evaluations:
        subsets = _split_into_chunks(current_steps, n)
        reduced = False

        # 1. Test each subset (removing the rest)
        for sub in subsets:
            if not sub:
                continue
            evaluations_used += 1
            try:
                reproduces = await test_fn(sub)
            except Exception as exc:
                logger.warning("Minimizer test error: %s", exc)
                reproduces = False

            if reproduces:
                current_steps = sub
                n = max(n - 1, 2)
                reduced = True
                break
            if evaluations_used >= max_evaluations:
                break

        if reduced:
            continue

        # 2. Test the complement of each subset (removing sub)
        if evaluations_used < max_evaluations:
            for sub in subsets:
                complement = [s for s in current_steps if s not in sub]
                if not complement:
                    continue
                evaluations_used += 1
                try:
                    reproduces = await test_fn(complement)
                except Exception as exc:
                    logger.warning("Minimizer complement test error: %s", exc)
                    reproduces = False

                if reproduces:
                    current_steps = complement
                    n = max(n - 1, 2)
                    reduced = True
                    break
                if evaluations_used >= max_evaluations:
                    break

        if reduced:
            continue

        # 3. Increase granularity if cannot reduce further at level n
        if n == len(current_steps):
            break
        n = min(n * 2, len(current_steps))

    return current_steps


def _split_into_chunks(items: list[Any], n: int) -> list[list[Any]]:
    """Splits items into n approximately equal chunks."""
    if n <= 1:
        return [items]
    k, m = divmod(len(items), n)
    chunks = []
    start = 0
    for i in range(n):
        end = start + k + (1 if i < m else 0)
        chunks.append(items[start:end])
        start = end
    return [c for c in chunks if c]
