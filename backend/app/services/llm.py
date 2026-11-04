"""LLM access via any OpenAI-compatible API.

Used by the evaluation engine's LLM judge. The demo agent ships its own
copy so it stays standalone.
"""

from __future__ import annotations

import json
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.llm_model
        self._client = None
        effective_key = api_key if api_key is not None else settings.llm_api_key
        effective_base_url = base_url or settings.llm_base_url
        if effective_key:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(
                    api_key=effective_key,
                    base_url=effective_base_url,
                    max_retries=1,
                    timeout=10.0,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to initialize LLM client: %s", exc)

    @property
    def available(self) -> bool:
        return self._client is not None

    async def complete(
        self,
        messages: list[dict],
        json_mode: bool = False,
        max_tokens: int = 700,
        temperature: float = 0.2,
    ) -> str | None:
        """Return completion text, or None when unavailable/failed."""
        if self._client is None:
            return None
        try:
            kwargs: dict = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            response = await self._client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            return content.strip() if content else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM completion failed: %s", exc)
            return None

    async def complete_json(self, messages: list[dict], max_tokens: int = 700) -> dict | None:
        text = await self.complete(messages, json_mode=True, max_tokens=max_tokens)
        if text is None:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Tolerate fenced JSON from providers without json_object support.
            stripped = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return None
