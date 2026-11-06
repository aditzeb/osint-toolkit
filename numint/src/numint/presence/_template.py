"""Copy this file to add a new site's presence check.

Rename it (drop the leading underscore so it's auto-discovered), rename the
class, and fill in `_check`. That's the whole integration - no other wiring.

RULES for a bundled check:
  * Read the site's OWN signup/reset/lookup response. Never log in, never
    scrape unrelated pages, never bypass a restriction.
  * `non_notifying = True` ONLY if the endpoint sends nothing to the target.
    If it can text/email the person, it does not belong here.
  * Degrade to `registered="unknown"` on any response you don't recognize -
    never guess. Raise on transport errors; the base class isolates them.
"""

from __future__ import annotations

import httpx

from ..core.models import PresenceResult
from .base import PresenceCheck, register_presence  # noqa: F401


# @register_presence  # <-- uncomment once implemented and file is renamed
class ExamplePresence(PresenceCheck):
    site = "example"
    method = "reset"  # lookup | reset | signup
    non_notifying = True

    async def _check(
        self, number, client: httpx.AsyncClient
    ) -> PresenceResult:
        resp = await client.post(
            "https://api.example.com/account/lookup",
            json={"phone": number.e164},
        )
        body = resp.json()

        if not body.get("exists"):
            return PresenceResult(
                site=self.site, registered="no", method=self.method
            )
        return PresenceResult(
            site=self.site,
            registered="yes",
            masked_email=body.get("masked_email"),   # e.g. "j••@gm***.com"
            masked_phone=body.get("masked_phone"),
            hint=body.get("username"),
            method=self.method,
        )
