# whisper_local/
# faster-whisper engine adapter, adapted from drajb/whisper-local (MIT).
# See adapter.py for the full attribution and pattern provenance.

from .adapter import ATTRIBUTION, WhisperLocalEngine
from .config import MODEL_SIZE_HINTS, WhisperLocalConfig, model_size_hint

__all__ = [
    "ATTRIBUTION",
    "WhisperLocalEngine",
    "WhisperLocalConfig",
    "MODEL_SIZE_HINTS",
    "model_size_hint",
]
