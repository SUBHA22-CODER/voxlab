# tts.py
# Minimal offline text-to-speech used by the Darwin audio engine to synthesize
# SEED audio (and content-mutated variants of it) from reference transcripts.
#
# Implementation: Windows SAPI via PowerShell (built into Windows, fully
# offline, a default synthetic voice — never a clone of a real person; product
# rule: no deceptive impersonations, no unauthorized voice cloning).
#
# On non-Windows platforms `is_available()` is False and callers skip honestly;
# VoxLab never requires TTS for core functionality (AGENTS.md determinism rule).

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from .exceptions import SpeechError

logger = logging.getLogger(__name__)

_SAPI_SCRIPT_TEMPLATE = (
    "Add-Type -AssemblyName System.Speech; "
    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    "$s.SetOutputToWaveFile('{path}'); "
    "$s.Rate = {rate}; "
    "$s.Speak({quoted}); "
    "$s.Dispose()"
)


class TTSError(SpeechError):
    """Speech synthesis failed."""


def is_available() -> bool:
    """True only on Windows with PowerShell reachable (checked cheaply)."""
    return sys.platform == "win32"


def _ps_quote(text: str) -> str:
    """Single-quote PS string with embedded-quote doubling."""
    return "'" + text.replace("'", "''") + "'"


async def synthesize_to_wav(
    text: str,
    destination: Path,
    rate: int = 0,
    timeout_seconds: float = 60.0,
) -> Path:
    """Synthesize `text` to a 16-bit PCM WAV file at the SAPI default rate.

    Returns the destination path. Raises TTSError with the tool's stderr on
    failure — failures are never swallowed.
    """
    if not text.strip():
        raise TTSError("Refusing to synthesize empty text.")
    if not is_available():
        raise TTSError(
            "Offline TTS is only available on Windows (SAPI). Provide seed "
            "audio as an uploaded file instead."
        )
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    script = _SAPI_SCRIPT_TEMPLATE.format(
        path=destination.resolve().as_posix(), rate=int(rate), quoted=_ps_quote(text)
    )
    try:
        process = await asyncio.create_subprocess_exec(
            "powershell", "-NoProfile", "-Command", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await asyncio.wait_for(process.communicate(), timeout_seconds)
    except TimeoutError as exc:
        raise TTSError(f"SAPI synthesis timed out after {timeout_seconds:.0f}s.") from exc
    except OSError as exc:
        raise TTSError(f"Failed to launch PowerShell for SAPI synthesis: {exc}") from exc

    if process.returncode != 0 or not destination.exists():
        detail = stderr.decode("utf-8", errors="replace").strip()
        raise TTSError(f"SAPI synthesis failed (rc={process.returncode}): {detail}")
    return destination
