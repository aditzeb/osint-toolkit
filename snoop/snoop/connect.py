"""Deterministic link analysis and discovery-path tracing.

`connections()` explains *why* records in a case relate to each other, with
the source that establishes each link and an honest strength label.
`trace()` answers "how did the investigation get here?" by walking the lead
provenance chain: query -> result -> page -> alias -> profile.

Nothing here creates evidence or changes identity decisions. Shared handles,
shared images and shared sites are clues; only an explicit published link is
labelled strong, and even that is not proof of personal ownership.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from snoop.model import canonical_url

STRONG, MODERATE, CLUE = "strong", "moderate", "clue"


def _host(url: str) -> str:
    return (urlsplit(url or "").hostname or "").casefold().removeprefix("www.")


def _excluded(dossier, account: dict) -> bool:
    return False


def connections(dossier) -> list[dict]:
    """Every explainable link between accounts and sources in the case."""
    from snoop.evidence import _is_platform_domain

    accounts = list(dossier.all_accounts)
    by_url = {canonical_url(a.get("canonical_url") or a.get("url", "")): a for a in accounts}
    rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    def add(kind: str, a: str, b: str, detail: str, strength: str, source_url: str = "", excluded: bool = False):
        key = (kind, *sorted((a, b)))
        if a == b or key in seen:
            return
        seen.add(key)
        rows.append(
            {
                "kind": kind,
                "a": a,
                "b": b,
                "detail": detail,
                "strength": strength,
                "source_url": source_url,
                "excluded_side": excluded,
            }
        )

    # 1. An account publishes a link to another account's profile.
    for account in accounts:
        for link in account.get("links", []) or []:
            other = by_url.get(canonical_url(link))
            if other is None or other is account:
                continue
            add(
                "links_to",
                account.get("ref", ""),
                other.get("ref", ""),
                f"{account.get('platform', '?')} profile publishes a link to the {other.get('platform', '?')} profile",
                STRONG,
                account.get("canonical_url", ""),
                _excluded(dossier, account) or _excluded(dossier, other),
            )

    # 2. The same handle on different platforms — a clue, never proof alone.
    by_handle: dict[str, list[dict]] = {}
    for account in accounts:
        handle = str(account.get("matched_handle") or "").casefold().lstrip("@")
        if len(handle) >= 4:
            by_handle.setdefault(handle, []).append(account)
    for handle, group in by_handle.items():
        platforms = {a.get("platform") for a in group}
        if len(group) < 2 or len(platforms) < 2:
            continue
        for index, left in enumerate(group):
            for right in group[index + 1:]:
                if left.get("platform") == right.get("platform"):
                    continue
                add(
                    "same_handle",
                    left.get("ref", ""),
                    right.get("ref", ""),
                    f'both use the handle "{handle}" — anyone can register a handle, so this is a clue',
                    CLUE,
                    excluded=_excluded(dossier, left) or _excluded(dossier, right),
                )

    # 3. Two accounts link to the same non-platform (personal) site.
    by_site: dict[str, list[dict]] = {}
    for account in accounts:
        for link in account.get("links", []) or []:
            host = _host(link)
            if host and not _is_platform_domain(host):
                by_site.setdefault(host, [])
                if account not in by_site[host]:
                    by_site[host].append(account)
    for host, group in by_site.items():
        for index, left in enumerate(group):
            for right in group[index + 1:]:
                add(
                    "shared_site",
                    left.get("ref", ""),
                    right.get("ref", ""),
                    f"both link to the personal site {host}",
                    MODERATE,
                    f"https://{host}/",
                    _excluded(dossier, left) or _excluded(dossier, right),
                )

    # 4. The same avatar image on different platforms (image reuse is a clue).
    by_avatar: dict[str, list[dict]] = {}
    for account in accounts:
        avatar = str(account.get("avatar") or "")
        if avatar and not any(g in avatar.casefold() for g in ("default", "placeholder", "identicon", "githubassets")):
            by_avatar.setdefault(avatar, []).append(account)
    for avatar, group in by_avatar.items():
        if not 2 <= len(group) <= 4:
            continue
        for index, left in enumerate(group):
            for right in group[index + 1:]:
                if left.get("platform") == right.get("platform"):
                    continue
                add(
                    "same_image_url",
                    left.get("ref", ""),
                    right.get("ref", ""),
                    "identical profile-image URL — image reuse is a clue, not identification",
                    CLUE,
                    avatar,
                    _excluded(dossier, left) or _excluded(dossier, right),
                )

    # 5. A source page the investigation read led directly to an account.
    sources = {s.get("id"): s for s in dossier.sources}
    for lead in dossier.leads:
        for account_id in (lead.get("produced") or {}).get("accounts", []):
            account = dossier.account(account_id)
            origin = _nearest_source(dossier, lead)
            if not account or not origin or origin not in sources:
                continue
            source = sources[origin]
            add(
                "led_to",
                source.get("id", ""),
                account.get("ref", ""),
                f"reading \"{(source.get('title') or source.get('url', ''))[:60]}\" led to the "
                f"{account.get('platform', '?')} account",
                MODERATE,
                source.get("url", ""),
                _excluded(dossier, account),
            )

    order = {STRONG: 0, MODERATE: 1, CLUE: 2}
    rows.sort(key=lambda r: (r["excluded_side"], order.get(r["strength"], 3)))
    return rows


def _lead_index(dossier) -> dict[str, dict]:
    return {lead.get("id"): lead for lead in dossier.leads if lead.get("id")}


def _nearest_source(dossier, lead: dict) -> str:
    """The closest ancestor lead (including itself) that produced a source."""
    index = _lead_index(dossier)
    current, hops = index.get(lead.get("parent", "")), 0
    while current is not None and hops < 12:
        produced = (current.get("produced") or {}).get("sources", [])
        if produced:
            return produced[0]
        current, hops = index.get(current.get("parent", "")), hops + 1
    return ""


def _producer(dossier, kind: str, record_id: str) -> dict | None:
    for lead in dossier.leads:
        if record_id in (lead.get("produced") or {}).get(kind, []):
            return lead
    return None


def _step(dossier, lead: dict) -> dict:
    args = lead.get("args") or {}
    produced = lead.get("produced") or {}
    step = {
        "lead_id": lead.get("id", ""),
        "type": lead.get("type", ""),
        "purpose": lead.get("purpose", ""),
        "origin": lead.get("origin", ""),
        "status": lead.get("status", ""),
        "query": args.get("query", ""),
        "url": args.get("url", "") or args.get("domain", ""),
        "produced": {k: len(v) for k, v in produced.items()},
    }
    if step["type"] == "web_search":
        from snoop.model import query_id

        for query in dossier.queries:
            if str(query.get("query", "")).casefold() == str(step["query"]).casefold() or query.get("id") == query_id(
                str(args.get("engine", "")), str(step["query"])
            ):
                step["results"] = len(query.get("results", []))
                step["provider"] = query.get("provider", query.get("engine", ""))
                break
    return step


def resolve(dossier, ref: str) -> tuple[str, dict] | None:
    """Find an account, source or evidence record by ref/id/url."""
    ref = (ref or "").strip()
    account = dossier.account(ref) if ref else None
    if account:
        return "accounts", account
    for source in dossier.sources:
        if ref in {source.get("id"), source.get("url")} or canonical_url(ref) == source.get("url"):
            return "sources", source
    for record in dossier.evidence_records:
        if record.get("id") == ref:
            return "evidence", record
    return None


def trace(dossier, ref: str) -> dict:
    """The discovery path that produced one account, source or evidence record."""
    found = resolve(dossier, ref)
    if not found:
        raise ValueError(f"nothing in this case matches {ref!r}; use an account ref (H01), source id or evidence id")
    kind, record = found
    record_id = record.get("account_id") if kind == "accounts" else record.get("id", "")
    item = {
        "kind": kind.rstrip("s") if kind != "evidence" else "evidence",
        "id": record_id,
        "label": (
            f"{record.get('ref', '')} {record.get('platform', '')} {record.get('canonical_url', '')}".strip()
            if kind == "accounts"
            else (record.get("title") or record.get("url", "")) if kind == "sources"
            else record.get("claim", "")
        ),
    }
    producer = _producer(dossier, kind, record_id)
    if producer is None and kind == "evidence":
        # Evidence is usually extracted from a source; trace that source.
        source_id = record.get("dependence", "")
        producer = _producer(dossier, "sources", source_id)
    steps: list[dict] = []
    index = _lead_index(dossier)
    current, hops = producer, 0
    while current is not None and hops < 15:
        steps.append(_step(dossier, current))
        current, hops = index.get(current.get("parent", "")), hops + 1
    steps.reverse()
    note = ""
    if not steps:
        origin = record.get("discovery_source") or record.get("via") or record.get("extraction_method") or "unknown"
        note = f"no recorded lead chain (older case or direct import); recorded origin: {origin}"
    return {"item": item, "steps": steps, "note": note}


def render_trace(result: dict) -> str:
    lines = [f"How SNOOP found: {result['item']['label']}"]
    for number, step in enumerate(result["steps"], 1):
        detail = step["query"] and f'"{step["query"]}"' or step["url"]
        extra = f" — {step['results']} result(s) via {step.get('provider', '')}" if "results" in step else ""
        lines.append(f"  {number}. [{step['origin']}] {step['type']}: {detail}{extra}")
        lines.append(f"     {step['purpose']}")
    if result.get("note"):
        lines.append("  " + result["note"])
    return "\n".join(lines)
