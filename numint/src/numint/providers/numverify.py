"""Numverify (APILayer) provider - free ~100 requests/month.

Returns validity, carrier, line type, location and country.
Get a free key: https://numverify.com/
"""

from __future__ import annotations

import httpx

from ..core.models import ParsedNumber, ProviderResult
from ..core.registry import register
from .base import BaseProvider

_LINE_TYPE_MAP = {
    "mobile": "mobile",
    "landline": "fixed_line",
    "special_services": "premium_rate",
    "toll_free": "toll_free",
    "premium_rate": "premium_rate",
    "voip": "voip",
    "satellite": "unknown",
    "paging": "pager",
}


@register
class NumverifyProvider(BaseProvider):
    name = "numverify"
    requires_key = True
    env_key = "NUMVERIFY_API_KEY"
    signup_url = "https://numverify.com/product"

    async def _lookup(
        self, number: ParsedNumber, client: httpx.AsyncClient
    ) -> ProviderResult:
        resp = await client.get(
            "https://apilayer.net/api/validate",
            params={
                "access_key": self.api_key(),
                "number": number.e164,
                "format": 1,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("valid") and "error" in data:
            info = data["error"].get("info", "Numverify error")
            return ProviderResult(
                source=self.name, ok=False, raw=data, error=info
            )

        mapped = {
            "valid": data.get("valid"),
            "carrier": data.get("carrier") or None,
            "line_type": _LINE_TYPE_MAP.get(data.get("line_type") or ""),
            "location": data.get("location") or None,
            "country": data.get("country_name") or None,
            "country_iso": data.get("country_code") or None,
        }
        return ProviderResult(
            source=self.name,
            ok=True,
            raw=data,
            mapped={k: v for k, v in mapped.items() if v not in (None, "")},
        )
