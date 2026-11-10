# vosk/
# Vosk (Kaldi) engine adapter — VoxLab's second speech engine (VoxLab 2.5).
# CPU-first, fully offline, genuinely streaming-capable decode.

from .adapter import DEFAULT_MODEL_NAME, DEFAULT_MODEL_REPO, VoskEngine

__all__ = ["DEFAULT_MODEL_NAME", "DEFAULT_MODEL_REPO", "VoskEngine"]
