"""Failure configuration for the Wispr Flow dictation demo agent."""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULTS = {
    "ignore_self_corrections": False,
    "strip_fillers": True,
    "literal_period_handling": False,
    "mangle_names": False,
}

_CONFIG_PATH = Path(__file__).resolve().parent / "failure_config.json"
_state: dict = {}


def load() -> dict:
    data = dict(DEFAULTS)
    if _CONFIG_PATH.exists():
        try:
            raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            data.update({k: v for k, v in raw.items() if not k.startswith("_")})
        except (json.JSONDecodeError, OSError):
            pass
    if os.environ.get("VOXLAB_NO_FAILURES") == "1":
        data = {k: False for k in data}
        data["strip_fillers"] = True
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
        pass
    return dict(_state)
