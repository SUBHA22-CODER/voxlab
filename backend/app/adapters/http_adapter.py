"""HTTP agent adapter.

Contract (documented in docs/api-reference.md):

    POST <agent endpoint>
    {
      "session_id": "string",
      "message": "string",
      "metadata": {"interrupt": bool?, "inject": {...}?, "signal": "silence"?}
    }
    ->
    200
    {
      "reply": "string",
      "tool_calls": [{"name": ..., "args": ..., "status": ..., "duration_ms": ...}],
      "state": {...},
      "timings": {"llm_ms": ..., "tool_ms": ..., "total_ms": ...},
      "error": "string | null"
    }
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.adapters.base import AgentTurnResult, VoiceAgentAdapter


class HTTPAgentAdapter(VoiceAgentAdapter):
    def __init__(self, agent_config: dict, auth_config: dict | None = None, client: httpx.AsyncClient | None = None):
        super().__init__(agent_config, auth_config)
        self._client = client
        self.timeout_s = float(agent_config.get("timeout_s", 30))

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout_s)
        return self._client

    async def connect(self) -> None:
        await self._ensure_client()

    async def send_message(
        self, message: str, metadata: dict | None = None
    ) -> AgentTurnResult:
        payload: dict[str, Any] = {
            "session_id": self.agent_config.get("session_id", "vx-default-session"),
            "message": message,
            "metadata": metadata or {},
        }
        client = await self._ensure_client()
        started = time.perf_counter()
        try:
            response = await client.post(
                self.agent_config["endpoint"],
                json=payload,
                headers=self.auth_headers(),
            )
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException:
            return AgentTurnResult(error="timeout", timings={"total_ms": int((time.perf_counter() - started) * 1000)})
        except httpx.HTTPStatusError as exc:
            return AgentTurnResult(
                error=f"http_{exc.response.status_code}",
                timings={"total_ms": int((time.perf_counter() - started) * 1000)},
            )
        except httpx.HTTPError as exc:
            return AgentTurnResult(
                error=f"connection_error: {exc.__class__.__name__}",
                timings={"total_ms": int((time.perf_counter() - started) * 1000)},
            )
        except ValueError:
            return AgentTurnResult(
                error="invalid_json_response",
                timings={"total_ms": elapsed_ms},
            )

        return AgentTurnResult(
            reply=str(data.get("reply") or ""),
            tool_calls=list(data.get("tool_calls") or []),
            state=dict(data.get("state") or {}),
            timings={**(data.get("timings") or {}), "total_ms": data.get("timings", {}).get("total_ms", elapsed_ms)},
            error=data.get("error"),
            interrupted=bool(data.get("interrupted")),
            raw=data,
        )

    async def send_audio(
        self, audio: bytes, metadata: dict | None = None
    ) -> AgentTurnResult:
        # MVP: audio turns are transcribed client-side (Web Speech API) and
        # delivered as text. Kept on the interface for provider adapters.
        raise NotImplementedError("HTTP adapter accepts text turns only in MVP")

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
