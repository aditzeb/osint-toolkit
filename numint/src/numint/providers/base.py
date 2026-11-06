"""Provider plugin contract.

A data provider is a single file that subclasses `BaseProvider` and is decorated
with `@register`. Adding a new source is literally: drop one file in this package
and register it. The engine auto-discovers everything registered and only runs
providers that report `is_configured()`.
"""

from __future__ import annotations

import abc
import time

import httpx

from ..core.config import Settings
from ..core.models import ParsedNumber, ProviderResult, ProviderStatus


class BaseProvider(abc.ABC):
    """Abstract base for every external data provider."""

    #: Human-readable, stable identifier used as the source tag.
    name: str = "base"
    #: Whether the provider needs an API key to function.
    requires_key: bool = True
    #: Environment/config key that holds this provider's credential.
    env_key: str | None = None
    #: Whether the provider is advanced/optional (e.g. needs a full account).
    optional: bool = False
    #: Where a user gets the free key (shown in `providers` and the UI).
    signup_url: str | None = None

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def api_key(self) -> str | None:
        if not self.env_key:
            return None
        return self.settings.get(self.env_key)

    def is_configured(self) -> bool:
        """A provider is active when it needs no key, or its key is present."""
        if not self.requires_key:
            return True
        return bool(self.api_key())

    @abc.abstractmethod
    async def _lookup(
        self, number: ParsedNumber, client: httpx.AsyncClient
    ) -> ProviderResult:
        """Perform the actual lookup. Implemented per provider."""

    async def lookup(
        self, number: ParsedNumber, client: httpx.AsyncClient
    ) -> ProviderResult:
        """Wrap `_lookup` with timing and uniform error handling."""
        start = time.monotonic()
        try:
            result = await self._lookup(number, client)
        except httpx.HTTPError as exc:
            result = ProviderResult(
                source=self.name,
                ok=False,
                status=ProviderStatus.ERROR,
                error=f"HTTP error: {exc.__class__.__name__}",
            )
        except Exception as exc:  # never let one provider crash the scan
            result = ProviderResult(
                source=self.name,
                ok=False,
                status=ProviderStatus.ERROR,
                error=f"{exc.__class__.__name__}: {exc}",
            )
        result.elapsed_ms = int((time.monotonic() - start) * 1000)
        return result
