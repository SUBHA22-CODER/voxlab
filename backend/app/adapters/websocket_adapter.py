"""WebSocket agent adapter for real-time streaming agents.

Frame contract:
    -> {"type": "user_message", "session_id": ..., "content": ..., "metadata": {...}}
    <- {"type": "agent_response", "reply": ..., "tool_calls": [...], "state": {...},
        "timings": {...}, "error": null}
    <- {"type": "error", "message": ...}
"""

from __future__ import annotations

import asyncio
import json
import time

import websockets  # provided via uvicorn[standard]

from app.adapters.base import AgentTurnResult, VoiceAgentAdapter


class WebSocketAgentAdapter(VoiceAgentAdapter):
    def __init__(self, agent_config: dict, auth_config: dict | None = None):
        super().__init__(agent_config, auth_config)
        self._ws = None
        self.timeout_s = float(agent_config.get("timeout_s", 30))

    async def connect(self) -> None:
        headers = self.auth_headers()
        # websockets accepts extra headers for the handshake.
        self._ws = await websockets.connect(
            self.agent_config["endpoint"],
            additional_headers=headers or None,
            open_timeout=self.timeout_s,
        )

    async def _recv_until(self, want_types: set[str]) -> dict:
        assert self._ws is not None
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            remaining = max(deadline - time.monotonic(), 0.1)
            try:
                frame = await asyncio.wait_for(self._ws.recv(), timeout=remaining)
            except asyncio.TimeoutError as exc:
                raise TimeoutError("agent websocket response timed out") from exc
            data = json.loads(frame)
            if data.get("type") in want_types:
                return data
        raise TimeoutError("agent websocket response timed out")

    async def send_message(
        self, message: str, metadata: dict | None = None
    ) -> AgentTurnResult:
        if self._ws is None:
            await self.connect()
        started = time.perf_counter()
        await self._ws.send(
            json.dumps(
                {
                    "type": "user_message",
                    "session_id": self.agent_config["session_id"],
                    "content": message,
                    "metadata": metadata or {},
                }
            )
        )
        try:
            data = await self._recv_until({"agent_response", "error"})
        except (TimeoutError, Exception) as exc:  # noqa: BLE001 — normalize to result
            return AgentTurnResult(
                error=f"websocket_error: {exc}",
                timings={"total_ms": int((time.perf_counter() - started) * 1000)},
            )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if data.get("type") == "error":
            return AgentTurnResult(error=data.get("message", "agent_error"), timings={"total_ms": elapsed_ms})
        return AgentTurnResult(
            reply=str(data.get("reply") or ""),
            tool_calls=list(data.get("tool_calls") or []),
            state=dict(data.get("state") or {}),
            timings={**(data.get("timings") or {}), "total_ms": data.get("timings", {}).get("total_ms", elapsed_ms)},
            error=data.get("error"),
            raw=data,
        )

    async def send_audio(
        self, audio: bytes, metadata: dict | None = None
    ) -> AgentTurnResult:
        if self._ws is None:
            await self.connect()
        await self._ws.send(audio)  # binary audio passthrough
        try:
            data = await self._recv_until({"agent_response", "error"})
        except Exception as exc:  # noqa: BLE001
            return AgentTurnResult(error=f"websocket_error: {exc}")
        return AgentTurnResult(
            reply=str(data.get("reply") or ""),
            tool_calls=list(data.get("tool_calls") or []),
            state=dict(data.get("state") or {}),
            timings=data.get("timings") or {},
            error=data.get("error"),
        )

    async def disconnect(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
