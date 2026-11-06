"""Amazon presence check - ported from `megadose/ignorant`.

Loads Amazon's OpenID sign-in page, replays its hidden form fields with the
phone number as the `email`, and posts to the sign-in endpoint. Amazon shows
the `auth-password-missing-alert` div only when the account already exists -
that is the existence signal. This stops at the password step; no OTP/SMS is
sent to the target.

ignorant uses BeautifulSoup; to avoid an extra dependency the hidden inputs are
parsed with a small regex instead. Logic is otherwise identical.
"""

from __future__ import annotations

import random
import re

import httpx

from ..core.models import PresenceResult
from .base import CHROME_UAS, PresenceCheck, register_presence

_SIGNIN_GET = (
    "https://www.amazon.com/ap/signin?openid.pape.max_auth_age=0"
    "&openid.return_to=https%3A%2F%2Fwww.amazon.com%2F%3F_encoding%3DUTF8"
    "%26ref_%3Dnav_ya_signin"
    "&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"
    "%2Fidentifier_select&openid.assoc_handle=usflex"
    "&openid.mode=checkid_setup"
    "&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"
    "%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&"
)
_SIGNIN_POST = "https://www.amazon.com/ap/signin/"

_INPUT_RE = re.compile(r"<input\b[^>]*>", re.IGNORECASE)


def _parse_inputs(html: str) -> dict[str, str]:
    """Collect every <input> with both name and value (bs4-select equivalent)."""
    data: dict[str, str] = {}
    for tag in _INPUT_RE.findall(html):
        name = re.search(r'name\s*=\s*"([^"]*)"', tag, re.IGNORECASE)
        value = re.search(r'value\s*=\s*"([^"]*)"', tag, re.IGNORECASE)
        if name and value:
            data[name.group(1)] = value.group(1)
    return data


@register_presence
class AmazonPresence(PresenceCheck):
    site = "amazon"
    method = "login"
    non_notifying = True

    async def _check(
        self, number, client: httpx.AsyncClient
    ) -> PresenceResult:
        headers = {"User-agent": random.choice(CHROME_UAS)}
        try:
            req = await client.get(_SIGNIN_GET, headers=headers)
            data = _parse_inputs(req.text)
            data["email"] = number.digits  # str(country_code)+str(phone)
            req = await client.post(_SIGNIN_POST, data=data, headers=headers)
        except Exception:
            return PresenceResult(
                site=self.site, registered="rate_limited", method=self.method
            )

        if 'id="auth-password-missing-alert"' in req.text:
            return PresenceResult(
                site=self.site, registered="yes", method=self.method
            )
        return PresenceResult(
            site=self.site, registered="no", method=self.method
        )
