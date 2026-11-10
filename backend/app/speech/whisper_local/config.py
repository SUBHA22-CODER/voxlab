# config.py
# Configuration for the whisper_local engine, resolved from environment
# settings (app.core.config.Settings) with safe CPU-only defaults.
#
# Model size hints mirror whisper-local's first-run UX: the caller can tell
# the user *before* triggering a download roughly how large the model is.

from __future__ import annotations

from dataclasses import dataclass

MODEL_SIZE_HINTS: dict[str, str] = {
    "tiny": "~75 MB",
    "base": "~141 MB",
    "small": "~465 MB",
    "medium": "~1.5 GB",
    "large": "~3 GB",
    "distil": "~1.5 GB",
}

# Whisper models with a ".en" suffix are English-only and cannot auto-detect.
ENGLISH_ONLY_SUFFIX = ".en"

SUPPORTED_COMPUTE_TYPES = {"int8", "int8_float16", "float16", "float32", "auto"}


def model_size_hint(model_key: str) -> str:
    key = (model_key or "").lower()
    for prefix, size in MODEL_SIZE_HINTS.items():
        if key.startswith(prefix):
            return size
    return ""


def is_english_only(model_key: str) -> bool:
    return model_key.lower().endswith(ENGLISH_ONLY_SUFFIX)


@dataclass
class WhisperLocalConfig:
    """Runtime knobs for WhisperLocalEngine."""

    model_key: str = "base"
    device: str = "cpu"  # "cpu" | "cuda" (cuda only used when explicitly set)
    compute_type: str = "int8"
    beam_size: int = 5
    language: str | None = None  # None = auto-detect per clip
    vad_filter: bool = True  # Silero VAD inside faster-whisper (skips silence)
    timeout_seconds: float = 120.0
    word_timestamps: bool = False  # engine-provided per-word timings (Phase 4)
    cpu_threads: int = 0  # 0 = CTranslate2 default
    num_workers: int = 1

    def validate(self) -> None:
        if self.beam_size < 1:
            raise ValueError("beam_size must be >= 1")
        if self.compute_type not in SUPPORTED_COMPUTE_TYPES:
            raise ValueError(
                f"compute_type '{self.compute_type}' not in "
                f"{sorted(SUPPORTED_COMPUTE_TYPES)}"
            )
        if self.device not in {"cpu", "cuda", "auto"}:
            raise ValueError(f"device '{self.device}' must be cpu, cuda, or auto")

    @property
    def resolved_language(self) -> str | None:
        """None means auto-detect; explicit language always wins."""
        if self.language and self.language.lower() == "auto":
            return None
        return self.language
