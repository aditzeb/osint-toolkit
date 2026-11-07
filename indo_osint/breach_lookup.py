"""Live Email Breach, Stealer Malware, and Profile OSINT Intelligence.

Free and public sources:
- XposedOrNot API: Known data breaches, pastes, and exposed data fields.
- Hudson Rock Cavalier API: Infostealer malware infections (RedLine, Lumma, Raccoon, Vidar).
- Gravatar API: Public profile, full name, avatars, and linked accounts.
- GitHub Commits/User API: Developer identity and repository linking.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _fetch_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> Optional[Any]:
    req_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None
    return None


def check_xposedornot(email: str) -> Dict[str, Any]:
    """Query XposedOrNot for data breaches and analytics."""
    safe_email = urllib.parse.quote(email.strip().lower())
    url = f"https://api.xposedornot.com/v1/breach-analytics?email={safe_email}"
    data = _fetch_json(url, timeout=12)

    result: Dict[str, Any] = {
        "found": False,
        "breach_count": 0,
        "breaches": [],
        "paste_count": 0,
        "pastes": [],
        "risk_score": "Unknown",
        "exposed_fields": set(),
    }

    if not data or "Error" in data:
        # Fallback to simple check endpoint
        simple_url = f"https://api.xposedornot.com/v1/check-email/{safe_email}"
        simple_data = _fetch_json(simple_url, timeout=10)
        if simple_data and "breaches" in simple_data:
            breach_list = simple_data.get("breaches", [[]])[0]
            if breach_list:
                result["found"] = True
                result["breach_count"] = len(breach_list)
                result["breaches"] = [{"name": b, "domain": "", "date": "Unknown", "exposed": []} for b in breach_list]
        return result

    breaches_details = data.get("ExposedBreaches", {}).get("breaches_details", [])
    if not breaches_details and "BreachesSummary" in data:
        # Check if site string exists
        site_str = data.get("BreachesSummary", {}).get("site", "")
        if site_str:
            site_list = [s.strip() for s in site_str.split(";") if s.strip()]
            breaches_details = [{"breach": s, "domain": "", "xposed_date": "Unknown", "xposed_records": 0, "xposed_data": ""} for s in site_list]

    if breaches_details:
        result["found"] = True
        result["breach_count"] = len(breaches_details)
        for b in breaches_details:
            exposed_data = b.get("xposed_data", [])
            if isinstance(exposed_data, str):
                exposed_data = [x.strip() for x in exposed_data.split(";") if x.strip()]
            for f in exposed_data:
                result["exposed_fields"].add(f)
            result["breaches"].append({
                "name": b.get("breach", "Unknown"),
                "domain": b.get("domain", ""),
                "date": b.get("xposed_date", "Unknown"),
                "records": b.get("xposed_records", 0),
                "exposed": exposed_data,
                "description": b.get("details", ""),
            })

    pastes = data.get("PastesSummary", {}).get("cnt", 0)
    result["paste_count"] = pastes

    risk_obj = data.get("BreachMetrics", {}).get("risk", [])
    if isinstance(risk_obj, list) and risk_obj:
        result["risk_score"] = f"{risk_obj[0].get('risk_label', 'Unknown')} ({risk_obj[0].get('risk_score', '')})"
    elif isinstance(risk_obj, dict):
        result["risk_score"] = f"{risk_obj.get('risk_label', 'Unknown')} ({risk_obj.get('risk_score', '')})"
    else:
        result["risk_score"] = "Low"

    result["exposed_fields"] = sorted(list(result["exposed_fields"]))
    return result


def check_hudsonrock_infostealers(email: str) -> Dict[str, Any]:
    """Query Hudson Rock Cavalier for infostealer malware compromises."""
    safe_email = urllib.parse.quote(email.strip().lower())
    url = f"https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-email?email={safe_email}"
    data = _fetch_json(url, timeout=12)

    result: Dict[str, Any] = {
        "compromised": False,
        "stealer_count": 0,
        "stealers": [],
        "total_corp_services": 0,
        "total_user_services": 0,
    }

    if not data or not isinstance(data, dict):
        return result

    stealers = data.get("stealers", [])
    if stealers:
        result["compromised"] = True
        result["stealer_count"] = len(stealers)
        result["total_corp_services"] = data.get("total_corporate_services", 0)
        result["total_user_services"] = data.get("total_user_services", 0)

        for s in stealers:
            result["stealers"].append({
                "date": s.get("date_compromised", "Unknown"),
                "computer_name": s.get("computer_name", "Unknown"),
                "os": s.get("operating_system", "Unknown"),
                "malware_path": s.get("malware_path", "Unknown"),
                "antiviruses": s.get("antiviruses", []),
                "ip": s.get("ip", "Unknown"),
                "passwords_count": len(s.get("top_passwords", [])),
                "sample_logins": s.get("top_logins", [])[:5],
            })
    return result


def check_gravatar(email: str) -> Dict[str, Any]:
    """Check Gravatar for public profile, avatar, and linked social profiles."""
    email_clean = email.strip().lower()
    email_hash = hashlib.md5(email_clean.encode("utf-8")).hexdigest()
    url = f"https://en.gravatar.com/{email_hash}.json"
    data = _fetch_json(url, timeout=8)

    result: Dict[str, Any] = {
        "found": False,
        "hash": email_hash,
        "avatar_url": f"https://www.gravatar.com/avatar/{email_hash}?s=400&d=404",
        "display_name": "",
        "full_name": "",
        "about": "",
        "urls": [],
        "accounts": [],
    }

    if data and "entry" in data and data["entry"]:
        entry = data["entry"][0]
        result["found"] = True
        result["display_name"] = entry.get("displayName", "")
        result["full_name"] = entry.get("name", {}).get("formatted", "")
        result["about"] = entry.get("aboutMe", "")
        result["urls"] = [u.get("value") for u in entry.get("urls", []) if "value" in u]
        result["accounts"] = [
            f"{a.get('shortname')}: {a.get('url')}"
            for a in entry.get("accounts", [])
            if "shortname" in a and "url" in a
        ]
    return result


def check_github_developer(email: str) -> Dict[str, Any]:
    """Check public GitHub developer artifacts for an email address."""
    safe_email = urllib.parse.quote(email.strip().lower())
    url = f"https://api.github.com/search/commits?q=author-email:{safe_email}&sort=author-date&order=desc"
    data = _fetch_json(url, timeout=10)

    result: Dict[str, Any] = {
        "found": False,
        "commit_count": 0,
        "names": set(),
        "usernames": set(),
        "recent_repos": [],
    }

    if data and "items" in data and data["items"]:
        items = data["items"]
        result["found"] = True
        result["commit_count"] = data.get("total_count", len(items))

        for item in items[:10]:
            commit = item.get("commit", {})
            author = commit.get("author", {})
            if author.get("name"):
                result["names"].add(author.get("name"))

            gh_author = item.get("author")
            if gh_author and gh_author.get("login"):
                result["usernames"].add(gh_author.get("login"))

            repo = item.get("repository", {})
            if repo.get("full_name"):
                result["recent_repos"].append(repo.get("full_name"))

    result["names"] = list(result["names"])
    result["usernames"] = list(result["usernames"])
    result["recent_repos"] = list(dict.fromkeys(result["recent_repos"]))[:5]
    return result


def lookup_email_full(email: str) -> Dict[str, Any]:
    """Perform full comprehensive email reconnaissance across breaches, stealers, and profiles."""
    email_clean = email.strip().lower()
    return {
        "email": email_clean,
        "xposed": check_xposedornot(email_clean),
        "hudsonrock": check_hudsonrock_infostealers(email_clean),
        "gravatar": check_gravatar(email_clean),
        "github": check_github_developer(email_clean),
    }
