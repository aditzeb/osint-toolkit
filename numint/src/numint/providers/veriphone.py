"""Veriphone provider - free tier.

Returns validity, carrier, line type, region and country.
Get a free key: https://veriphone.io/
"""

from __future__ import annotations

import httpx

from ..core.models import ParsedNumber, ProviderResult
from ..core.registry import register
from .base import BaseProvider

_LINE_TYPE_MAP = {
    "MOBILE": "mobile",
    "FIXED_LINE": "fixed_line",
    "FIXED_LINE_OR_MOBILE": "fixed_or_mobile",
    "VOIP": "voip",
    "TOLL_FREE": "toll_free",
    "PREMIUM_RATE": "premium_rate",
    "SHARED_COST": "shared_cost",
    "PERSONAL_NUMBER": "personal",
    "PAGER": "pager",
    "UAN": "uan",
    "VOICEMAIL": "voicemail",
    "UNKNOWN": "unknown",
}


@register
class VeriphoneProvider(BaseProvider):
    name = "veriphone"
    requires_key = True
    env_key = "VERIPHONE_API_KEY"
    signup_url = "https://veriphone.io/"

    async def _lookup(
        self, number: ParsedNumber, client: httpx.AsyncClient
    ) -> ProviderResult:
        resp = await client.get(
            "https://api.veriphone.io/v2/verify",
            params={"key": self.api_key(), "phone": number.e164},
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "success":
            return ProviderResult(
                source=self.name,
                ok=False,
                raw=data,
                error=data.get("status") or "Veriphone error",
            )

        mapped = {
            "valid": data.get("phone_valid"),
            "carrier": data.get("carrier") or None,
            "line_type": _LINE_TYPE_MAP.get(data.get("phone_type") or ""),
            "location": data.get("phone_region") or None,
            "country": data.get("country") or None,
            "country_iso": data.get("country_code") or None,
        }
        return ProviderResult(
            source=self.name,
            ok=True,
            raw=data,
            mapped={k: v for k, v in mapped.items() if v not in (None, "")},
        )
