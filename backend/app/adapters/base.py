"""Voice agent adapter interface (spec Module A).

Every integration translates provider-specific behavior into VoxLab's
internal event format via `AgentTurnResult`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AgentTurnResult:
    """Normalized result of one conversational turn with an agent."""

    reply: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    state: dict = field(default_factory=dict)
    timings: dict = field(default_factory=dict)
    error: str | None = None
    interrupted: bool = False
    raw: dict = field(default_factory=dict)


class VoiceAgentAdapter(ABC):
    """Standard adapter interface every agent framework plugs into."""

    def __init__(self, agent_config: dict, auth_config: dict | None = None):
        self.agent_config = agent_config
        self.auth_config = auth_config or {}

    @abstractmethod
    async def connect(self) -> None:
        """Establish a connection to the agent."""

    @abstractmethod
    async def send_message(
        self, message: str, metadata: dict | None = None
    ) -> AgentTurnResult:
        """Send a user utterance (text) and await the agent's turn result."""

    @abstractmethod
    async def send_audio(
        self, audio: bytes, metadata: dict | None = None
    ) -> AgentTurnResult:
        """Send a user audio chunk and await the agent's turn result."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Tear down the connection."""

    def auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.auth_config.get("type") == "bearer" and self.auth_config.get("token"):
            headers["Authorization"] = f"Bearer {self.auth_config['token']}"
        headers.update(self.auth_config.get("headers") or {})
        return headers


def build_adapter(agent_config: dict, auth_config: dict | None = None) -> VoiceAgentAdapter:
    """Factory: pick the adapter for an agent row's type."""
    from app.adapters.http_adapter import HTTPAgentAdapter
    from app.adapters.websocket_adapter import WebSocketAgentAdapter

    agent_type = agent_config.get("agent_type", "http")
    if agent_type == "websocket":
        return WebSocketAgentAdapter(agent_config, auth_config)
    return HTTPAgentAdapter(agent_config, auth_config)
