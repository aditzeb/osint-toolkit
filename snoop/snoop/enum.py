"""Username enumeration using the packaged catalog and soft-404 controls."""

from __future__ import annotations

import asyncio
import json
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from snoop.core import Bus, Http
from snoop.model import canonical_url, stable_account_id, utcnow

_SITES = json.loads((Path(__file__).parent / "data" / "sites.json").read_text("utf-8"))["sites"]

USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,38}[A-Za-z0-9])?$")


def is_username(s: str) -> bool:
    return bool(USERNAME_RE.match(s.strip()))


@dataclass
class Hit:
    platform: str
    category: str
    url: str
    data_url: str = ""
    parse: str = ""
    status: int = 0
    ms: float = 0.0
    # filled by the extractor later
    display_name: str = ""
    bio: str = ""
    avatar: str = ""
    location: str = ""
    links: list[str] = field(default_factory=list)
    joined: str = ""
    followers: str = ""
    extra: dict = field(default_factory=dict)
    account_id: str = ""
    ref: str = ""
    platform_id: str = ""
    canonical_url: str = ""
    matched_handle: str = ""
    discovery_source: str = "username-enumeration"
    observation_status: str = "found"
    retrieved_at: str = ""

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        return d


async def _check(http: Http, site: dict, username: str, control: str) -> Hit | None:
    url = site["url"].replace("{}", username)
    r = await http.get(url)
    if r.outcome != "found":
        return None
    method = site.get("method", "status")
    body = r.text or ""
    login_wall = bool(
        re.search(
            r"<title>\s*(?:log\s*in|sign\s*in)|log\s+in\s+to\s+continue|authentication required",
            body,
            re.IGNORECASE,
        )
    )
    if login_wall:
        return None

    if method == "message":
        if r.status != 200:
            return None
        if site.get("errorMsg") and site["errorMsg"] in body:
            return None
        if site.get("existMsg") and site["existMsg"] not in body:
            return None
    else:
        if r.status != 200:
            return None
        # control probe: if a bogus name is also 200 the site has no real 404
        ctrl_url = site["url"].replace("{}", control)
        c = await http.get(ctrl_url, control=True)
        # Only a conclusive missing control makes the positive usable. A found,
        # blocked, timed-out or rate-limited control is inconclusive.
        if c.outcome != "not_found":
            return None
    canonical = canonical_url(r.final_url or url)
    return Hit(
        platform=site["name"],
        category=site.get("cat", "other"),
        url=r.final_url or url,
        data_url=(site.get("data", "").replace("{}", username) or ""),
        parse=site.get("parse", ""),
        status=r.status,
        ms=r.elapsed_ms,
        account_id=stable_account_id(site["name"], canonical, username),
        platform_id=username,
        canonical_url=canonical,
        matched_handle=username,
        retrieved_at=r.retrieved_at or utcnow(),
    )


def prioritized_sites(max_sites: int | None = None) -> list[dict]:
    """Deterministic site ordering: structured parsers and core categories first,
    so a bounded probe budget spends itself on the most informative platforms."""
    category_rank = {"dev": 0, "social": 1, "identity": 2, "forum": 3, "media": 4, "gaming": 5}
    ordered = sorted(
        enumerate(_SITES),
        key=lambda pair: (
            0 if pair[1].get("parse") else 1,
            category_rank.get(pair[1].get("cat", "other"), 6),
            pair[0],
        ),
    )
    rows = [site for _index, site in ordered]
    return rows[:max_sites] if max_sites is not None else rows


async def enumerate_username(
    username: str, bus: Bus, http: Http, *, sites: list[dict] | None = None, max_sites: int | None = None
) -> list[Hit]:
    username = username.strip().lstrip("@")
    control = f"{username}{secrets.token_hex(3)}zz"
    probe_sites = sites if sites is not None else prioritized_sites(max_sites)
    await bus.emit("scan_start", target=username, total=len(probe_sites))

    hits: list[Hit] = []

    async def one(site: dict) -> None:
        await bus.emit("probe", platform=site["name"])
        try:
            hit = await asyncio.wait_for(_check(http, site, username, control), timeout=15)
        except Exception:
            hit = None
        if hit:
            hits.append(hit)
            await bus.emit(
                "hit", platform=hit.platform, category=hit.category, url=hit.url, ms=round(hit.ms)
            )
        else:
            await bus.emit("miss", platform=site["name"], outcome="inconclusive_or_not_found")

    await asyncio.gather(*(one(s) for s in probe_sites))
    hits.sort(key=lambda h: (h.category, h.platform.lower()))
    return hits
