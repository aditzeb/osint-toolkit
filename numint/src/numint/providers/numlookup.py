"""NumLookupAPI provider - free tier.

Returns carrier, line type, location and country.
Get a free key: https://www.numlookupapi.com/
"""

from __future__ import annotations

import httpx

from ..core.models import ParsedNumber, ProviderResult
from ..core.registry import register
from .base import BaseProvider

_LINE_TYPE_MAP = {
    "mobile": "mobile",
    "landline": "fixed_line",
    "fixed_line": "fixed_line",
    "voip": "voip",
    "toll_free": "toll_free",
    "toll free": "toll_free",
}


@register
class NumLookupProvider(BaseProvider):
    name = "numlookupapi"
    requires_key = True
    env_key = "NUMLOOKUPAPI_API_KEY"
    signup_url = "https://www.numlookupapi.com/"

    async def _lookup(
        self, number: ParsedNumber, client: httpx.AsyncClient
    ) -> ProviderResult:
        resp = await client.get(
            f"https://api.numlookupapi.com/v1/validate/{number.e164}",
            params={"apikey": self.api_key()},
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("valid") is None and ("message" in data or "error" in data):
            return ProviderResult(
                source=self.name,
                ok=False,
                raw=data,
                error=data.get("message") or str(data.get("error")),
            )

        mapped = {
            "valid": data.get("valid"),
            "carrier": data.get("carrier") or None,
            "line_type": _LINE_TYPE_MAP.get(
                (data.get("line_type") or "").lower()
            ),
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
