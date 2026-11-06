"""LLM adapter interface - mirrors the data-provider plugin pattern.

The user configures exactly one provider via AI_PROVIDER + its key. If none is
set, the AI layer is silently disabled and the tool works normally.
"""

from __future__ import annotations

import abc

from ..core.config import Settings


class LLMProvider(abc.ABC):
    """Provider-agnostic chat adapter."""

    name: str = "base"
    env_key: str = ""
    default_model: str = ""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def api_key(self) -> str | None:
        return self.settings.get(self.env_key)

    def model(self) -> str:
        return self.settings.ai_model or self.default_model

    def is_configured(self) -> bool:
        return bool(self.api_key())

    @abc.abstractmethod
    async def complete(self, system: str, user: str) -> str:
        """Return the model's text response to a system + user prompt."""


_LLM_REGISTRY: dict[str, type[LLMProvider]] = {}


def register_llm(cls: type[LLMProvider]) -> type[LLMProvider]:
    _LLM_REGISTRY[cls.name] = cls
    return cls


def get_llm_classes() -> dict[str, type[LLMProvider]]:
    # Import implementations so they register.
    from . import anthropic_provider, gemini_provider, openai_provider  # noqa: F401

    return dict(_LLM_REGISTRY)


def resolve_llm(settings: Settings) -> LLMProvider | None:
    """Return the configured LLM provider, or None if AI is disabled."""
    classes = get_llm_classes()
    chosen = settings.ai_provider
    if chosen:
        cls = classes.get(chosen.lower())
        if cls:
            inst = cls(settings)
            return inst if inst.is_configured() else None
        return None
    # No explicit choice: auto-pick the first configured provider.
    for cls in classes.values():
        inst = cls(settings)
        if inst.is_configured():
            return inst
    return None
