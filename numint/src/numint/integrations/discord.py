"""Discord webhook push.

Turns a `Profile` into a single Discord embed and posts it to a webhook URL.
One shared embed builder feeds both a sync sender (CLI) and an async sender
(web), so the formatting never drifts between the two.

The webhook URL is a secret - it comes from config/env (`DISCORD_WEBHOOK_URL`),
never from user-facing input in the web layer.
"""

from __future__ import annotations

import httpx

from ..core.models import Profile

# Embed side-bar colors (Discord wants a decimal int).
_COLOR_GOOD = 0x22C55E
_COLOR_WARN = 0xF59E0B
_COLOR_BAD = 0xEF4444
_COLOR_NEUTRAL = 0x38BDF8

_TIMEOUT = 10.0


def _risk_color(profile: Profile) -> int:
    fs = profile.risk.fraud_score
    if fs is None:
        return _COLOR_NEUTRAL
    try:
        s = float(fs.value)
    except (TypeError, ValueError):
        return _COLOR_NEUTRAL
    if s >= 75:
        return _COLOR_BAD
    if s >= 40:
        return _COLOR_WARN
    return _COLOR_GOOD


def _field(name: str, value: str, inline: bool = True) -> dict:
    # Discord truncates hard at 1024 chars/field; stay well under.
    return {"name": name, "value": (value or "unknown")[:1000], "inline": inline}


def _first(attrs) -> str | None:
    for a in attrs or []:
        if a.value not in (None, ""):
            return str(a.value)
    return None


def build_discord_embed(profile: Profile) -> dict:
    """Build one rich Discord embed summarizing the whole scan."""
    n = profile.input
    carrier = profile.primary_carrier() or n.carrier or "unknown"
    line_type = profile.primary_line_type() or (n.number_type.value or "unknown")
    location = _first(profile.locations) or n.region or "unknown"

    fields = [
        _field("Valid", "yes" if n.is_valid else "no"),
        _field("Line type", str(line_type).replace("_", " ")),
        _field("Carrier", carrier),
        _field("Country", f"{n.country_name or 'unknown'} ({n.country_iso or '?'})"),
        _field("Location", location),
        _field("Time zones", ", ".join(n.timezones) or "unknown"),
        _field(
            "Formats",
            f"E.164: {n.e164}\nNational: {n.national}\n"
            f"International: {n.international}",
            inline=False,
        ),
    ]

    # Risk signals.
    r = profile.risk
    if r.fraud_score is not None:
        fields.append(_field("Fraud score", f"{r.fraud_score.value}/100"))
    flags = []
    for label, attr in (
        ("spam", r.spam), ("VoIP", r.voip),
        ("disposable", r.disposable), ("recent abuse", r.recent_abuse),
        ("active", r.active),
    ):
        if attr is not None and isinstance(attr.value, bool):
            flags.append(f"{label}: {'yes' if attr.value else 'no'}")
    if flags:
        fields.append(_field("Risk signals", " | ".join(flags), inline=False))

    # Account presence.
    if profile.presence:
        found = [p.site for p in profile.presence if p.registered == "yes"]
        checked = len(profile.presence)
        summary = (", ".join(found) if found else "none")
        summary += f"  ({len(found)}/{checked} found)"
        fields.append(_field("Accounts found", summary, inline=False))
        leaks = [
            f"{p.site}: {p.masked_email or p.masked_phone or p.hint}"
            for p in profile.presence
            if p.masked_email or p.masked_phone or p.hint
        ]
        if leaks:
            fields.append(_field("Leaked hints", "\n".join(leaks), inline=False))

    # AI details as extra fields.
    ai = profile.ai_analysis
    if ai and not ai.error:
        for label, val in (
            ("AI risk read", ai.risk_read),
            ("AI next steps", ai.next_steps),
            ("AI conflicts", ai.conflicts),
        ):
            if val and val.strip().lower() not in ("none", ""):
                fields.append(_field(label, val, inline=False))

    # Description carries the headline AI text (or the --ask answer).
    description = n.international
    if ai and not ai.error:
        headline = ai.answer or ai.summary
        if headline and headline.strip():
            description = headline.strip()[:4000]

    return {
        "title": n.e164,
        "description": description,
        "color": _risk_color(profile),
        "fields": fields[:25],
        "footer": {"text": "numint"},
        "timestamp": profile.generated_at.isoformat(),
    }


def _payload(profile: Profile) -> dict:
    return {"embeds": [build_discord_embed(profile)]}


def send_discord_sync(profile: Profile, webhook_url: str) -> None:
    """Post the embed synchronously (used by the CLI). Raises on HTTP error."""
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(webhook_url, json=_payload(profile))
        resp.raise_for_status()


async def send_discord_async(
    profile: Profile, webhook_url: str, client: httpx.AsyncClient | None = None
) -> None:
    """Post the embed on an event loop (used by the web layer)."""
    if client is not None:
        resp = await client.post(webhook_url, json=_payload(profile))
        resp.raise_for_status()
        return
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        resp = await c.post(webhook_url, json=_payload(profile))
        resp.raise_for_status()
