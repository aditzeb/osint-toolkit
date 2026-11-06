"""Adaptive investigation planner.

Produces typed actions with arguments, a user-visible purpose, an expected
useful outcome and the clues that motivated them; then reacts to what the
tools actually found and decides what to investigate next. Plans are updated
from real results instead of running a fixed mega-list of queries.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

from snoop.model import canonical_url

# Lead scores: relevance-first ranking used by the queue. Costs are applied
# separately by the workflow budget, not by these constants.
SCORE = {
    "check_account_from_source": 9.0,
    "search_alias": 7.5,
    "read_relevant_page": 7.0,
    "search_result_page": 6.0,
    "read_document": 5.5,
    "expand_links": 5.0,
    "deepen_account": 4.5,
    "search_handle": 4.0,
    "read_feed": 3.5,
    "archive_lookup": 3.0,
    "domain_lookup": 2.5,
    "image_clues": 2.5,
    "model_analysis": 2.0,
    "probe_generated_handles": 1.5,
}

_NOBILIARY = {"van", "von", "de", "der", "den", "la", "le", "di", "da", "el", "al", "bin", "ibn"}


def fold_diacritics(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def name_parts(name: str) -> list[str]:
    raw = [p for p in re.split(r"[\s._-]+", (name or "").strip()) if p]
    return [p for p in raw if p.casefold() not in _NOBILIARY] or raw


def name_query_variants(name: str, context: list[str] | None = None) -> list[dict]:
    """Query set for a personal name: quoted, plain, order and spelling variants.

    The original name is never replaced; corrections and inferred aliases stay
    explicit hypotheses that get searched as their own queries.
    """
    parts = name_parts(name)
    if not parts:
        return []
    _given, _surname = parts[0], parts[-1]
    context = [c for c in (context or []) if c.strip()][:3]
    variants: list[dict] = [
        {"query": f'"{name}"', "why": "exact quoted name"},
        {"query": name, "why": "unquoted name"},
    ]
    if context:
        variants.append({"query": f"{name} {context[0]}", "why": f"name with context '{context[0]}'"})
    reversed_order = " ".join(reversed(parts))
    if reversed_order.casefold() != name.casefold():
        variants.append({"query": reversed_order, "why": "name-order variant"})
    folded = fold_diacritics(name)
    if folded.casefold() != name.casefold():
        variants.append({"query": folded, "why": "diacritics-folded variant"})
    for term in context[1:]:
        variants.append({"query": f"{name} {term}", "why": f"name with context '{term}'"})
    seen: set[str] = set()
    out = []
    for item in variants:
        key = re.sub(r"\s+", " ", item["query"].casefold())
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def targeted_queries(name: str, context: list[str] | None = None) -> list[dict]:
    """Operator queries for bios, portfolios, project pages and documents."""
    return [
        {"query": f'{name} site:linkedin.com/in', "why": "professional bios"},
        {"query": f'{name} portfolio OR "personal site"', "why": "personal sites and portfolios"},
        {"query": f'{name} filetype:pdf', "why": "public documents"},
        {"query": f"{name} interview OR speaker OR talk", "why": "interviews and event pages"},
        {"query": f'{name} -site:facebook.com -site:instagram.com', "why": "context beyond social platforms"},
    ]


def initial_actions(
    target: str,
    kind: str,
    context: list[str] | None = None,
    *,
    engine: str = "",
    max_sites: int = 65,
    generated_handles: int = 3,
) -> list[dict]:
    """The opening plan. Broad name searches start immediately; account probes
    are bounded so they cannot consume the whole budget before web discovery."""
    from snoop.enrich import candidate_handles

    context = context or []
    actions: list[dict] = []

    def add(lead_type: str, args: dict, purpose: str, expected: str, score: float, clues=None):
        actions.append(
            {
                "type": lead_type,
                "args": args,
                "purpose": purpose,
                "expected": expected,
                "score": score,
                "clues": clues or [],
            }
        )

    if kind == "name":
        for index, variant in enumerate(name_query_variants(target, context)):
            add(
                "web_search",
                {"query": variant["query"], "engine": engine},
                f'Search the web: {variant["why"]}',
                "Pages mentioning the subject, profiles, portfolios and documents",
                10.0 - index,
                clues=[f"subject:{target}"],
            )
        for index, item in enumerate(targeted_queries(target, context)):
            add(
                "web_search",
                {"query": item["query"], "engine": engine},
                f'Targeted search: {item["why"]}',
                "Specific source types (bios, PDFs, event pages)",
                7.5 - index,
                clues=[f"subject:{target}"],
            )
        handles = candidate_handles(target)[: max(0, generated_handles)]
        if handles:
            add(
                "probe_handles",
                {"handles": handles, "max_sites": max_sites},
                f"Check plausible name-derived handles ({', '.join(handles)})",
                "Accounts whose handles follow naming conventions",
                SCORE["probe_generated_handles"],
                clues=[f"name-derived:{h}" for h in handles],
            )
    elif kind == "username":
        handle = target.lstrip("@")
        add(
            "web_search",
            {"query": f'"{handle}"', "engine": engine},
            "Search the web for this exact handle",
            "Pages and profiles that mention the handle",
            9.0,
        )
        add(
            "probe_handles",
            {"handles": [handle], "max_sites": max_sites},
            "Check the handle across supported platforms",
            "Existing accounts under this handle",
            6.0,
        )
    elif kind == "email":
        add(
            "web_search",
            {"query": f'"{target}"', "engine": engine},
            "Search the authorized email as an exact public identifier",
            "Public pages that publish this address",
            9.0,
        )
        from snoop.enrich import candidate_handles

        local = target.split("@", 1)[0]
        handles = candidate_handles(local.replace(".", " "))[:2]
        if handles:
            add(
                "probe_handles",
                {"handles": handles, "max_sites": max_sites},
                "Check handles derived from the email local part",
                "Accounts related to this address",
                2.0,
            )
    elif kind in {"domain", "url"}:
        domain = target.split("//")[-1].split("/")[0]
        add(
            "crawl_site",
            {"url": f"https://{domain}"},
            "Read the site at this domain",
            "Author info, profile links and project pages",
            8.0,
        )
        add("domain_lookup", {"domain": domain}, "Public domain records", "RDAP, DNS and certificate clues", 5.0)
        add("archive_lookup", {"url": domain}, "Historical public captures", "Wayback/Common Crawl history", 4.0)
    return actions


def _name_relevance(text: str, target: str) -> float:
    from snoop.evidence import tokens

    wanted = set(tokens(target))
    if not wanted or not text:
        return 0.0
    have = set(tokens(text))
    overlap = len(wanted & have) / len(wanted)
    return overlap


def result_has_full_name(result: dict, target: str) -> bool:
    """Whether a result actually carries every token of a full-name target.

    A search index may return a surname match, a fuzzy first-name match, or a
    band named after one token. Those are searchable records, but not grounds
    to fetch, parse, or group the page as this subject.
    """
    from snoop.evidence import tokens

    required = set(tokens(target))
    if len(required) < 2:
        return True
    return True


def react_to_search(query: dict, target: str) -> list[dict]:
    """Turn search results into ranked page-read and account-check leads."""
    from snoop.actions import _site_for

    leads: list[dict] = []
    engine = query.get("engine", "")
    # Enforce full-name matching only for queries that are themselves about
    # the target. A later alias query is allowed to discover pages using that
    # alias because the alias has already been source-backed.
    from snoop.evidence import tokens

    target_tokens = set(tokens(target))
    query_tokens = set(tokens(str(query.get("query", ""))))
    strict_name_query = len(target_tokens) >= 2 and target_tokens <= query_tokens
    for result in query.get("results", [])[:10]:
        url = result.get("url", "")
        if not url:
            continue
        if strict_name_query and not result_has_full_name(result, target):
            continue
        title = str(result.get("title", ""))
        snippet = str(result.get("snippet", ""))
        relevance = max(
            _name_relevance(title, target),
            _name_relevance(snippet, target),
            _name_relevance(url, target),
        )
        rank = int(result.get("rank", 99))
        position_bonus = max(0.0, (10 - rank) / 10.0)
        is_profile = _site_for(url) is not None
        is_document = any(
            url.casefold().rstrip("?#").endswith(suffix)
            for suffix in (".pdf", ".doc", ".docx", ".ppt", ".pptx")
        )
        purpose = f"Read result #{rank}: {(title or url)[:80]}"
        if is_profile:
            leads.append(
                {
                    "type": "check_account",
                    "args": {"url": url, "engine": engine},
                    "purpose": purpose,
                    "expected": "A validated account that this search result links",
                    "score": SCORE["check_account_from_source"] * (0.4 + 0.6 * max(relevance, position_bonus)),
                    "clues": [query.get("id", ""), url],
                }
            )
        elif is_document:
            leads.append(
                {
                    "type": "read_document",
                    "args": {"url": url, "engine": engine},
                    "purpose": purpose,
                    "expected": "Text, author fields and links inside the linked document",
                    "score": SCORE["read_document"] * (0.4 + 0.6 * max(relevance, position_bonus)),
                    "clues": [query.get("id", ""), url],
                }
            )
        else:
            leads.append(
                {
                    "type": "read_source",
                    "args": {"url": url, "engine": engine},
                    "purpose": purpose,
                    "expected": "Mentions, aliases, profile links and documents on the original page",
                    "score": SCORE["search_result_page"] * (0.4 + 0.6 * max(relevance, position_bonus)),
                    "clues": [query.get("id", ""), url],
                }
            )
    return leads


def react_to_page(source: dict, page: dict, dossier, target: str) -> list[dict]:
    """New leads extracted from a page the investigation actually read."""
    from snoop.actions import _site_for

    leads: list[dict] = []
    source_id = source.get("id", "")
    from snoop.evidence import tokens

    target_tokens = set(tokens(target))
    exact_people = [
        person
        for person in page.get("persons", [])[:5]
        if target_tokens and target_tokens <= set(tokens(person.get("name", "")))
    ]
    has_subject_context = bool(page.get("mentions")) or bool(exact_people)
    known_accounts = {
        canonical_url(h.get("canonical_url", "")) for h in dossier.all_accounts if hasattr(dossier, "all_accounts")
    }
    known_handles = {
        h.casefold()
        for h in ([target] + list(getattr(dossier, "handles_tried", []) or []))
        if h
    }

    def add(lead_type, args, purpose, expected, score, clues=None):
        leads.append(
            {
                "type": lead_type,
                "args": args,
                "purpose": purpose,
                "expected": expected,
                "score": score,
                "clues": [source_id, *(clues or [])],
            }
        )

    for person in exact_people:
        for url in person.get("same_as", [])[:10]:
            if canonical_url(url) in known_accounts:
                continue
            if _site_for(url):
                add(
                    "check_account",
                    {"url": url},
                    f'Validate profile asserted by this page\'s structured data ({person.get("name", "Person")})',
                    "An account the source itself claims via sameAs",
                    SCORE["check_account_from_source"],
                )
            else:
                add(
                    "crawl_site",
                    {"url": url},
                    f"Read site asserted via sameAs by {person.get('name', 'this source')}",
                    "The personal site the source explicitly claims",
                    SCORE["read_relevant_page"],
                )
        for alias in person.get("alternate_names", [])[:6]:
            if 3 <= len(alias) <= 40 and alias.casefold() not in known_handles:
                add(
                    "web_search",
                    {"query": f'"{alias}"'},
                    f'Search alias "{alias}" asserted by structured data',
                    "Pages and accounts using this alias",
                    SCORE["search_alias"],
                )

    if not has_subject_context:
        # This page may be a coincidental result. Preserve its source record,
        # but do not pivot through its people, documents, or outbound links.
        return leads

    for url in page.get("rel_me", [])[:12]:
        if canonical_url(url) in known_accounts:
            continue
        if _site_for(url):
            add(
                "check_account",
                {"url": url},
                "Validate a rel=me profile link",
                "An account the page explicitly claims",
                SCORE["check_account_from_source"],
            )
        else:
            add(
                "crawl_site",
                {"url": url},
                "Read the personal site this page links with rel=me",
                "The site the source explicitly claims as its own",
                SCORE["read_relevant_page"],
            )

    mentions_subject = bool(page.get("mentions"))
    for item in page.get("handles", [])[:14]:
        handle = item["handle"].casefold()
        if handle in known_handles or len(handle) < 4:
            continue
        add(
            "web_search",
            {"query": f'"{item["handle"]}"'},
            f'Search handle "{item["handle"]}" ({item["origin"]})',
            "Accounts and pages using this handle",
            SCORE["search_alias"] * (1.15 if mentions_subject else 0.6),
            clues=[f"handle-origin:{item['origin']}"],
        )

    for url in page.get("documents", [])[:8]:
        add(
            "read_document",
            {"url": url},
            f"Read linked document {url.rsplit('/', 1)[-1][:60]}",
            "Text, author fields, dates and links inside the document",
            SCORE["read_document"],
        )

    if mentions_subject:
        # Outbound links from a page that mentions the subject: platform
        # profiles become account checks; personal sites become page reads.
        personal_domains = set(page.get("domains", []))
        source_host = (urlsplit(source.get("url", "")).hostname or "").removeprefix("www.")
        queued_domains: set[str] = set()
        for url in page.get("links", [])[:40]:
            if canonical_url(url) in known_accounts:
                continue
            host = (urlsplit(url).hostname or "").removeprefix("www.")
            if not host or host == source_host:
                continue
            if _site_for(url):
                add(
                    "check_account",
                    {"url": url},
                    f"Validate profile linked beside the subject mention: {host}",
                    "An account the mentioning page links directly",
                    SCORE["check_account_from_source"] * 0.9,
                )
            elif host in personal_domains and host not in queued_domains:
                queued_domains.add(host)
                add(
                    "crawl_site",
                    {"url": url},
                    f"Read the personal site linked beside the subject mention: {host}",
                    "Portfolio/project pages connected to the subject",
                    SCORE["read_relevant_page"] * 0.95,
                )
        for domain in page.get("domains", [])[:4]:
            add(
                "archive_lookup",
                {"url": domain},
                f"Check public archive history for {domain}",
                "Historical versions of related pages",
                SCORE["archive_lookup"],
            )
            add(
                "domain_lookup",
                {"domain": domain},
                f"Public records for {domain}",
                "Registration and certificate clues (clues, not ownership proof)",
                SCORE["domain_lookup"],
            )

    for url in page.get("feeds", [])[:2]:
        add(
            "read_source",
            {"url": url},
            "Read the site's public feed",
            "Recent public activity and authorship",
            SCORE["read_feed"],
        )

    return leads


def react_to_account(account: dict, source_id: str = "") -> list[dict]:
    """Follow-up leads for a newly validated account."""
    handle = account.get("matched_handle") or account.get("platform_id") or ""
    platform = account.get("platform", "")
    account.get("links", []) or []
    leads = [
        {
            "type": "expand_links",
            "args": {"ref": account.get("ref", "")},
            "purpose": f"Follow links published by the {platform} account",
            "expected": "Linked profiles validated with the source-to-destination path",
            "score": SCORE["expand_links"],
            "clues": [source_id, account.get("account_id", "")],
        }
    ]
    if handle:
        leads.append(
            {
                "type": "web_search",
                "args": {"query": f'"{handle}"'},
                "purpose": f'Search the web for handle "{handle}" as text',
                "expected": "Pages mentioning this handle beyond the platform itself",
                "score": SCORE["search_handle"],
                "clues": [account.get("account_id", "")],
            }
        )
    return leads


def pivot_leads_allowed(lead: dict, depth_used: int, max_depth: int) -> bool:
    """A discovery from a discovery is a pivot; bound their depth."""
    pivot = int(lead.get("pivot_depth", 0))
    return pivot <= 0 or pivot + depth_used <= max_depth
