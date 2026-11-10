# limits.py
# Single source of truth for hard engine limits. The Darwin budget cap was
# previously duplicated (api/darwin.py and darwin/evolution.py could drift);
# both text and audio Darwin now read it from here.

from __future__ import annotations

import os

DARWIN_MAX_SESSIONS_DEFAULT = 60


def max_darwin_sessions() -> int:
    """Effective session budget: DARWIN_MAX_SESSIONS env override, default 60.

    A "session" is one evaluated candidate (one agent conversation for text
    Darwin, one transcription for audio Darwin). The cap is a hard ceiling —
    engines must stop, never bypass it.
    """
    raw = os.environ.get("DARWIN_MAX_SESSIONS", "")
    try:
        value = int(raw) if raw else DARWIN_MAX_SESSIONS_DEFAULT
    except ValueError:
        value = DARWIN_MAX_SESSIONS_DEFAULT
    return max(1, value)


def clamp_generations(population_size: int, generations: int) -> int:
    """population_size * generations <= budget; shrink generations first."""
    budget = max_darwin_sessions()
    if population_size * generations <= budget:
        return generations
    return max(1, budget // max(1, population_size))
