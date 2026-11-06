"""OpenAI (GPT) LLM adapter."""

from __future__ import annotations

import httpx

from .base import LLMProvider, register_llm


@register_llm
class OpenAIProvider(LLMProvider):
    name = "openai"
    env_key = "OPENAI_API_KEY"
    default_model = "gpt-4o-mini"

    async def complete(self, system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key()}"},
                json={
                    "model": self.model(),
                    "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
