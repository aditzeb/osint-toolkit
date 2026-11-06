"""Google (Gemini) LLM adapter."""

from __future__ import annotations

import httpx

from .base import LLMProvider, register_llm


@register_llm
class GeminiProvider(LLMProvider):
    name = "gemini"
    env_key = "GEMINI_API_KEY"
    default_model = "gemini-1.5-flash"

    async def complete(self, system: str, user: str) -> str:
        model = self.model()
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                params={"key": self.api_key()},
                json={
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": user}]}],
                    "generationConfig": {"temperature": 0.2},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return ""
            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts).strip()
