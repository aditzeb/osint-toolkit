"""Open each found profile and read what is public.

JSON endpoints (parse=<name>) give clean structured data; everything else falls
back to OpenGraph / Twitter-card / JSON-LD tags scraped from the HTML.
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from snoop.core import Bus, Http
from snoop.enum import Hit

_URL_RE = re.compile(r"https?://[^\s\"'<>)]+")


def _first(*vals: Any) -> str:
    for v in vals:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


# --------------------------------------------------------------- JSON parsers


def _p_github(j: dict, h: Hit) -> None:
    h.display_name = _first(j.get("name"))
    h.bio = _first(j.get("bio"))
    h.avatar = _first(j.get("avatar_url"))
    h.location = _first(j.get("location"))
    h.joined = _first(j.get("created_at"))[:10]
    h.followers = str(j.get("followers", ""))
    for k in ("blog", "twitter_username", "company", "email"):
        v = j.get(k)
        if v:
            h.links.append(str(v))
    h.extra.update(
        {
            "public_repos": j.get("public_repos"),
            "company": j.get("company"),
            "email": j.get("email"),
            "twitter": j.get("twitter_username"),
            "hireable": j.get("hireable"),
            "id": j.get("id"),
        }
    )
    h.platform_id = str(j.get("id") or h.platform_id)


def _p_gitlab(j: Any, h: Hit) -> None:
    if isinstance(j, list) and j:
        j = j[0]
    if not isinstance(j, dict):
        return
    h.display_name = _first(j.get("name"))
    h.bio = _first(j.get("bio"))
    h.avatar = _first(j.get("avatar_url"))
    h.location = _first(j.get("location"))
    h.joined = _first(j.get("created_at"))[:10]
    for k in ("website_url", "linkedin", "twitter", "organization"):
        if j.get(k):
            h.links.append(str(j[k]))


def _p_dockerhub(j: dict, h: Hit) -> None:
    h.display_name = _first(j.get("full_name"))
    h.avatar = _first(j.get("gravatar_url"))
    h.location = _first(j.get("location"))
    h.joined = _first(j.get("date_joined"))[:10]
    if j.get("company"):
        h.links.append(str(j["company"]))
    if j.get("profile_url"):
        h.links.append(str(j["profile_url"]))


def _p_devto(j: dict, h: Hit) -> None:
    h.display_name = _first(j.get("name"))
    h.bio = _first(j.get("summary"))
    h.avatar = _first(j.get("profile_image"))
    h.location = _first(j.get("location"))
    h.joined = _first(j.get("joined_at"))
    for k in ("website_url", "github_username", "twitter_username"):
        if j.get(k):
            h.links.append(str(j[k]))


def _p_keybase(j: dict, h: Hit) -> None:
    them = j.get("them") or [None]
    them = them[0] if them else None
    if not them:
        return
    them.get("basics", {})
    profile = them.get("profile", {})
    h.display_name = _first(profile.get("full_name"))
    h.bio = _first(profile.get("bio"))
    h.location = _first(profile.get("location"))
    pic = them.get("pictures", {}).get("primary", {}).get("url")
    h.avatar = _first(pic)
    for val in (them.get("proofs_summary", {}).get("by_presentation_group", {}) or {}).values():
        for item in val:
            if item.get("service_url"):
                h.links.append(item["service_url"])


def _p_reddit(j: dict, h: Hit) -> None:
    d = j.get("data", {})
    h.display_name = _first(d.get("subreddit", {}).get("title"), d.get("name"))
    h.bio = _first(d.get("subreddit", {}).get("public_description"))
    h.avatar = _first(d.get("snoovatar_img"), d.get("icon_img", "").split("?")[0])
    h.followers = str(d.get("subreddit", {}).get("subscribers", "") or "")
    if d.get("created_utc"):
        import datetime

        h.joined = datetime.datetime.utcfromtimestamp(d["created_utc"]).strftime("%Y-%m-%d")
    h.extra.update(
        {
            "karma": (d.get("total_karma") or d.get("link_karma", 0) + d.get("comment_karma", 0)),
            "verified": d.get("verified"),
            "gold": d.get("is_gold"),
            "id": d.get("id"),
        }
    )
    h.platform_id = str(d.get("id") or h.platform_id)


def _p_hackernews(j: dict, h: Hit) -> None:
    h.bio = _first(BeautifulSoup(j.get("about", "") or "", "lxml").get_text(" "))
    h.extra.update({"karma": j.get("karma")})
    if j.get("created"):
        import datetime

        h.joined = datetime.datetime.utcfromtimestamp(j["created"]).strftime("%Y-%m-%d")
    h.links += _URL_RE.findall(j.get("about", "") or "")


def _p_mastodon(j: dict, h: Hit) -> None:
    h.display_name = _first(j.get("display_name"))
    h.bio = _first(BeautifulSoup(j.get("note", "") or "", "lxml").get_text(" "))
    h.avatar = _first(j.get("avatar_static"), j.get("avatar"))
    h.followers = str(j.get("followers_count", ""))
    h.joined = _first(j.get("created_at"))[:10]
    for f in j.get("fields", []):
        val = BeautifulSoup(f.get("value", ""), "lxml")
        a = val.find("a")
        if a and a.get("href"):
            h.links.append(a["href"])


def _p_bluesky(j: dict, h: Hit) -> None:
    h.display_name = _first(j.get("displayName"))
    h.bio = _first(j.get("description"))
    h.avatar = _first(j.get("avatar"))
    h.followers = str(j.get("followersCount", ""))
    h.joined = _first(j.get("createdAt"))[:10]


def _p_lichess(j: dict, h: Hit) -> None:
    p = j.get("profile", {})
    h.display_name = _first(p.get("realName"), j.get("username"))
    h.bio = _first(p.get("bio"))
    h.location = _first(p.get("location"))
    if p.get("links"):
        h.links += _URL_RE.findall(p["links"])
    if j.get("createdAt"):
        import datetime

        h.joined = datetime.datetime.utcfromtimestamp(j["createdAt"] / 1000).strftime("%Y-%m-%d")
    h.extra.update({"country": p.get("flag"), "fide": p.get("fideRating"), "id": j.get("id")})


def _p_chesscom(j: dict, h: Hit) -> None:
    h.display_name = _first(j.get("name"))
    h.location = _first(j.get("location"))
    h.avatar = _first(j.get("avatar"))
    h.followers = str(j.get("followers", ""))
    if j.get("joined"):
        import datetime

        h.joined = datetime.datetime.utcfromtimestamp(j["joined"]).strftime("%Y-%m-%d")
    h.extra.update(
        {
            "country": (j.get("country") or "").split("/")[-1],
            "title": j.get("title"),
            "id": j.get("player_id"),
        }
    )


def _p_gravatar(j: dict, h: Hit) -> None:
    e = (j.get("entry") or [None])[0]
    if not e:
        return
    h.display_name = _first(e.get("displayName"), (e.get("name") or {}).get("formatted"))
    h.avatar = _first(e.get("thumbnailUrl"))
    h.location = _first(e.get("currentLocation"))
    h.bio = _first(e.get("aboutMe") or "")
    for acc in e.get("accounts", []):
        if acc.get("url"):
            h.links.append(acc["url"])
    for em in e.get("emails", []):
        if em.get("value"):
            h.extra.setdefault("emails", []).append(em["value"])


def _p_mixcloud(j: dict, h: Hit) -> None:
    h.display_name = _first(j.get("name"))
    h.bio = _first(j.get("biog"))
    h.location = _first(j.get("city"), j.get("country"))
    h.avatar = _first((j.get("pictures") or {}).get("large"))
    h.followers = str(j.get("follower_count", ""))


def _p_duolingo(j: dict, h: Hit) -> None:
    users = j.get("users") or []
    if not users:
        return
    u = users[0]
    h.display_name = _first(u.get("name"))
    h.avatar = _first(("https:" + u["picture"] + "/xxlarge") if u.get("picture") else "")
    h.bio = _first(u.get("bio"))
    h.extra.update(
        {
            "streak": u.get("streak"),
            "learning": [c.get("title") for c in u.get("courses", [])],
            "id": u.get("id"),
        }
    )
    if u.get("creationDate"):
        import datetime

        h.joined = datetime.datetime.utcfromtimestamp(u["creationDate"]).strftime("%Y-%m-%d")


def _p_steam(_txt: str, h: Hit) -> None:
    soup = BeautifulSoup(_txt, "lxml-xml")
    h.display_name = _first(soup.find("steamID").get_text() if soup.find("steamID") else "")
    h.avatar = _first(soup.find("avatarFull").get_text() if soup.find("avatarFull") else "")
    h.location = _first(soup.find("location").get_text() if soup.find("location") else "")
    summ = soup.find("summary")
    if summ:
        h.bio = BeautifulSoup(summ.get_text(), "lxml").get_text(" ")[:400]


def _p_telegram(txt: str, h: Hit) -> None:
    soup = BeautifulSoup(txt, "lxml")
    t = soup.find("meta", property="og:title")
    d = soup.find("meta", property="og:description")
    i = soup.find("meta", property="og:image")
    h.display_name = _first(t["content"] if t else "")
    h.bio = _first(d["content"] if d else "")
    h.avatar = _first(i["content"] if i else "")


def _p_linktree(txt: str, h: Hit) -> None:
    _p_og(txt, h)
    _skip = (
        "linktr.ee",
        "linktree",
        "w3.org",
        "schema.org",
        "googleapis",
        "gstatic",
        "cloudflare",
        "google-analytics",
        "googletagmanager",
        "sentry",
        "cdn.",
    )
    h.links += sorted(
        {
            u
            for u in _URL_RE.findall(txt)
            if not any(s in u for s in _skip)
            and not u.endswith(
                (".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".woff2", ".ico", ".webp")
            )
        }
    )[:15]


# --------------------------------------------------------------- generic HTML


def _p_og(txt: str, h: Hit) -> None:
    soup = BeautifulSoup(txt, "lxml")

    def meta(*names: str) -> str:
        for n in names:
            m = soup.find("meta", property=n) or soup.find("meta", attrs={"name": n})
            if m and m.get("content"):
                return m["content"].strip()
        return ""

    h.display_name = h.display_name or _first(
        meta("og:title", "twitter:title"), soup.title.get_text() if soup.title else ""
    )
    h.bio = h.bio or _first(meta("og:description", "twitter:description", "description"))
    h.avatar = h.avatar or _first(meta("og:image", "twitter:image", "twitter:image:src"))

    # JSON-LD Person
    import json as _j

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = _j.loads(tag.string or "{}")
        except Exception:
            continue
        for node in data if isinstance(data, list) else [data]:
            if not isinstance(node, dict):
                continue
            if node.get("@type") in ("Person", "ProfilePage", "Organization"):
                h.display_name = h.display_name or _first(node.get("name"))
                h.bio = h.bio or _first(node.get("description"))
                h.avatar = h.avatar or _first(
                    node.get("image")
                    if isinstance(node.get("image"), str)
                    else (node.get("image") or {}).get("url")
                )
                addr = node.get("address") or {}
                if isinstance(addr, dict):
                    h.location = h.location or _first(
                        addr.get("addressLocality"), addr.get("addressCountry")
                    )
                for s in node.get("sameAs", []) or []:
                    h.links.append(s)


_JSON_PARSERS = {
    "github": _p_github,
    "gitlab": _p_gitlab,
    "dockerhub": _p_dockerhub,
    "devto": _p_devto,
    "keybase": _p_keybase,
    "reddit": _p_reddit,
    "hackernews": _p_hackernews,
    "mastodon": _p_mastodon,
    "bluesky": _p_bluesky,
    "lichess": _p_lichess,
    "chesscom": _p_chesscom,
    "gravatar": _p_gravatar,
    "mixcloud": _p_mixcloud,
    "duolingo": _p_duolingo,
}
_TEXT_PARSERS = {"steam": _p_steam, "telegram": _p_telegram, "linktree": _p_linktree}


async def enrich_hit(http: Http, h: Hit, bus: Bus) -> None:
    preserved = dict(h.extra)
    try:
        if h.parse in _JSON_PARSERS and h.data_url:
            r = await http.get(
                h.data_url, want_json=True, headers={"User-Agent": "snoop-osint/1.0"}
            )
            if r.json is not None:
                _JSON_PARSERS[h.parse](r.json, h)
        elif h.parse in _TEXT_PARSERS:
            url = h.data_url or h.url
            r = await http.get(url)
            if r.text:
                _TEXT_PARSERS[h.parse](r.text, h)
        else:
            r = await http.get(h.url)
            if r.text:
                _p_og(r.text, h)
    except Exception:
        pass
    # Parsers may add structured fields but must never erase discovery metadata.
    for key, value in preserved.items():
        h.extra.setdefault(key, value)
    h.matched_handle = h.matched_handle or str(h.extra.get("matched_handle", ""))

    # tidy
    h.bio = re.sub(r"\s+", " ", h.bio or "").strip()[:500]
    dn = (h.display_name or "").strip()[:120]
    plat_low = h.platform.lower().split(".")[0]
    handle = str(h.extra.get("matched_handle", "")).lower()

    # strip site chrome:  " | Platform" / " - Platform" / " on Platform" / "(@handle) • Platform"
    plat_pat = re.escape(h.platform).replace(r"\.", r"\.?")
    dn = re.sub(
        r"\s*(?:[|•·\-–—]|\bon\b|\bat\b)\s*" + plat_pat + r"(?:\.\w+)?\s*[.!]?$",
        "",
        dn,
        flags=re.IGNORECASE,
    ).strip(" .-–—|·")
    dn = re.sub(
        r"^\s*" + plat_pat + r"\s*(?:profile)?\s*[|•·\-–—:]\s*", "", dn, flags=re.IGNORECASE
    ).strip()
    dn = re.sub(r"\s*\(@[\w.]+\)\s*$", "", dn).strip()
    for pre in ("signup for free to see", "sign up to see", "join ", "listen to "):
        if dn.lower().startswith(pre):
            dn = ""

    _junk = {
        "sign up",
        "log in",
        "login",
        "sign in",
        "register",
        "home",
        "page not found",
        "404",
        "not found",
        "error",
        "loading...",
        "just a moment...",
        "redirecting",
        "make your day",
        "tiktok - make your day",
        "pay me on cash app",
        "instagram",
        "explore",
        "watch",
        "discover",
    }
    dn_low = dn.lower()
    dn_parts = {p.strip() for p in re.split(r"[|·–—-]", dn_low) if p.strip()}
    # echo of the searched handle, not a real name ("torvalds", "torvalds on X", "torvalds's gists")
    echo = handle and (
        dn_low == handle or dn_low.startswith((handle + " on ", handle + "'s ", handle + "’s "))
    )
    if dn_low in _junk or not dn_parts or dn_parts <= {plat_low} or echo:
        dn = ""
    h.display_name = dn
    if h.bio.lower() in _junk or (len(h.bio) < 4):
        h.bio = ""
    # generic marketing blurbs that sites serve as their default og:description
    for boiler in (
        "is empowering a new generation of creators",
        "build and deploy software collaboratively",
        "the world's largest online music",
        "the world’s largest online music",
        "instantly exchange money for free",
        "pay me on cash app",
        "make your day",
        "create an account or log in",
        "is an audio platform that lets you listen",
        "a substack publication with",
        "get your own music profile",
        "discover and share",
        "uses letterboxd to",
        "is an artist on deviantart",
    ):
        if boiler in h.bio.lower():
            h.bio = ""
    seen, clean = set(), []
    for l in h.links:
        l = l.strip()
        if l and l.lower() not in seen and len(l) < 300:
            seen.add(l.lower())
            clean.append(l)
    h.links = clean[:20]
    if h.display_name or h.bio or h.avatar or h.location or h.links:
        await bus.emit(
            "profile",
            platform=h.platform,
            name=h.display_name,
            bio=h.bio[:140],
            avatar=h.avatar,
            location=h.location,
            links=h.links,
            url=h.url,
        )
