"""Stable identifiers and source-backed records used throughout a case."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def canonical_url(url: str) -> str:
    """Canonicalise profile URLs without treating arbitrary substrings as identity."""
    try:
        p = urlsplit((url or "").strip())
        scheme = p.scheme.lower()
        host = (p.hostname or "").lower().removeprefix("www.")
        port = f":{p.port}" if p.port and not (scheme == "https" and p.port == 443) else ""
        path = re.sub(r"/+", "/", p.path).rstrip("/") or "/"
        query = urlencode(
            sorted((k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_"))
        )
        return urlunsplit((scheme, host + port, path, query, ""))
    except Exception:
        return (url or "").strip()


def stable_account_id(platform: str, url: str, platform_id: str = "") -> str:
    key = f"{platform.lower()}|{platform_id or canonical_url(url)}"
    return "acct_" + hashlib.sha256(key.encode()).hexdigest()[:16]


def evidence_id(account_id: str, method: str, source_url: str, value: Any) -> str:
    key = f"{account_id}|{method}|{canonical_url(source_url)}|{value!r}"
    return "ev_" + hashlib.sha256(key.encode()).hexdigest()[:16]


def evidence_record(
    *,
    account_id: str = "",
    claim: str = "",
    source_url: str = "",
    source_location: str = "",
    value: Any = None,
    excerpt: str = "",
    method: str,
    kind: str = "observation",
    retrieved_at: str | None = None,
    source_event_time: str | None = None,
    strength: int = 0,
    supports: bool | None = True,
    dependence: str = "",
    limitation: str = "",
) -> dict:
    rid = evidence_id(
        account_id or claim, method, source_url, value if value is not None else excerpt
    )
    return {
        "id": rid,
        "account_id": account_id,
        "claim": claim,
        "source_url": canonical_url(source_url),
        "source_location": source_location[:160],
        "value": value,
        "excerpt": excerpt[:500],
        "retrieved_at": retrieved_at or utcnow(),
        "extraction_method": method,
        "source_event_time": source_event_time,
        "kind": kind,
        "strength": int(strength),
        "supports": supports,
        "dependence": dependence or rid,
        "limitation": limitation,
    }


def ensure_account(hit: dict, used_refs: set[str] | None = None) -> dict:
    hit.setdefault("canonical_url", canonical_url(hit.get("url", "")))
    hit.setdefault("platform_id", str((hit.get("extra") or {}).get("id", "")))
    hit.setdefault("matched_handle", str((hit.get("extra") or {}).get("matched_handle", "")))
    hit.setdefault("discovery_source", "username-enumeration")
    hit.setdefault(
        "account_id",
        stable_account_id(hit.get("platform", ""), hit["canonical_url"], hit["platform_id"]),
    )
    hit.setdefault("ownership_status", "unresolved")
    hit.setdefault("observation_status", "found")
    hit.setdefault("retrieved_at", utcnow())
    if not re.fullmatch(r"H\d{2,}", str(hit.get("ref", ""))):
        used_refs = used_refs or set()
        number = 1
        while f"H{number:02d}" in used_refs:
            number += 1
        hit["ref"] = f"H{number:02d}"
    hit.setdefault("evidence", [])
    hit.setdefault("conflicts", [])
    hit.setdefault("enrichment", {})
    return hit


def new_identity(accounts: list[str], name: str = "", *, label: str = "") -> dict:
    iid = "id_" + uuid.uuid4().hex[:12]
    return {
        "id": iid,
        "label": label,
        "display_label": label,
        "name": name,
        "evidence_score": 0,
        "status": "unresolved",
        "account_ids": list(accounts),
        "is_same_person_accounts": list(accounts),
        "reasoning": "",
        "evidence_ids": [],
        "limitations": ["Identity ownership remains unresolved."],
    }


def _short_hash(key: str, prefix: str) -> str:
    return prefix + hashlib.sha256(key.encode()).hexdigest()[:16]


def source_id(url: str, *, via: str = "") -> str:
    """One stable id per canonical URL: mirrors and repeated visits collapse
    onto the same source record instead of inflating the collection."""
    return _short_hash(canonical_url(url), "src_")


def source_record(
    *,
    url: str,
    outcome: str,
    final_url: str = "",
    title: str = "",
    content_type: str = "",
    via: str = "",
    excerpt: str = "",
    error: str = "",
    retrieved_at: str | None = None,
    http_status: int = 0,
    extra: dict | None = None,
) -> dict:
    canonical = canonical_url(final_url or url)
    return {
        "id": source_id(url, via=via),
        "url": canonical,
        "requested_url": url,
        "outcome": outcome,
        "title": (title or "")[:300],
        "content_type": content_type,
        "via": via,
        "excerpt": (excerpt or "")[:500],
        "error": error,
        "retrieved_at": retrieved_at or utcnow(),
        "http_status": http_status,
        "extra": extra or {},
    }


def query_id(engine: str, query: str) -> str:
    return _short_hash(f"{engine.casefold()}|{query.strip().casefold()}", "q_")


def lead_id(lead_type: str, args: dict) -> str:
    key = f"{lead_type}|{json.dumps(args, sort_keys=True, default=str).casefold()}"
    return _short_hash(key, "lead_")


def lead_record(
    *,
    lead_type: str,
    args: dict,
    purpose: str,
    expected: str = "",
    clues: list[str] | None = None,
    origin: str = "planner",
    score: float = 0.0,
    status: str = "pending",
    reason: str = "",
) -> dict:
    return {
        "id": lead_id(lead_type, args),
        "type": lead_type,
        "args": dict(args),
        "purpose": purpose[:300],
        "expected": expected[:300],
        "clues": list(clues or []),
        "origin": origin,
        "status": status,
        "reason": reason,
        "score": float(score),
        "attempts": 0,
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
