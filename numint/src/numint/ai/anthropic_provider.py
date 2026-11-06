"""Anthropic (Claude) LLM adapter."""

from __future__ import annotations

import httpx

from .base import LLMProvider, register_llm


@register_llm
class AnthropicProvider(LLMProvider):
    name = "anthropic"
    env_key = "ANTHROPIC_API_KEY"
    default_model = "claude-sonnet-5"

    async def complete(self, system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key() or "",
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model(),
                    "max_tokens": 1024,
                    "temperature": 0.2,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            parts = [
                block.get("text", "")
                for block in data.get("content", [])
                if block.get("type") == "text"
            ]
            return "".join(parts).strip()
