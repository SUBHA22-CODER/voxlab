"""Failure configuration for the demo agent.

Deliberate bugs are config, not code: flip a switch, rerun the benchmark,
watch the score move. Loaded once at startup; mutable at runtime via the
admin endpoints (the demo agent is a single-process demo, not a service).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULTS = {
    "ignore_interruptions": False,
    "crash_on_tool_error": False,
    "forget_context": False,
    "hinglish_support": True,
}

_CONFIG_PATH = Path(__file__).resolve().parent / "failure_config.json"

_state: dict = {}


def load() -> dict:
    """Load failure switches from disk (or defaults)."""
    data = dict(DEFAULTS)
    if _CONFIG_PATH.exists():
        try:
            raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            data.update({k: v for k, v in raw.items() if not k.startswith("_")})
        except (json.JSONDecodeError, OSError):
            pass  # fall back to defaults on a corrupt config
    # Env override wins (set VOXLAB_NO_FAILURES=1 to run the "fixed" agent).
    if os.environ.get("VOXLAB_NO_FAILURES") == "1":
        data = {k: False for k in data}
    _state.clear()
    _state.update(data)
    return dict(_state)


def get() -> dict:
    if not _state:
        return load()
    return dict(_state)


def update(partial: dict) -> dict:
    for key in DEFAULTS:
        if key in partial and isinstance(partial[key], bool):
            _state[key] = partial[key]
    try:
        persistable = {"_comment": "Managed via /admin/failure-config", **_state}
        _CONFIG_PATH.write_text(json.dumps(persistable, indent=2), encoding="utf-8")
    except OSError:
        pass  # demo agent: in-memory switch still applies
    return dict(_state)
