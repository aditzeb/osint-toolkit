"""Pivots: name -> candidate handles, handle/name -> candidate emails, breach checks."""

from __future__ import annotations

import asyncio
import hashlib
import re

from snoop.config import config
from snoop.core import Bus, Http

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_COMMON_DOMAINS = [
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "yahoo.com",
    "proton.me",
    "icloud.com",
]


_NOBILIARY = ("van", "von", "de", "der", "den", "la", "le", "di", "da", "el", "al", "bin", "ibn")


def candidate_handles(name: str) -> list[str]:
    """Ordered best-guess first: strongest handle conventions come first so a
    non-deep run that only tries the top N still covers the likely one."""
    raw = [p for p in re.split(r"[\s._-]+", name.strip().lower()) if p.isalnum()]
    parts = [p for p in raw if p not in _NOBILIARY] or raw
    if not parts:
        return []
    first, last, mids = parts[0], parts[-1], parts[1:-1]
    mi = "".join(m[0] for m in mids)
    ordered = [
        first + last,
        f"{first}.{last}",
        first[0] + last,
        f"{first}_{last}",
        first + last[0],
        first + mi + last,
        first[0] + mi + last,
        "".join(raw),
        first[0] + "".join(raw[1:]),  # gvanrossum-style
        "".join(p[0] for p in raw[:-1]) + raw[-1],
        f"{first}-{last}",
        last + first,
        first,
        last,
        "the" + first + last,
        first + last + "1",
        "real" + first + last,
    ]
    seen, out = set(), []
    for h in ordered:
        if 2 < len(h) < 30 and h not in seen:
            seen.add(h)
            out.append(h)
    return out


def candidate_emails(seed: str, name: str = "") -> list[str]:
    """Ordered, not a set - which stems survive the cut must not depend on
    hash ordering."""
    ordered: list[str] = []
    s = re.sub(r"[^a-z0-9._-]", "", seed.lower())
    if s:
        ordered.append(s)
    if name:
        parts = [p for p in re.split(r"[\s._-]+", name.strip().lower()) if p]
        if len(parts) >= 2:
            f, l = parts[0], parts[-1]
            ordered += [f + l, f + "." + l, f[0] + l, f + "_" + l, f + l[0]]
    stems, seen = [], set()
    for stem in ordered:
        if stem and stem not in seen:
            seen.add(stem)
            stems.append(stem)
    return [f"{stem}@{dom}" for stem in stems[:4] for dom in _COMMON_DOMAINS]


async def gravatar_for_email(http: Http, email: str) -> dict | None:
    h = hashlib.md5(email.strip().lower().encode()).hexdigest()
    r = await http.get(
        f"https://gravatar.com/{h}.json", want_json=True, headers={"User-Agent": "snoop-osint/1.0"}
    )
    if isinstance(r.json, dict) and r.json.get("entry"):
        e = r.json["entry"][0]
        return {
            "email": email,
            "hash": h,
            "avatar": f"https://gravatar.com/avatar/{h}?s=256",
            "name": (e.get("displayName") or (e.get("name") or {}).get("formatted") or ""),
            "location": e.get("currentLocation", ""),
            "accounts": [a.get("url") for a in e.get("accounts", []) if a.get("url")],
            "profile": e.get("profileUrl", ""),
        }
    return None


async def hibp_breaches(http: Http, email: str) -> dict:
    if not config.hibp_key:
        return {"status": "missing_configuration", "items": [], "retrieved_at": ""}
    r = await http.get(
        f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}?truncateResponse=false",
        headers={"hibp-api-key": config.hibp_key, "User-Agent": "snoop-osint"},
        want_json=True,
        credentials_for="haveibeenpwned.com",
    )
    if r.status == 200 and isinstance(r.json, list) and all(isinstance(b, dict) for b in r.json):
        items = [
            {
                "name": b.get("Name"),
                "domain": b.get("Domain"),
                "date": b.get("BreachDate"),
                "count": b.get("PwnCount"),
                "data": b.get("DataClasses", []),
            }
            for b in r.json
        ]
        return {
            "status": "found" if items else "empty",
            "items": items,
            "retrieved_at": r.retrieved_at,
        }
    if r.status == 404:
        return {"status": "empty", "items": [], "retrieved_at": r.retrieved_at}
    status = "authentication_failure" if r.status in {401, 403} else r.outcome
    return {"status": status, "items": [], "retrieved_at": r.retrieved_at}


async def run_email_enrichment(emails: list[str], http: Http, bus: Bus) -> dict:
    emails = sorted({e.lower() for e in emails})[:8]
    out: dict = {"gravatar": [], "breaches": {}, "provider_status": {"hibp": {}}}
    if not emails:
        return out
    await bus.emit("stage", name=f"checking {len(emails)} email(s)")

    async def one(email: str) -> None:
        g = await gravatar_for_email(http, email)
        if g:
            out["gravatar"].append(g)
            await bus.emit(
                "enrich", sig="gravatar", email=email, name=g["name"], avatar=g["avatar"]
            )
        result = await hibp_breaches(http, email)
        out["provider_status"]["hibp"][email] = {
            "status": result["status"],
            "retrieved_at": result["retrieved_at"],
        }
        if result["items"]:
            out["breaches"][email] = result["items"]
            await bus.emit(
                "enrich",
                sig="breach",
                email=email,
                count=len(result["items"]),
                names=[x["name"] for x in result["items"]][:8],
            )

    await asyncio.gather(*(one(e) for e in emails))
    return out


def harvest_emails(text_blobs: list[str]) -> list[str]:
    found: set[str] = set()
    for blob in text_blobs:
        for m in _EMAIL_RE.findall(blob or ""):
            if not m.lower().endswith((".png", ".jpg", ".gif", ".svg", ".webp")):
                found.add(m.lower())
    return sorted(found)
