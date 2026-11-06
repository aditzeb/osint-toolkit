"""Twilio Lookup provider - OPTIONAL / advanced (needs a Twilio account).

Provides Line Type Intelligence and, where available, caller name (CNAM).
Uses HTTP Basic auth with Account SID + Auth Token. Free trial credit applies.
Set both TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN.
Get started: https://www.twilio.com/try-twilio
"""

from __future__ import annotations

import httpx

from ..core.models import ParsedNumber, ProviderResult
from ..core.registry import register
from .base import BaseProvider

_LINE_TYPE_MAP = {
    "mobile": "mobile",
    "landline": "fixed_line",
    "fixedVoip": "voip",
    "nonFixedVoip": "voip",
    "tollFree": "toll_free",
    "voip": "voip",
}


@register
class TwilioProvider(BaseProvider):
    name = "twilio"
    requires_key = True
    env_key = "TWILIO_ACCOUNT_SID"  # token checked separately below
    optional = True
    signup_url = "https://www.twilio.com/try-twilio"

    def is_configured(self) -> bool:
        return bool(
            self.settings.get("TWILIO_ACCOUNT_SID")
            and self.settings.get("TWILIO_AUTH_TOKEN")
        )

    async def _lookup(
        self, number: ParsedNumber, client: httpx.AsyncClient
    ) -> ProviderResult:
        sid = self.settings.get("TWILIO_ACCOUNT_SID")
        token = self.settings.get("TWILIO_AUTH_TOKEN")
        resp = await client.get(
            f"https://lookups.twilio.com/v2/PhoneNumbers/{number.e164}",
            params={"Fields": "line_type_intelligence,caller_name"},
            auth=(sid, token),  # type: ignore[arg-type]
        )
        resp.raise_for_status()
        data = resp.json()

        lti = data.get("line_type_intelligence") or {}
        caller = data.get("caller_name") or {}
        mapped = {
            "valid": data.get("valid"),
            "carrier": lti.get("carrier_name") or None,
            "line_type": _LINE_TYPE_MAP.get(lti.get("type") or ""),
            "country": data.get("country_code") or None,
            "country_iso": data.get("country_code") or None,
            "caller_name": caller.get("caller_name") or None,
        }
        return ProviderResult(
            source=self.name,
            ok=True,
            raw=data,
            mapped={k: v for k, v in mapped.items() if v not in (None, "")},
        )
