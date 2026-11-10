"""Path-scoped sliding-window rate limiter (in-memory, single process).

Rules are matched by path prefix: auth rules protect credentials,
expensive-audio rules protect CPU-heavy transcription endpoints. Swap for
Redis-based limiting when running multiple workers (documented boundary).
TEST_OVERRIDE_LIMIT, when set, replaces every rule's limit (used by tests).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

_MAX_TRACKED_CLIENTS = 10_000
TEST_OVERRIDE_LIMIT: int | None = None

# (path prefix, window seconds, max requests) — first match wins.
RULES: list[tuple[str, float, int]] = [
    ("/api/auth", 60.0, 15),
    ("/api/v1/darwin/audio/evolve", 60.0, 10),
    ("/api/v1/audio/transcribe", 60.0, 30),
    ("/api/v1/benchmarks/audio", 60.0, 10),
]

_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def _prune(now: float) -> None:
    if len(_hits) <= _MAX_TRACKED_CLIENTS:
        return
    stale = [key for key, hits in _hits.items() if not hits or now - hits[-1] > 240.0]
    for key in stale:
        _hits.pop(key, None)


def _match(path: str) -> tuple[str, float, int] | None:
    for prefix, window, limit in RULES:
        if path.startswith(prefix):
            return prefix, window, TEST_OVERRIDE_LIMIT if TEST_OVERRIDE_LIMIT is not None else limit
    return None


async def auth_rate_limit_middleware(request: Request, call_next):
    matched = _match(request.url.path)
    if matched is not None:
        prefix, window, limit = matched
        now = time.monotonic()
        client_ip = request.client.host if request.client else "unknown"
        _prune(now)

        key = (prefix, client_ip)
        hits = _hits[key]
        while hits and now - hits[0] > window:
            hits.popleft()
        if len(hits) >= limit:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please wait a minute and try again."
                },
            )
        hits.append(now)
    return await call_next(request)
