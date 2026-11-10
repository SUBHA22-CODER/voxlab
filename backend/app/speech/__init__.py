# speech/
# VoxLab 2.0 speech engine layer: modular STT adapters, audio validation,
# transcription metrics, and reproducible audio transformations.
#
# Speech-recognition core adapted from whisper-local
# (https://github.com/drajb/whisper-local, MIT) — attribution retained per
# its license: Copyright (c) 2025 Pin Wang (original whisper-key-local),
# Copyright (c) 2026 Rohit Burani (whisper-local fork and modifications).

from .base import (
    AudioData,
    EngineCapabilities,
    EngineHealth,
    EngineMetadata,
    PartialTranscription,
    SpeechEngine,
    TranscriptionResult,
    TranscriptionSegment,
)
from .exceptions import (
    AudioCorrupt,
    AudioTooLarge,
    AudioValidationError,
    EngineInitializationError,
    EngineNotInstalled,
    EngineTimeout,
    SpeechError,
    TranscriptionFailed,
    UnsupportedAudioFormat,
)

__all__ = [
    "AudioData",
    "EngineCapabilities",
    "EngineHealth",
    "EngineMetadata",
    "PartialTranscription",
    "SpeechEngine",
    "TranscriptionResult",
    "TranscriptionSegment",
    "AudioCorrupt",
    "AudioTooLarge",
    "AudioValidationError",
    "EngineInitializationError",
    "EngineNotInstalled",
    "EngineTimeout",
    "SpeechError",
    "TranscriptionFailed",
    "UnsupportedAudioFormat",
]
