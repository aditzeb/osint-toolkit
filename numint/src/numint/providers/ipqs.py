"""IPQualityScore (IPQS) provider - free tier. The risk / reputation layer.

Returns fraud score, spam status, line type, carrier, active status and
recent-abuse signals.
Get a free key: https://www.ipqualityscore.com/create-account
"""

from __future__ import annotations

import httpx

from ..core.models import ParsedNumber, ProviderResult
from ..core.registry import register
from .base import BaseProvider

_LINE_TYPE_MAP = {
    "Wireless": "mobile",
    "Landline": "fixed_line",
    "VOIP": "voip",
    "Toll Free": "toll_free",
}


@register
class IPQSProvider(BaseProvider):
    name = "ipqs"
    requires_key = True
    env_key = "IPQS_API_KEY"
    signup_url = "https://www.ipqualityscore.com/create-account"

    async def _lookup(
        self, number: ParsedNumber, client: httpx.AsyncClient
    ) -> ProviderResult:
        resp = await client.get(
            f"https://ipqualityscore.com/api/json/phone/{self.api_key()}/{number.digits}"
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success", False):
            return ProviderResult(
                source=self.name,
                ok=False,
                raw=data,
                error=data.get("message", "IPQS error"),
            )

        mapped = {
            "valid": data.get("valid"),
            "carrier": data.get("carrier") or None,
            "line_type": _LINE_TYPE_MAP.get(data.get("line_type") or ""),
            "country": data.get("country") or None,
            "country_iso": data.get("country") or None,
            "location": ", ".join(
                p for p in (data.get("city"), data.get("region")) if p
            )
            or None,
            # Risk signals - the reason this provider exists.
            "fraud_score": data.get("fraud_score"),
            "spam": data.get("spammer"),
            "voip": data.get("VOIP"),
            "disposable": data.get("prepaid"),
            "active": data.get("active"),
            "recent_abuse": data.get("recent_abuse"),
        }
        return ProviderResult(
            source=self.name,
            ok=True,
            raw=data,
            mapped={k: v for k, v in mapped.items() if v is not None},
        )
