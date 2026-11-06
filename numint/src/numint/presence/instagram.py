"""Instagram presence check - ported from `megadose/ignorant`.

Posts an HMAC-signed lookup to Instagram's mobile `users/lookup` endpoint (the
"forgot password" pre-check). Existence is decided exactly as ignorant does:
if the response is not "No users found", the number is linked to an account.
No SMS/email is sent to the target.

As a bonus over ignorant, if the account exists the response's obfuscated
contact hints are captured for pivoting.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import urllib.parse

import httpx

from ..core.models import PresenceResult
from .base import PresenceCheck, register_presence

USERS_LOOKUP_URL = "https://i.instagram.com/api/v1/users/lookup/"
SIG_KEY_VERSION = "4"
IG_SIG_KEY = "e6358aeede676184b9fe702b30f4fd35e71744605e39d2181a34cede076b3c33"


def _generate_signature(data: str) -> str:
    return (
        "ig_sig_key_version="
        + SIG_KEY_VERSION
        + "&signed_body="
        + hmac.new(
            IG_SIG_KEY.encode("utf-8"), data.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        + "."
        + urllib.parse.quote_plus(data)
    )


def _generate_data(q: str) -> dict:
    return {
        "login_attempt_count": "0",
        "directly_sign_in": "true",
        "source": "default",
        "q": q,
        "ig_sig_key_version": SIG_KEY_VERSION,
    }


@register_presence
class InstagramPresence(PresenceCheck):
    site = "instagram"
    method = "lookup"
    non_notifying = True

    async def _check(
        self, number, client: httpx.AsyncClient
    ) -> PresenceResult:
        # ignorant signs on str(country_code)+str(phone); that is E.164 digits.
        payload = _generate_data(number.digits)
        data = _generate_signature(json.dumps(payload))
        headers = {
            "Accept-Language": "en-US",
            "User-Agent": "Instagram 101.0.0.15.120",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept-Encoding": "gzip, deflate",
            "X-FB-HTTP-Engine": "Liger",
            "Connection": "close",
        }
        try:
            r = await client.post(USERS_LOOKUP_URL, headers=headers, data=data)
            rep = r.json()
        except Exception:
            return PresenceResult(
                site=self.site, registered="rate_limited", method=self.method
            )

        if rep.get("message") == "No users found":
            return PresenceResult(
                site=self.site, registered="no", method=self.method
            )
        return PresenceResult(
            site=self.site,
            registered="yes",
            masked_email=rep.get("obfuscated_email") or None,
            masked_phone=rep.get("obfuscated_phone") or None,
            hint=rep.get("username") or None,
            method=self.method,
        )
