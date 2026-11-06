"""Typed, case-aware actions shared by CLI, chat, and web."""

from __future__ import annotations

import html
import json
import re
from dataclasses import asdict
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

from snoop.config import DATA_DIR, config
from snoop.core import Bus, Http, UnsafeUrl, validate_public_url
from snoop.enum import _SITES, Hit
from snoop.extract import enrich_hit
from snoop.model import canonical_url, ensure_account, evidence_record, stable_account_id, utcnow
from snoop.pipeline import Dossier, apply_assessments


def _site_for(url: str) -> dict | None:
    host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
    for site in _SITES:
        sample = site["url"].replace("{}", "sample")
        known = (urlsplit(sample).hostname or "").casefold().removeprefix("www.")
        if host == known or host.endswith("." + known) or known.endswith("." + host):
            return site
    return None


def _handle_from_url(url: str) -> str:
    path = urlsplit(url).path.strip("/")
    return (path.split("/")[-1] if path else (urlsplit(url).hostname or "").split(".")[0]).lstrip(
        "@$"
    )


def _profile_handle(url: str, site: dict) -> str:
    """Match a URL against the connector's profile shape and return its identifier."""
    actual = urlsplit(url)
    template = urlsplit(site["url"])
    actual_host = (actual.hostname or "").casefold().removeprefix("www.")
    template_host = (template.hostname or "").casefold().removeprefix("www.")
    placeholder = r"(?P<handle>[A-Za-z0-9._@-]+)"
    if "{}" in template_host:
        host_pattern = re.escape(template_host).replace(r"\{\}", placeholder)
        if match := re.fullmatch(host_pattern, actual_host):
            return unquote(match.group("handle")).lstrip("@$.")
        return ""
    if actual_host != template_host:
        return ""
    if "{}" in template.path:
        path_pattern = re.escape(template.path.rstrip("/")).replace(r"\{\}", placeholder)
        if match := re.fullmatch(path_pattern, actual.path.rstrip("/")):
            return unquote(match.group("handle")).lstrip("@$.")
        return ""
    if "{}" in template.query:
        template_query = parse_qs(template.query)
        actual_query = parse_qs(actual.query)
        key = next((name for name, values in template_query.items() if "{}" in values), "")
        return str(actual_query.get(key, [""])[0]).lstrip("@$") if key else ""
    return _handle_from_url(url)


async def anchor(
    dossier: Dossier, url: str, bus: Bus | None = None, *, discovery_source: str = "user-anchor"
) -> str:
    bus = bus or Bus()
    site = _site_for(url)
    if not site:
        raise ValueError("anchor URL is not for a supported connector")
    handle = _profile_handle(url, site)
    if not handle:
        raise ValueError("anchor URL does not match this connector's public profile URL shape")
    await validate_public_url(url)
    canonical = canonical_url(url)
    if any(h.get("canonical_url") == canonical for h in dossier.all_accounts):
        return "anchor already exists in this case"
    async with Http(concurrency=4) as http:
        response = await http.get(url, safe=True)
        if response.outcome != "found":
            # Record the failure honestly so callers can keep the exact-name
            # result as an unverified lead instead of dropping it.
            dossier.record_action("anchor_unavailable", url=url, outcome=response.outcome)
            return f"anchor is {response.outcome}; no account was added"
        hit = Hit(
            site["name"],
            site.get("cat", "other"),
            response.final_url or url,
            data_url=site.get("data", "").replace("{}", handle),
            parse=site.get("parse", ""),
            status=response.status,
            ms=response.elapsed_ms,
            matched_handle=handle,
            discovery_source=discovery_source,
            canonical_url=canonical,
            platform_id=handle,
            account_id=stable_account_id(site["name"], canonical, handle),
            retrieved_at=response.retrieved_at,
        )
        hit.extra["matched_handle"] = handle
        await enrich_hit(http, hit, bus)
    row = hit.to_dict()
    row["original_search_input"] = dossier.target
    ensure_account(row, {h.get("ref") for h in dossier.all_accounts})
    pool = dossier.all_accounts + [row]
    apply_assessments(dossier, pool)
    record = evidence_record(
        account_id=row["account_id"],
        claim="user-supplied-anchor",
        source_url=canonical,
        value=canonical,
        method="user-input",
        kind="user_hint",
        strength=0,
        limitation="An anchor confirms scope and account existence, not ownership.",
    )
    dossier.evidence_records.append(record)
    row.setdefault("evidence", []).append(
        {
            "points": 0,
            "label": "anchor",
            "detail": "explicitly supplied by the user as a reference profile",
            "evidence_id": record["id"],
            "source_url": canonical,
            "dependence": record["id"],
            "supports": None,
            "limitation": record["limitation"],
        }
    )
    dossier.record_action("anchor", account_id=row["account_id"], source_url=canonical)
    dossier.save()
    return f"added {row['ref']} ({row['platform']}) as a user-provided anchor; ownership remains {row['ownership_status']}"


async def search(dossier: Dossier, context: str, bus: Bus | None = None, budget: int = 5) -> str:
    if not config.brave_search_key:
        return "Brave Search is not configured. Set BRAVE_SEARCH_API_KEY; existing username discovery remains available."
    bus = bus or Bus()
    query = " ".join(x for x in [dossier.target, context] if x).strip()
    async with Http(concurrency=2) as http:
        response = await http.get(
            "https://api.search.brave.com/res/v1/web/search?q="
            + quote(query)
            + "&count=10&safesearch=strict",
            headers={"X-Subscription-Token": config.brave_search_key},
            want_json=True,
            credentials_for="api.search.brave.com",
        )
    if response.outcome != "found" or not isinstance(response.json, dict):
        if response.status in {401, 403}:
            return "search provider authentication failed; no candidates added"
        return f"search provider {response.outcome}; no candidates added"
    urls = []
    for item in response.json.get("web", {}).get("results", []):
        url = item.get("url", "") if isinstance(item, dict) else ""
        if url and _site_for(url):
            urls.append(url)
    added = 0
    for url in list(dict.fromkeys(urls))[: max(1, min(budget, 10))]:
        before = len(dossier.all_accounts)
        try:
            await anchor(dossier, url, bus, discovery_source="brave-search")
        except (ValueError, UnsafeUrl):
            continue
        added += len(dossier.all_accounts) > before
    dossier.record_action(
        "search", context=context, provider="brave", candidates=len(urls), added=added
    )
    dossier.save()
    return f"Brave returned {len(urls)} supported profile clue(s); fetched and added {added} validated candidate(s)"


def show_evidence(dossier: Dossier, ref: str) -> dict:
    account = dossier.account(ref)
    if not account:
        raise ValueError(f"unknown account reference {ref!r}")
    ids = {e.get("evidence_id") for e in account.get("evidence", [])}
    records = [
        r
        for r in dossier.evidence_records
        if r.get("account_id") == account["account_id"] or r.get("id") in ids
    ]
    return {
        "account": {
            k: account.get(k)
            for k in (
                "ref",
                "account_id",
                "platform",
                "platform_id",
                "matched_handle",
                "canonical_url",
                "observation_status",
                "ownership_status",
                "evidence_score",
            )
        },
        "evidence": records,
        "conflicts": [r for r in records if r.get("supports") is False],
        "limitations": account.get("limitations", []),
    }


def compare(dossier: Dossier, left: str, right: str) -> dict:
    a, b = dossier.account(left), dossier.account(right)
    if not a or not b:
        raise ValueError("both account references must exist in the active case")
    shared_links = sorted(
        set(map(canonical_url, a.get("links", []))) & set(map(canonical_url, b.get("links", [])))
    )
    cross = canonical_url(b.get("canonical_url", "")) in set(
        map(canonical_url, a.get("links", []))
    ) or canonical_url(a.get("canonical_url", "")) in set(map(canonical_url, b.get("links", [])))
    return {
        "left": show_evidence(dossier, left),
        "right": show_evidence(dossier, right),
        "supporting": (["explicit profile cross-link"] if cross else [])
        + ([f"shared linked URL: {x}" for x in shared_links]),
        "conflicting": [
            x
            for x in [
                "different displayed names"
                if a.get("display_name")
                and b.get("display_name")
                and a["display_name"].casefold() != b["display_name"].casefold()
                else "",
                "different locations"
                if a.get("location")
                and b.get("location")
                and a["location"].casefold() != b["location"].casefold()
                else "",
            ]
            if x
        ],
        "conclusion": "Candidates remain separate unless the evidence and user constraints support a merge.",
    }


async def verify(dossier: Dossier, ref: str, bus: Bus | None = None) -> str:
    account = dossier.account(ref)
    if not account:
        return f"unknown account reference {ref!r}"
    async with Http(concurrency=2) as http:
        result = await http.get(account["canonical_url"], safe=True)
    previous = account.get("observation_status", "found")
    account["last_verification"] = {
        "at": utcnow(),
        "outcome": result.outcome,
        "status": result.status,
        "previous": previous,
        "from_cache": result.from_cache,
    }
    account["observation_status"] = result.outcome
    record = evidence_record(
        account_id=account["account_id"],
        claim="account-existence",
        source_url=account["canonical_url"],
        value=result.outcome,
        method="verification",
        supports=True
        if result.outcome == "found"
        else (False if result.outcome == "not_found" else None),
        limitation="Unavailable observations are inconclusive.",
    )
    dossier.evidence_records.append(record)
    dossier.record_action("verify", account_id=account["account_id"], outcome=result.outcome)
    dossier.save()
    return f"{account['ref']} current observation: {result.outcome} (HTTP {result.status or 'none'}); ownership remains {account['ownership_status']}"


async def follow(
    dossier: Dossier, ref: str, bus: Bus | None = None, depth: int = 1, budget: int = 8
) -> str:
    origin = dossier.account(ref)
    if not origin:
        return f"unknown account reference {ref!r}"
    depth, budget = max(1, min(depth, 2)), max(1, min(budget, 12))
    queue = [(origin, 0)]
    visited = {origin["canonical_url"]}
    added = attempted = 0
    while queue and attempted < budget:
        source, level = queue.pop(0)
        if level >= depth:
            continue
        for url in source.get("links", []):
            canonical = canonical_url(url)
            if canonical in visited or not _site_for(url):
                continue
            visited.add(canonical)
            attempted += 1
            before = {h["account_id"] for h in dossier.all_accounts}
            try:
                await anchor(dossier, url, bus, discovery_source=f"follow:{source['account_id']}")
            except (ValueError, UnsafeUrl):
                continue
            found = next((h for h in dossier.all_accounts if h["account_id"] not in before), None)
            if found:
                added += 1
                queue.append((found, level + 1))
            if attempted >= budget:
                break
    dossier.record_action(
        "follow",
        account_id=origin["account_id"],
        depth=depth,
        attempted=attempted,
        added=added,
        budget=budget,
    )
    dossier.save()
    return f"followed {attempted}/{budget} supported link(s), added {added} validated candidate(s); cycles and duplicates skipped"


async def deepen_account(dossier: Dossier, ref: str, bus: Bus | None = None) -> str:
    from snoop.deepen import deepen

    account = dossier.account(ref)
    if not account:
        return f"unknown account reference {ref!r}"
    handle = account.get("matched_handle") or account.get("platform_id")
    async with Http(concurrency=3) as http:
        facts = await deepen(http, account["platform"], handle)
    facts.update(
        account_id=account["account_id"], account_ref=account["ref"], retrieved_at=utcnow()
    )
    account["enrichment"] = facts
    dossier.deep[account["account_id"]] = facts
    dossier.record_action(
        "deepen", account_id=account["account_id"], supported=bool(facts.get("summary"))
    )
    dossier.save()
    if bus:
        await bus.emit("deepen", account=account["ref"], facts=facts)
    return facts.get("summary") or f"deep enrichment is unsupported for {account['platform']}"


def timeline(dossier: Dossier, identity_label: str = "") -> list[dict]:
    identity = next(
        (
            i
            for i in dossier.analysis.get("identities", [])
            if str(i.get("label", "")).casefold() == identity_label.casefold()
            or str(i.get("id", "")).casefold() == identity_label.casefold()
        ),
        None,
    )
    account_ids = (
        set(identity.get("account_ids", []))
        if identity
        else {h["account_id"] for h in dossier.hits}
    )
    events = []
    for account in dossier.hits:
        if account["account_id"] not in account_ids:
            continue
        if account.get("joined"):
            events.append(
                {
                    "event_time": account["joined"],
                    "retrieved_at": account.get("retrieved_at"),
                    "account_ref": account["ref"],
                    "event": "public account join date",
                    "source_url": account["canonical_url"],
                    "speculative": False,
                }
            )
        for event in account.get("enrichment", {}).get("events", []):
            if isinstance(event, dict) and event.get("source_url") and event.get("event_time"):
                events.append({**event, "account_ref": account["ref"], "speculative": False})
    # Case-level evidence with its own event time (archive captures, dated mentions).
    for record in dossier.evidence_records:
        event_time = record.get("source_event_time")
        if not event_time or not record.get("source_url"):
            continue
        if record.get("account_id") and record["account_id"] not in account_ids:
            continue
        events.append(
            {
                "event_time": event_time,
                "retrieved_at": record.get("retrieved_at"),
                "event": record.get("claim", "observed event"),
                "source_url": record["source_url"],
                "evidence_id": record.get("id"),
                "speculative": False,
            }
        )
    return sorted(events, key=lambda x: str(x.get("event_time", "")))


def build_graph(dossier: Dossier) -> dict:
    """Source-linked relationship graph. Every edge carries its provenance;
    co-occurrence alone never creates an edge."""
    from snoop.evidence import tokens

    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def node(node_id: str, **props) -> str:
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, **props}
        return node_id

    {h.get("ref"): h for h in dossier.all_accounts}
    source_by_url = {s.get("url"): s for s in dossier.sources}

    for source in dossier.sources:
        node(
            source["id"],
            kind="source",
            label=source.get("title") or (urlsplit(source["url"]).hostname or source["url"]),
            url=source["url"],
            outcome=source.get("outcome"),
            via=source.get("via"),
        )

    for account in dossier.all_accounts:
        node(
            account["account_id"],
            kind="account",
            label=account.get("ref", ""),
            platform=account.get("platform"),
            url=account.get("canonical_url"),
            verdict=account.get("verdict"),
            ownership=account.get("ownership_status"),
        )
        discovered = str(account.get("discovery_source", ""))
        for prefix in ("search:", "brave-search", "follow:"):
            if discovered.startswith(prefix):
                edges.append(
                    {
                        "type": "discovered_via",
                        "from": account["account_id"],
                        "to": _graph_source_for(discovered, source_by_url, account),
                        "provenance": discovered,
                    }
                )
                break

    for identity in dossier.analysis.get("identities", []):
        identity_id = node(
            identity.get("id") or identity.get("label", "?"),
            kind="identity",
            label=identity.get("label", "?"),
            name=identity.get("name", ""),
            status=identity.get("status", "unresolved"),
            selected=bool(identity.get("selected")),
        )
        for account_id in identity.get("account_ids", []):
            edges.append(
                {
                    "type": "account_of" if identity.get("selected") else "candidate_of",
                    "from": account_id,
                    "to": identity_id,
                    "provenance": ", ".join(identity.get("evidence_ids", [])[:3]) or "grouping",
                }
            )
        if identity.get("selected"):
            edges.append(
                {
                    "type": "user_selected",
                    "from": "user",
                    "to": identity_id,
                    "provenance": "manual pick (a decision, not verification)",
                }
            )

    by_ref = {h.get("ref"): h for h in dossier.all_accounts}
    for account in dossier.all_accounts:
        for ev in account.get("evidence", []):
            if ev.get("label") != "cross-link" or (ev.get("points") or 0) < 18:
                continue
            other = by_ref.get(str(ev.get("detail", "")).rsplit(" ", 1)[-1])
            if other:
                edges.append(
                    {
                        "type": "links_to",
                        "from": account["account_id"],
                        "to": other["account_id"],
                        "provenance": ev.get("evidence_id") or ev.get("source_url", "cross-link"),
                    }
                )

    subject_tokens = set(tokens(dossier.target))
    for source in dossier.sources:
        author = (source.get("extra") or {}).get("author", "")
        if not author:
            continue
        author_tokens = set(tokens(author))
        for account in dossier.all_accounts:
            name_tokens = set(tokens(account.get("display_name", "")))
            if name_tokens and author_tokens and name_tokens == author_tokens:
                edges.append(
                    {
                        "type": "authored",
                        "from": account["account_id"],
                        "to": source["id"],
                        "provenance": f"author metadata on {source['url']}",
                    }
                )
                break

    for record in dossier.evidence_records:
        claim = str(record.get("claim", ""))
        if not claim.startswith("mentioned-in"):
            continue
        target_id = source_by_url.get(record.get("source_url"), {}).get(
            "id", f"src:{canonical_url(record.get('source_url', ''))}"
        )
        edges.append(
            {
                "type": "mentioned_in",
                "from": "subject",
                "to": target_id,
                "provenance": record.get("id", ""),
            }
        )
        _ = subject_tokens

    return {
        "nodes": list(nodes.values()) + (
            [{"id": "user", "kind": "user", "label": "analyst"},
             {"id": "subject", "kind": "subject", "label": dossier.target}]
            if edges and any(e["from"] in {"user", "subject"} or e["to"] in {"user", "subject"} for e in edges)
            else []
        ),
        "edges": [e for e in edges if e.get("to")],
    }


def _graph_source_for(discovered: str, source_by_url: dict, account: dict) -> str:
    for source in source_by_url.values():
        if source.get("url") in discovered or discovered.endswith(source.get("url", "\0")):
            return source["id"]
    return discovered


def list_aliases(dossier: Dossier) -> list[dict]:
    """Every alias the case knows about, with where it came from."""
    rows: dict[str, dict] = {}
    for handle in dossier.handles_tried or []:
        rows.setdefault(
            handle.casefold(),
            {"alias": handle, "origin": "user-supplied target / name-derived guess", "used": True},
        )
    for account in dossier.all_accounts:
        handle = str(account.get("matched_handle") or "")
        if handle:
            origin = {
                "user-anchor": "user-supplied anchor",
                "username-enumeration": "platform enumeration",
            }.get(
                account.get("discovery_source", ""),
                f"discovered via {account.get('discovery_source', 'investigation')}",
            )
            rows.setdefault(handle.casefold(), {"alias": handle, "origin": origin, "used": True})
    for lead in dossier.leads:
        for handle in lead.get("args", {}).get("handles", []) or []:
            if str(lead.get("args", {}).get("origin", "")).startswith("source"):
                rows.setdefault(
                    handle.casefold(),
                    {"alias": handle, "origin": "found in a source", "used": False},
                )
    for query in dossier.queries:
        match = re.match(r'^"([^"]{3,40})"$', query.get("query", ""))
        if match and not re.search(r"\s", match.group(1)):
            rows.setdefault(
                match.group(1).casefold(),
                {
                    "alias": match.group(1),
                    "origin": f'searched as a quoted alias ({query.get("provider")})',
                    "used": True,
                },
            )
    for source in dossier.sources:
        for person in (source.get("extra") or {}).get("persons", []) or []:
            for alias in person.get("alternate_names", []) or []:
                rows.setdefault(
                    alias.casefold(),
                    {"alias": alias, "origin": "structured data assertion (hypothesis)", "used": False},
                )
    return sorted(rows.values(), key=lambda r: r["alias"])


def case_overview(dossier: Dossier) -> dict:
    from snoop import interview

    accounts = [
        {
            "ref": h.get("ref"),
            "platform": h.get("platform"),
            "handle": h.get("matched_handle"),
            "url": h.get("canonical_url"),
            "verdict": h.get("verdict"),
            "ownership": h.get("ownership_status"),
            "score": h.get("evidence_score", h.get("score", 0)),
            "discovery_source": h.get("discovery_source"),
        }
        for h in dossier.all_accounts
    ]
    return {
        "case_id": dossier.id,
        "target": dossier.target,
        "kind": dossier.kind,
        "mode": dossier.mode,
        "context": dossier.context,
        "workflow": dossier.workflow,
        "subject": interview.subject_status(dossier),
        "pending_question": interview.pending(dossier),
        "accounts": accounts,
        "queries": [
            {
                "id": q.get("id"),
                "engine": q.get("engine"),
                "provider": q.get("provider"),
                "query": q.get("query"),
                "outcome": q.get("outcome"),
                "results": len(q.get("results", [])),
            }
            for q in dossier.queries
        ],
        "sources": [
            {
                "id": s.get("id"),
                "url": s.get("url"),
                "title": s.get("title"),
                "outcome": s.get("outcome"),
                "via": s.get("via"),
                "content_type": s.get("content_type"),
            }
            for s in dossier.sources
        ],
        "coverage": coverage_statement(dossier),
    }


def coverage_statement(dossier: Dossier) -> dict:
    by_engine: dict[str, int] = {}
    for query in dossier.queries:
        by_engine[query.get("engine", "?")] = by_engine.get(query.get("engine", "?"), 0) + 1
    unavailable = [s for s in dossier.sources if s.get("outcome") != "found"]
    pending = [lead for lead in dossier.leads if lead.get("status") in {"pending", "deferred"}]
    return {
        "queries_by_engine": by_engine,
        "sources_read": len([s for s in dossier.sources if s.get("outcome") == "found"]),
        "unavailable_sources": len(unavailable),
        "pending_leads": len(pending),
        "exhaustive": False,
        "note": "Coverage is bounded by the configured budgets and providers; "
        "this is not an exhaustive internet search.",
    }


def case_report(dossier: Dossier) -> dict:
    """The readable wrap-up: what was found, why it matters, what is uncertain,
    and what to investigate next."""
    from snoop import interview
    from snoop.leads import LeadQueue

    queue = LeadQueue(dossier)
    insufficient = [h for h in dossier.hits if h.get("verdict") == "insufficient"]
    unresolved = [
        i
        for i in dossier.analysis.get("identities", [])
        if not i.get("selected") and i.get("status") == "unresolved"
    ]
    hypotheses = [
        {"identity": i.get("label"), **m}
        for i in dossier.analysis.get("identities", [])
        for m in i.get("membership_hypotheses", [])
    ]
    frontier = [
        {"type": l["type"], "purpose": l["purpose"], "score": l.get("score", 0)}
        for l in sorted(queue.pending(), key=lambda x: -float(x.get("score", 0)))[:8]
    ]
    findings = []
    for record in dossier.evidence_records:
        if record.get("kind") == "observation" and record.get("supports") and record.get("excerpt"):
            findings.append(
                {
                    "claim": record.get("claim"),
                    "excerpt": record.get("excerpt"),
                    "source_url": record.get("source_url"),
                    "evidence_id": record.get("id"),
                    "retrieved_at": record.get("retrieved_at"),
                }
            )
    return {
        "case_id": dossier.id,
        "target": dossier.target,
        "subject": interview.subject_status(dossier),
        "mode": dossier.mode,
        "summary": dossier.analysis.get("summary", ""),
        "identities": [
            {
                "label": i.get("label"),
                "name": i.get("name"),
                "status": i.get("status"),
                "selected": bool(i.get("selected")),
                "evidence_score": i.get("evidence_score", 0),
                "accounts": i.get("account_ids", []),
            }
            for i in dossier.analysis.get("identities", [])
        ],
        "findings": findings[:30],
        "unresolved_questions": {
            "pending_question": interview.pending(dossier),
            "insufficient_accounts": [h.get("ref") for h in insufficient],
            "unresolved_identities": [i.get("label") for i in unresolved],
            "membership_hypotheses": hypotheses,
            "snippet_only": [
                {"url": s.get("url"), "title": s.get("title"), "snippet": (s.get("extra") or {}).get("snippet", "")}
                for s in dossier.sources
                if (s.get("extra") or {}).get("snippet_only")
            ],
            "rejected_similar_name_matches": list(dossier.analysis.get("rejected_matches", [])),
        },
        "coverage": coverage_statement(dossier),
        "next_steps": frontier,
        "workflow": dossier.workflow,
    }


def diff_cases(before: Dossier, after: Dossier) -> dict:
    def keyed(case):
        return {r.get("id"): r for r in case.evidence_records if r.get("id")}

    old, new = keyed(before), keyed(after)
    changed = []
    for key in old.keys() & new.keys():
        if {k: old[key].get(k) for k in ("value", "excerpt", "supports")} != {
            k: new[key].get(k) for k in ("value", "excerpt", "supports")
        }:
            changed.append({"before": old[key], "after": new[key]})
    inconclusive = {"blocked", "rate_limited", "unavailable", "parse_failure"}
    unavailable_accounts = [
        h["ref"] for h in after.all_accounts if h.get("observation_status") in inconclusive
    ]
    removed = [
        old[k]
        for k in old.keys() - new.keys()
        if old[k].get("account_id")
        not in {
            h["account_id"]
            for h in after.all_accounts
            if h.get("observation_status") in inconclusive
        }
    ]
    unavailable = [
        old[k]
        for k in old.keys() - new.keys()
        if old[k].get("account_id")
        in {
            h["account_id"]
            for h in after.all_accounts
            if h.get("observation_status") in inconclusive
        }
    ]
    return {
        "before": before.id,
        "after": after.id,
        "new": [new[k] for k in new.keys() - old.keys()],
        "changed": changed,
        "no_longer_observed": removed,
        "unavailable": unavailable,
        "unavailable_accounts": unavailable_accounts,
        "unchanged": len(old.keys() & new.keys()) - len(changed),
    }


class Redactor:
    def __init__(self, values: list[str]):
        self.values = sorted(
            {v for v in values if v}, key=lambda item: (-len(item), item.casefold())
        )
        self.aliases = {value: f"PERSONAL_{i + 1}" for i, value in enumerate(self.values)}

    def text(self, value: str) -> str:
        out = str(value)
        for raw, alias in self.aliases.items():
            out = re.sub(re.escape(raw), alias, out, flags=re.IGNORECASE)
        return out

    def obj(self, value):
        if isinstance(value, dict):
            return {self.text(str(k)): self.obj(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.obj(v) for v in value]
        if isinstance(value, str):
            return self.text(value)
        return value


def export_case(dossier: Dossier, redact: bool = False) -> dict:
    import hashlib

    report_dir = DATA_DIR / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = asdict(dossier)
    from snoop.privacy import case_identifiers

    identifiers = [*case_identifiers(dossier), *config.redact_values]
    redactor = Redactor(identifiers) if redact else Redactor([])
    payload = redactor.obj(payload)
    basename = (
        "case-" + hashlib.sha256(dossier.id.encode()).hexdigest()[:10] + "-redacted"
        if redact
        else dossier.id
    )
    json_path = report_dir / f"{basename}.json"
    html_path = report_dir / f"{basename}.html"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), "utf-8")
    rows = "".join(
        f"<li><a href='{html.escape(str(h.get('canonical_url', '')), quote=True)}'>{html.escape(str(h.get('ref')))} {html.escape(str(h.get('platform')))}</a> — {html.escape(str(h.get('ownership_status')))} (evidence score {h.get('evidence_score', 0)})</li>"
        for h in payload["hits"]
    )
    body = f"<!doctype html><meta charset='utf-8'><title>SNOOP report</title><h1>Case {html.escape(payload['id'])}</h1><p>Collected {html.escape(payload['created'])}. Evidence scores are not probabilities. Unavailable sources are inconclusive.</p><ul>{rows}</ul><pre>{html.escape(json.dumps(payload.get('analysis', {}), indent=2, ensure_ascii=False))}</pre>"
    html_path.write_text(body, "utf-8")
    dossier.record_action("export", redacted=redact)
    dossier.save()
    return {"json": str(json_path), "html": str(html_path), "redacted": redact}


def doctor() -> dict:
    """Diagnostics without secrets: versions, paths, configuration and readiness."""
    import platform as _platform
    import sys
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _pkg_version
    from importlib.util import find_spec

    from snoop import __version__

    package_root = Path(__file__).resolve().parent
    installed = ""
    install_note = ""
    try:
        installed = _pkg_version("snoop-osint")
        if installed != __version__:
            install_note = (
                f"installed metadata says {installed} but running code is {__version__}; "
                "re-run 'python -m pip install -e .' so the entry point matches this checkout"
            )
    except PackageNotFoundError:
        install_note = "not installed as a package; running directly from the source tree"
    env_candidates = [
        Path.cwd() / ".env",
        package_root.parent / ".env",
    ]
    seen_env: set[str] = set()
    env_candidates = [p for p in env_candidates if not (str(p) in seen_env or seen_env.add(str(p)))]
    try:
        connectors = len(json.loads((package_root / "data" / "sites.json").read_text("utf-8"))["sites"])
    except Exception:
        connectors = 0

    return {
        "ok": (package_root / "data" / "sites.json").is_file()
        and (package_root / "data" / "index.html").is_file()
        and connectors > 0,
        "version": {
            "snoop": __version__,
            "installed_package": installed or "none",
            "install_note": install_note,
            "python": sys.version.split()[0],
            "python_executable": sys.executable,
            "platform": _platform.platform(),
        },
        "package": {
            "loaded_from": str(package_root),
            "web_assets": (package_root / "data" / "index.html").is_file(),
        },
        "configuration": {
            "env_files_checked": [str(p) for p in env_candidates],
            "env_files_present": [str(p) for p in env_candidates if p.is_file()],
            "data_dir": str(DATA_DIR),
            "case_dir": str(DATA_DIR / "dossiers"),
            "saved_cases": len(list((DATA_DIR / "dossiers").glob("*.json"))),
            "search_engine_preference": config.search_engine,
        },
        "assets": {"sites_json": (package_root / "data" / "sites.json").is_file(), "connectors": connectors},
        "guards": {},
        "dependencies": {
            name: find_spec(name) is not None
            for name in ("aiohttp", "bs4", "rich", "dotenv", "pypdf", "PIL", "pytesseract")
        },
        "providers": providers_status()["providers"],
        "network_checks": "not run",
    }


def providers_status() -> dict:
    """Provider readiness, names only — never secret values."""
    from snoop import search as search_mod

    config.refresh_provider_credentials()
    return {
        "search": {
            "engines": search_mod.available_engines(),
            "preference": config.search_engine,
            "fallback": "enabled" if config.search_fallback else "disabled",
            "any_ready": search_mod.any_engine_ready(),
        },
        "providers": {
            "ai": config.ai_provider() or "not configured",
            "ai_model": {"openai": config.openai_model, "anthropic": config.anthropic_model,
                         "gemini": config.gemini_model, "ollama": config.ollama_model,
                         }.get(config.ai_provider(), ""),
            "ollama_base_url": config.ollama_base_url if config.ai_provider() == "ollama" else "",
            "reasoning_effort": config.reasoning_effort,
            "brave_search": "configured" if config.brave_search_key else "not configured",
            "google_via_serpapi": "configured" if config.serpapi_key else "not configured",
            "github": "configured" if config.github_token else "anonymous",
            "hibp": "configured" if config.hibp_key else "not configured",
            "ocr": "available" if __import__("snoop.discover", fromlist=["ocr_available"]).ocr_available() else "optional dependency not installed",
        },
        "presets": __import__("snoop.workflow", fromlist=["PRESETS"]).PRESETS,
    }
