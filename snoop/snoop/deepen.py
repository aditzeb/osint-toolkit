"""Platform deep-dives: follow-up fetches that go past the existence-check profile.

Deterministic, no extra AI call needed - these produce concrete facts fast.
"""

from __future__ import annotations

from snoop.config import config
from snoop.core import Http

_GH_LANG_ORDER: list[str] = []


async def deepen_github(http: Http, handle: str) -> dict:
    headers = {"User-Agent": "snoop-osint"}
    if config.github_token:
        headers["Authorization"] = f"Bearer {config.github_token}"
    repos_r = await http.get(
        f"https://api.github.com/users/{handle}/repos?sort=pushed&per_page=100",
        want_json=True,
        headers=headers,
        credentials_for="api.github.com",
    )
    orgs_r = await http.get(
        f"https://api.github.com/users/{handle}/orgs",
        want_json=True,
        headers=headers,
        credentials_for="api.github.com",
    )
    if repos_r.outcome != "found":
        status = (
            "authentication_failure"
            if config.github_token and repos_r.status in {401, 403}
            else repos_r.outcome
        )
        return {
            "platform": "GitHub",
            "status": status,
            "summary": f"GitHub enrichment {status}; no empty-result claim was made",
        }
    repos = repos_r.json if isinstance(repos_r.json, list) else []
    orgs = orgs_r.json if isinstance(orgs_r.json, list) else []

    langs: dict[str, int] = {}
    for r in repos:
        if isinstance(r, dict) and r.get("language"):
            langs[r["language"]] = langs.get(r["language"], 0) + 1
    top_repos = sorted(
        [r for r in repos if isinstance(r, dict) and not r.get("fork")],
        key=lambda r: r.get("stargazers_count", 0),
        reverse=True,
    )[:5]

    return {
        "platform": "GitHub",
        "repo_count": len(repos),
        "top_languages": sorted(langs, key=langs.get, reverse=True)[:5],
        "top_repos": [
            {
                "name": r["name"],
                "stars": r.get("stargazers_count", 0),
                "lang": r.get("language"),
                "desc": (r.get("description") or "")[:100],
            }
            for r in top_repos
        ],
        "organizations": [o.get("login") for o in orgs if isinstance(o, dict)],
        "organization_status": orgs_r.outcome,
        "events": [
            {
                "event": f"repository created: {r.get('name', '')}",
                "event_time": r.get("created_at"),
                "retrieved_at": repos_r.retrieved_at,
                "source_url": r.get("html_url"),
            }
            for r in repos[:20]
            if isinstance(r, dict) and r.get("created_at") and r.get("html_url")
        ],
        "summary": _gh_summary(len(repos), langs, top_repos, orgs),
    }


def _gh_summary(n: int, langs: dict, top_repos: list, orgs: list) -> str:
    bits = [f"{n} public repos"]
    if langs:
        bits.append("mostly " + ", ".join(sorted(langs, key=langs.get, reverse=True)[:3]))
    if top_repos:
        bits.append(f"top: {top_repos[0]['name']} ({top_repos[0].get('stargazers_count', 0)}★)")
    if orgs:
        bits.append(
            "member of " + ", ".join(o.get("login", "") for o in orgs[:3] if isinstance(o, dict))
        )
    return " · ".join(bits)


async def deepen_reddit(http: Http, handle: str) -> dict:
    sub_r = await http.get(
        f"https://www.reddit.com/user/{handle}/submitted.json?limit=25", want_json=True
    )
    com_r = await http.get(
        f"https://www.reddit.com/user/{handle}/comments.json?limit=25", want_json=True
    )
    if sub_r.outcome != "found" or com_r.outcome != "found":
        status = sub_r.outcome if sub_r.outcome != "found" else com_r.outcome
        return {
            "platform": "Reddit",
            "status": status,
            "summary": f"Reddit enrichment {status}; no empty-result claim was made",
        }
    subs: dict[str, int] = {}
    latest = 0
    total = 0
    for r in (sub_r.json, com_r.json):
        if not isinstance(r, dict):
            continue
        for child in r.get("data", {}).get("children", []):
            d = child.get("data", {})
            sr = d.get("subreddit")
            if sr:
                subs[sr] = subs.get(sr, 0) + 1
                total += 1
            latest = max(latest, d.get("created_utc", 0))

    import datetime

    return {
        "platform": "Reddit",
        "post_and_comment_count": total,
        "top_subreddits": sorted(subs, key=subs.get, reverse=True)[:8],
        "last_active": (
            datetime.datetime.utcfromtimestamp(latest).strftime("%Y-%m-%d") if latest else ""
        ),
        "status": sub_r.outcome if sub_r.outcome != "found" else com_r.outcome,
        "summary": _reddit_summary(total, subs, latest),
    }


def _reddit_summary(total: int, subs: dict, latest: float) -> str:
    if not total:
        return "no recent public posts or comments"
    top = sorted(subs, key=subs.get, reverse=True)[:5]
    bits = [f"{total} recent posts/comments", "active in " + ", ".join(f"r/{s}" for s in top)]
    if latest:
        import datetime

        bits.append(f"last seen {datetime.datetime.utcfromtimestamp(latest).strftime('%Y-%m-%d')}")
    return " · ".join(bits)


async def deepen_lichess(http: Http, handle: str) -> dict:
    r = await http.get(f"https://lichess.org/api/user/{handle}", want_json=True)
    if r.outcome != "found":
        return {
            "platform": "Lichess",
            "status": r.outcome,
            "summary": f"Lichess enrichment {r.outcome}; no empty-result claim was made",
        }
    j = r.json if isinstance(r.json, dict) else {}
    perfs = j.get("perfs", {})
    best = sorted(
        ((k, v.get("rating", 0)) for k, v in perfs.items() if isinstance(v, dict)),
        key=lambda x: -x[1],
    )[:4]
    return {
        "platform": "Lichess",
        "ratings": dict(best),
        "games": j.get("count", {}).get("all", 0),
        "status": r.outcome,
        "summary": " · ".join(f"{k} {v}" for k, v in best) or "no rated games",
    }


_DISPATCH = {"github": deepen_github, "reddit": deepen_reddit, "lichess": deepen_lichess}


async def deepen(http: Http, platform: str, handle: str) -> dict:
    fn = _DISPATCH.get(platform.lower().split(".")[0])
    if not fn:
        return {
            "platform": platform,
            "summary": f"no deeper API for {platform} - open the profile manually for more.",
        }
    try:
        return await fn(http, handle)
    except Exception as e:
        return {"platform": platform, "summary": f"deep-dive failed: {e}"}
