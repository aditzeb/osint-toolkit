"""AbstractAPI Phone Intelligence provider, free tier.

Returns validity, carrier, line type, location, and risk signals.
Get a free key: https://www.abstractapi.com/phone-validation-api
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
    "fixed": "fixed_line",
    "voip": "voip",
    "toll_free": "toll_free",
    "toll free": "toll_free",
    "premium_rate": "premium_rate",
}

# AbstractAPI reports a coarse risk level; map it to numint's 0-100 score.
_RISK_LEVEL_SCORE = {
    "low": 10,
    "medium": 50,
    "high": 85,
    "very_high": 95,
    "critical": 95,
}


@register
class AbstractAPIProvider(BaseProvider):
    name = "abstractapi"
    requires_key = True
    env_key = "ABSTRACTAPI_API_KEY"
    signup_url = "https://www.abstractapi.com/phone-validation-api"

    async def _lookup(
        self, number: ParsedNumber, client: httpx.AsyncClient
    ) -> ProviderResult:
        resp = await client.get(
            "https://phoneintelligence.abstractapi.com/v1/",
            params={"api_key": self.api_key(), "phone": number.e164},
        )
        resp.raise_for_status()
        data = resp.json()

        # Errors come back as a JSON object with an `error` key.
        if "error" in data:
            err = data["error"]
            msg = (
                err.get("message", "AbstractAPI error")
                if isinstance(err, dict)
                else str(err)
            )
            return ProviderResult(source=self.name, ok=False, raw=data, error=msg)

        carrier = data.get("phone_carrier") or {}
        location = data.get("phone_location") or {}
        validation = data.get("phone_validation") or {}
        risk = data.get("phone_risk") or {}

        # Build a human location like "Knoxville, Tennessee".
        loc_parts = [location.get("city"), location.get("region")]
        loc = ", ".join(p for p in loc_parts if p) or None

        line_status = (validation.get("line_status") or "").lower()
        risk_level = (risk.get("risk_level") or "").lower()

        mapped = {
            "valid": validation.get("is_valid"),
            "carrier": carrier.get("name") or None,
            "line_type": _LINE_TYPE_MAP.get((carrier.get("line_type") or "").lower()),
            "location": loc,
            "country": location.get("country_name") or None,
            "country_iso": location.get("country_code") or None,
            "voip": validation.get("is_voip"),
            "active": (line_status == "active") if line_status else None,
            "disposable": risk.get("is_disposable"),
            "recent_abuse": risk.get("is_abuse_detected"),
            "fraud_score": _RISK_LEVEL_SCORE.get(risk_level),
        }
        return ProviderResult(
            source=self.name,
            ok=True,
            raw=data,
            mapped={k: v for k, v in mapped.items() if v is not None and v != ""},
        )
