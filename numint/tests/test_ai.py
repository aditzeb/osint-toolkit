"""Tests for the LLM adapter layer, using mocks (no network)."""

from __future__ import annotations

import pytest

from numint.ai import answer_question, run_ai_analysis
from numint.ai.base import LLMProvider, register_llm, resolve_llm
from numint.core.aggregator import aggregate
from numint.core.config import Settings
from numint.core.models import ProviderResult
from numint.core.parser import parse_number


class _FakeSettings(Settings):
    def __init__(self, values: dict):
        self._values = values
        self._file = {}

    def get(self, key, default=None):
        return self._values.get(key, default)


@register_llm
class _MockLLM(LLMProvider):
    name = "mockllm"
    env_key = "MOCK_LLM_KEY"
    default_model = "mock-1"
    last_prompt = ""

    async def complete(self, system: str, user: str) -> str:
        _MockLLM.last_prompt = user
        return (
            '{"summary": "A valid US mobile.", "conflicts": "None", '
            '"risk_read": "Low risk.", "next_steps": "Try WhatsApp link."}'
        )


def _profile():
    number = parse_number("+14155552671")
    results = [ProviderResult(source="offline", ok=True, mapped={"valid": True})]
    return aggregate(number, results)


def test_resolve_llm_none_when_unconfigured():
    assert resolve_llm(_FakeSettings({})) is None


def test_resolve_llm_respects_ai_provider_choice():
    settings = _FakeSettings({"AI_PROVIDER": "mockllm", "MOCK_LLM_KEY": "k"})
    llm = resolve_llm(settings)
    assert llm is not None and llm.name == "mockllm"


def test_resolve_llm_disabled_when_chosen_provider_has_no_key():
    settings = _FakeSettings({"AI_PROVIDER": "mockllm"})
    assert resolve_llm(settings) is None


@pytest.mark.asyncio
async def test_run_ai_analysis_parses_json():
    settings = _FakeSettings({"AI_PROVIDER": "mockllm", "MOCK_LLM_KEY": "k"})
    ai = await run_ai_analysis(_profile(), settings)
    assert ai is not None
    assert ai.summary == "A valid US mobile."
    assert ai.next_steps == "Try WhatsApp link."
    assert ai.provider == "mockllm"


@pytest.mark.asyncio
async def test_run_ai_analysis_none_when_disabled():
    assert await run_ai_analysis(_profile(), _FakeSettings({})) is None


@pytest.mark.asyncio
async def test_ask_passes_question_and_returns_answer():
    settings = _FakeSettings({"AI_PROVIDER": "mockllm", "MOCK_LLM_KEY": "k"})
    ai = await answer_question(_profile(), "is this a real mobile?", settings)
    assert ai is not None
    assert "is this a real mobile?" in _MockLLM.last_prompt
    assert ai.answer  # mock returns the JSON string as the plain answer
