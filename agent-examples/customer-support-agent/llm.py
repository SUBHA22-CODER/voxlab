"""Optional LLM composition for the demo agent (LLM_DEMO_MODE=llm)."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("demo-agent")


class LLMClient:
    def __init__(self) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=os.environ.get("LLM_API_KEY", ""),
            base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
        )
        self.model = os.environ.get("LLM_MODEL", "gpt-4o-mini")

    async def complete(self, context: str, history: list[dict], message: str) -> str:
        messages = [{"role": "system", "content": context}]
        for turn in history[-8:]:
            role = "assistant" if turn["role"] == "agent" else "user"
            messages.append({"role": role, "content": turn["content"]})
        messages.append({"role": "user", "content": message})
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=200,
                temperature=0.3,
            )
            content = response.choices[0].message.content
            return (content or "").strip()
        except Exception as exc:  # noqa: BLE001 — demo agent degrades, never raises
            logger.warning("LLM completion failed, replying with fallback: %s", exc)
            return "I'm sorry, I didn't catch that. Could you repeat it?"
