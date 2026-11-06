"""Offline baseline provider - always active, requires no key.

Re-exposes the libphonenumber-derived facts through the normal provider channel
so the aggregator treats it uniformly with online sources.
"""

from __future__ import annotations

import httpx

from ..core.models import ParsedNumber, ProviderResult
from ..core.registry import register
from .base import BaseProvider


@register
class OfflineProvider(BaseProvider):
    name = "offline"
    requires_key = False
    env_key = None

    async def _lookup(
        self, number: ParsedNumber, client: httpx.AsyncClient
    ) -> ProviderResult:
        mapped = {
            "valid": number.is_valid,
            "line_type": number.number_type.value,
            "country": number.country_name,
            "country_iso": number.country_iso,
            "location": number.region,
            "carrier": number.carrier,
            "timezones": number.timezones,
        }
        return ProviderResult(
            source=self.name,
            ok=True,
            raw=number.model_dump(mode="json"),
            mapped={k: v for k, v in mapped.items() if v not in (None, "", [])},
        )
