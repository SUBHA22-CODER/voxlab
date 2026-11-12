# registry.py
# Engine discovery. Engines register lazily: the registry knows the adapter
# classes, asks each whether its runtime is importable, and only instantiates
# engines that are actually installed. A missing runtime is reported honestly
# ("available_engine": false + install hint) — the platform never pretends an
# uninstalled engine can transcribe.

from __future__ import annotations

import logging

from .base import SpeechEngine
from .exceptions import EngineNotInstalled

logger = logging.getLogger(__name__)


class EngineRegistry:
    def __init__(self) -> None:
        self._engine_classes: dict[str, type[SpeechEngine]] = {}
        self._instances: dict[str, SpeechEngine] = {}

    def register(self, engine_class: type[SpeechEngine]) -> None:
        engine_id = engine_class.engine_id()
        self._engine_classes[engine_id] = engine_class
        logger.debug("Registered speech engine: %s", engine_id)

    def known_engines(self) -> list[str]:
        return sorted(self._engine_classes)

    def is_installed(self, engine_id: str) -> bool:
        cls = self._engine_classes.get(engine_id)
        return bool(cls and cls.is_available())

    def install_hint(self, engine_id: str) -> str:
        if engine_id == "gnani_prisma":
            return (
                "Gnani Prisma STT requires GNANI_ENABLED=true and GNANI_API_KEY set in backend environment. "
                "See docs/GNANI_INTEGRATION.md"
            )
        if engine_id == "wav2vec2":
            return (
                f"Engine '{engine_id}' is known but its runtime is not installed. "
                "Install the speech extra: pip install -r requirements-speech-wav2vec2.txt"
            )
        if engine_id == "vosk":
            return (
                f"Engine '{engine_id}' is known but its runtime is not installed. "
                "Install the speech extra: pip install -r requirements-speech-vosk.txt"
            )
        return (
            f"Engine '{engine_id}' is known but its runtime is not installed. "
            "Install the speech extra: pip install -r requirements-speech.txt"
        )

    def get_engine(self, engine_id: str) -> SpeechEngine:
        """Return the shared instance, initializing it if needed (async-safe)."""
        cls = self._engine_classes.get(engine_id)
        if cls is None:
            raise EngineNotInstalled(f"Unknown speech engine: '{engine_id}'.")
        if not cls.is_available():
            raise EngineNotInstalled(self.install_hint(engine_id))

        instance = self._instances.get(engine_id)
        if instance is None:
            instance = cls()
            self._instances[engine_id] = instance
        return instance

    def describe_all(self) -> list[dict[str, object]]:
        """Status of every known engine, for the /api/v1/engines listing."""
        out: list[dict[str, object]] = []
        for engine_id in self.known_engines():
            cls = self._engine_classes[engine_id]
            installed = cls.is_available()
            entry: dict[str, object] = {
                "engine_id": engine_id,
                "installed": installed,
            }
            if installed:
                # Deliberately do NOT instantiate here (model load is expensive);
                # describe from class-level metadata only.
                from dataclasses import asdict

                entry["capabilities"] = asdict(cls.describe_capabilities())
                entry["attribution"] = getattr(cls, "ATTRIBUTION", None)
            else:
                entry["install_hint"] = self.install_hint(engine_id)
            out.append(entry)
        return out


def build_default_registry() -> EngineRegistry:
    """Registry with every adapter VoxLab ships. Import errors inside an
    adapter module are contained so one broken extra never breaks the API."""
    registry = EngineRegistry()
    try:
        from .whisper_local.adapter import WhisperLocalEngine

        registry.register(WhisperLocalEngine)
    except Exception as exc:  # noqa: BLE001 - defensive, contained
        logger.warning("whisper_local adapter could not be registered: %s", exc)
    try:
        from .vosk.adapter import VoskEngine

        registry.register(VoskEngine)
    except Exception as exc:  # noqa: BLE001 - defensive, contained
        logger.warning("vosk adapter could not be registered: %s", exc)
    try:
        from .wav2vec2.adapter import Wav2Vec2Engine

        registry.register(Wav2Vec2Engine)
    except Exception as exc:  # noqa: BLE001 - defensive, contained
        logger.warning("wav2vec2 adapter could not be registered: %s", exc)
    try:
        from ..providers.gnani.prisma_adapter import GnaniPrismaEngine

        registry.register(GnaniPrismaEngine)
    except Exception as exc:  # noqa: BLE001 - defensive, contained
        logger.warning("gnani_prisma adapter could not be registered: %s", exc)
    return registry


# Module-level singleton used by the API layer.
engine_registry = build_default_registry()
