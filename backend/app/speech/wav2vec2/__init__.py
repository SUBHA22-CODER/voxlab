# wav2vec2/
# Wav2Vec 2.0 (CTC) engine adapter — VoxLab's third speech engine (VoxLab 2.5).
# Self-supervised acoustic representations with a non-autoregressive CTC head.

from .adapter import DEFAULT_MODEL_NAME, Wav2Vec2Engine

__all__ = ["DEFAULT_MODEL_NAME", "Wav2Vec2Engine"]

