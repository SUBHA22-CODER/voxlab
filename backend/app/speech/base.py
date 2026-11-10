# base.py
# Common contract every speech recognition engine must implement. The platform
# talks to engines only through this interface so additional engines
# (faster-whisper variants, Whisper API, NVIDIA Parakeet, ...) can be added
# without touching the evaluation / Darwin / benchmark layers.
#
# Design notes:
# - Methods are async where the implementation may block (model load, decode,
#   inference). Concrete adapters must offload CPU-bound work to a thread so
#   the FastAPI event loop is never stalled.
# - TranscriptionResult only ever carries data the engine actually produced:
#   segments/timestamps stay empty when the engine does not provide them, and
#   speaker labels are never fabricated (product rule: never fabricate).

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:  # pragma: no cover - avoids an import cycle, type-only use
    from .alignment import WordTiming

# --- audio container passed to engines ---------------------------------------

@dataclass
class AudioData:
    """Engine-ready audio: mono float32 samples at a known sample rate.

    This is the canonical contract every engine receives (mirrors the
    whisper-local WhisperEngine contract: mono float32 @ 16 kHz).
    """

    samples: np.ndarray  # mono float32, values in [-1.0, 1.0]
    sample_rate: int = 16_000
    duration_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.duration_seconds <= 0.0 and self.samples.size:
            self.duration_seconds = round(self.samples.size / self.sample_rate, 6)


# --- transcription outputs ----------------------------------------------------

@dataclass
class TranscriptionSegment:
    """One timestamped segment, exactly as reported by the engine."""

    start_seconds: float
    end_seconds: float
    text: str


@dataclass
class TranscriptionResult:
    """Standardized transcription output for every engine."""

    engine: str
    text: str
    language: str | None = None
    language_probability: float | None = None
    segments: list[TranscriptionSegment] = field(default_factory=list)
    duration_seconds: float = 0.0
    processing_time_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    # Engine-provided word timings (hypothesis-token aligned) when the engine
    # supports them; empty when not. NEVER fabricated.
    word_timings: list[WordTiming] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "text": self.text,
            "language": self.language,
            "language_probability": self.language_probability,
            "segments": [
                {
                    "start_seconds": s.start_seconds,
                    "end_seconds": s.end_seconds,
                    "text": s.text,
                }
                for s in self.segments
            ],
            "duration_seconds": self.duration_seconds,
            "processing_time_seconds": round(self.processing_time_seconds, 6),
            "metadata": self.metadata,
            "word_timings": [
                {"word_index": i, "start_seconds": w.start_seconds, "end_seconds": w.end_seconds,
                 "confidence": w.confidence}
                for i, w in enumerate(self.word_timings)
            ],
        }


@dataclass
class PartialTranscription:
    """A progressive partial result emitted by transcribe_stream()."""

    text: str
    is_final: bool
    chunk_index: int
    start_seconds: float
    end_seconds: float


# --- engine description --------------------------------------------------------

@dataclass
class EngineCapabilities:
    """What the engine can do, reported honestly (never aspirational)."""

    languages: list[str] | None = None  # None = multilingual / auto-detect
    supports_timestamps: bool = False
    supports_language_detection: bool = False
    streaming_mode: str = "none"  # "none" | "chunked_window" | "true"
    max_audio_duration_seconds: float | None = None


@dataclass
class EngineMetadata:
    engine_id: str
    display_name: str
    version: str | None = None
    model: str | None = None
    device: str | None = None
    compute_type: str | None = None
    attribution: str | None = None
    installed: bool = True


@dataclass
class EngineHealth:
    status: str  # "healthy" | "degraded" | "unavailable"
    detail: str
    model_loaded: bool = False


# --- the engine ABC -------------------------------------------------------------

class SpeechEngine(ABC):
    """Abstract speech-to-text engine.

    Implementations must be safe to construct without their runtime being
    installed only if `is_available()` returns False in that case; the registry
    relies on that to report availability honestly.
    """

    @classmethod
    @abstractmethod
    def engine_id(cls) -> str:
        """Stable identifier used in APIs and stored artifacts."""

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """True when the engine's runtime dependencies are importable."""

    #: Human-readable credit line (license attribution), surfaced by the API.
    ATTRIBUTION: str | None = None

    @classmethod
    def describe_capabilities(cls) -> EngineCapabilities:
        """Static capabilities without instantiating (registry listing must
        not trigger a model load). Subclasses may override."""
        return EngineCapabilities()

    @abstractmethod
    async def initialize(self) -> None:
        """Load models / allocate resources. Idempotent."""

    @abstractmethod
    async def health_check(self) -> EngineHealth:
        """Report whether the engine is ready to transcribe right now."""

    @abstractmethod
    async def transcribe(
        self,
        audio: AudioData,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe a complete AudioData buffer.

        Raises TranscriptionFailed on engine errors; empty text is a valid
        result for silent audio and is NOT an error.
        """

    @abstractmethod
    def transcribe_stream(
        self,
        audio: AudioData,
        chunk_seconds: float = 3.0,
    ) -> Iterator[PartialTranscription]:
        """Progressive transcription over audio chunks.

        Engines with a chunked-window strategy yield partials per window;
        engines without streaming support raise TranscriptionFailed. The
        capabilities' streaming_mode tells callers what to expect.
        """

    @abstractmethod
    def get_capabilities(self) -> EngineCapabilities:
        """Declare capabilities truthfully (checked by tests)."""

    @abstractmethod
    def get_metadata(self) -> EngineMetadata:
        """Describe the engine instance (model, device, version)."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Release resources. Idempotent."""
