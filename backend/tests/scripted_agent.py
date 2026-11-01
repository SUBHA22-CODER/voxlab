"""A scripted in-process agent used to exercise the pipeline without network."""

from __future__ import annotations

from app.adapters.base import AgentTurnResult, VoiceAgentAdapter


class ScriptedAgentAdapter(VoiceAgentAdapter):
    """Returns pre-programmed turns based on the exact user message."""

    def __init__(self, script: dict[str, dict] | None = None, default: dict | None = None):
        super().__init__({})
        self.script = script or {}
        self.default = default or {"reply": "I'm here to help."}
        self.connected = False
        self.turns: list[tuple[str, dict | None]] = []

    async def connect(self) -> None:
        self.connected = True

    async def send_message(
        self, message: str, metadata: dict | None = None
    ) -> AgentTurnResult:
        self.turns.append((message, metadata))
        spec = self.script.get(message, self.default)
        result = AgentTurnResult(
            reply=spec.get("reply", ""),
            tool_calls=spec.get("tool_calls", []),
            state=spec.get("state", {}),
            timings=spec.get("timings", {"llm_ms": 120, "tool_ms": 40, "total_ms": 200}),
            error=spec.get("error"),
            interrupted=spec.get("interrupted", False),
        )
        return result

    async def send_audio(self, audio: bytes, metadata: dict | None = None) -> AgentTurnResult:
        return AgentTurnResult(reply="audio unsupported")

    async def disconnect(self) -> None:
        self.connected = False
