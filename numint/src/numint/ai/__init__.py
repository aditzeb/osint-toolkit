"""AI intelligence layer package.

Exposes `run_ai_analysis` and `answer_question`, which orchestrate the
configured LLM adapter over data the tool already collected. If no provider is
configured, callers get None and the tool proceeds normally.
"""

from __future__ import annotations

import json

from ..core.config import Settings
from ..core.logging import get_logger
from ..core.models import AIAnalysis, Profile
from .base import LLMProvider, resolve_llm
from .prompts import (
    ASK_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_analysis_user_prompt,
    build_ask_user_prompt,
)

log = get_logger("ai")

__all__ = ["run_ai_analysis", "answer_question", "resolve_llm", "LLMProvider"]


def _parse_json_block(text: str) -> dict:
    """Best-effort extraction of a JSON object from a model response."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {"summary": text}


async def run_ai_analysis(
    profile: Profile, settings: Settings
) -> AIAnalysis | None:
    """Produce the structured AI Analysis section, or None if AI is disabled."""
    llm = resolve_llm(settings)
    if llm is None:
        return None
    try:
        raw = await llm.complete(
            SYSTEM_PROMPT, build_analysis_user_prompt(profile)
        )
        parsed = _parse_json_block(raw)
        return AIAnalysis(
            provider=llm.name,
            model=llm.model(),
            summary=parsed.get("summary"),
            conflicts=parsed.get("conflicts"),
            risk_read=parsed.get("risk_read"),
            next_steps=parsed.get("next_steps"),
        )
    except Exception as exc:
        log.warning("AI analysis failed: %s", exc)
        return AIAnalysis(
            provider=llm.name,
            model=llm.model(),
            error=f"AI analysis unavailable: {exc.__class__.__name__}",
        )


async def answer_question(
    profile: Profile, question: str, settings: Settings
) -> AIAnalysis | None:
    """Answer a --ask question strictly from collected data."""
    llm = resolve_llm(settings)
    if llm is None:
        return None
    try:
        answer = await llm.complete(
            ASK_SYSTEM_PROMPT, build_ask_user_prompt(profile, question)
        )
        return AIAnalysis(provider=llm.name, model=llm.model(), answer=answer)
    except Exception as exc:
        log.warning("AI question failed: %s", exc)
        return AIAnalysis(
            provider=llm.name,
            model=llm.model(),
            error=f"AI unavailable: {exc.__class__.__name__}",
        )
