"""Minimal in-memory sliding-window rate limiter for auth endpoints.

Sufficient for the single-process MVP (brute-force protection on
login/register). Swap for Redis-based limiting when running multiple
workers.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

WINDOW_SECONDS = 60.0
MAX_REQUESTS = 15
_MAX_TRACKED_CLIENTS = 10_000

_hits: dict[str, deque[float]] = defaultdict(deque)


def _prune(now: float) -> None:
    if len(_hits) <= _MAX_TRACKED_CLIENTS:
        return
    stale = [ip for ip, hits in _hits.items() if not hits or now - hits[-1] > WINDOW_SECONDS]
    for ip in stale:
        _hits.pop(ip, None)


async def auth_rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/auth"):
        now = time.monotonic()
        client_ip = request.client.host if request.client else "unknown"
        _prune(now)

        hits = _hits[client_ip]
        while hits and now - hits[0] > WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= MAX_REQUESTS:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please wait a minute and try again."},
            )
        hits.append(now)
    return await call_next(request)
