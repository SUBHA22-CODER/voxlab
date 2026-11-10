# exceptions.py
# Exception hierarchy for the speech engine layer. Every failure mode that a
# caller (API route, Darwin audio loop, benchmark runner) needs to distinguish
# gets its own class so errors are never silently collapsed into a generic 500.

from __future__ import annotations


class SpeechError(Exception):
    """Base class for every speech-engine error."""


class AudioValidationError(SpeechError):
    """Audio input failed validation (empty, corrupt, too large, ...)."""


class UnsupportedAudioFormat(AudioValidationError):
    """The audio container or codec is not supported by any available decoder."""


class AudioTooLarge(AudioValidationError):
    """The upload exceeds the configured maximum size or duration."""


class AudioCorrupt(AudioValidationError):
    """The audio bytes could not be decoded (truncated container, bad header)."""


class EngineNotInstalled(SpeechError):
    """The engine's runtime dependency (e.g. faster-whisper) is not installed."""


class EngineInitializationError(SpeechError):
    """The engine failed to load its model or runtime."""


class EngineTimeout(SpeechError):
    """A transcription call exceeded the configured timeout."""


class TranscriptionFailed(SpeechError):
    """The engine ran but produced a hard failure (not merely empty text)."""
