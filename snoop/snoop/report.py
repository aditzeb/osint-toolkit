"""Terminal rendering. Reads like a case file: findings, the evidence behind
each one, and an explicit account of what was thrown away and why."""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape

console = Console(highlight=False)

W = 74
RULE = "─" * W

_VERDICT_STYLE = {
    "confirmed": "bold green",
    "probable": "yellow",
    "weak": "dim",
    "unrelated": "dim red",
}


def _row(label: str, value: str, style: str = "", indent: int = 2) -> None:
    if not value:
        return
    pad = " " * indent
    console.print(f"{pad}[dim]{label:<11}[/dim]", end="")
    console.print(value, style=style or None)


def _head(title: str, right: str = "") -> None:
    gap = max(1, W - len(title) - len(right))
    console.print(f"\n  [bold]{title}[/bold]{' ' * gap}[dim]{right}[/dim]")
    console.print(f"  [dim]{RULE}[/dim]")


def _verdict_tag(verdict: str, score: int) -> str:
    style = _VERDICT_STYLE.get(verdict, "dim")
    return f"[{style}]{verdict:<9}[/{style}] [dim]{score:>3}[/dim]"


def _short_url(url: str) -> str:
    return url.replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")


# --------------------------------------------------------------------- header


def _header(d) -> None:
    st = d.stats or {}
    when = (d.created or "").replace("T", " ")[:16]
    console.print()
    console.print(
        f"  [bold]CASE[/bold]  {d.id}{' ' * max(1, W - 8 - len(d.id) - len(when))}[dim]{when}[/dim]"
    )
    _row("SUBJECT", f"[bold]{escape(str(d.target))}[/bold]")
    _row(
        "TYPE",
        {
            "name": "personal name",
            "username": "handle",
            "email": "email address",
            "domain": "domain",
        }.get(d.kind, d.kind),
    )
    if d.context:
        _row("CONTEXT", escape(" · ".join(d.context)))
    console.print(f"  [dim]{RULE}[/dim]")

    scope = (
        f"{len(d.handles_tried)} handle variant"
        f"{'s' if len(d.handles_tried) != 1 else ''}; "
        f"{st.get('attempted', st.get('checks_run', 0))} request attempts"
    )
    _row("SCOPE", f"[dim]{scope}[/dim]")
    _row("RETURNED", f"[dim]{st.get('accounts_returned', 0)} accounts[/dim]")

    linked = st.get("linked", 0)
    breakdown = (
        f"confirmed {st.get('confirmed', 0)}   "
        f"probable {st.get('probable', 0)}   weak {st.get('weak', 0)}"
    )
    _row("LINKED", f"[bold]{linked}[/bold]   [dim]{breakdown}[/dim]")
    if st.get("discarded"):
        _row(
            "DISCARDED",
            f"[dim]{st['discarded']}  conflicting candidate(s) with contrary evidence[/dim]",
        )
    if st.get("insufficient"):
        _row(
            "UNRESOLVED",
            f"[dim]{st['insufficient']}  insufficient information, kept for follow-up[/dim]",
        )
    console.print(f"  [dim]{RULE}[/dim]")


# ------------------------------------------------------------------- findings


def _evidence_block(h: dict, indent: int = 4) -> None:
    pad = " " * indent
    for e in h.get("evidence") or []:
        pts = e["points"]
        if pts == 0:
            continue
        style = "green" if pts >= 25 else ("red" if pts < 0 else "dim")
        detail = escape(str(e["detail"]))
        if len(detail) > 42:
            detail = detail[:41] + "…"
        console.print(f"{pad}[dim]{e['label']:<13}[/dim]{detail:<43}[{style}]{pts:+d}[/{style}]")


def _account_line(h: dict, indent: int = 2) -> None:
    pad = " " * indent
    url = escape(_short_url(h["url"]))
    if len(url) > 33:
        url = url[:32] + "…"
    console.print(
        f"{pad}[bold]{(h.get('ref') or h['platform'])[:21]:<22}[/bold]{url:<34}"
        f"{_verdict_tag(h.get('verdict', 'weak'), h.get('score', 0))}"
    )


def _identities(d) -> None:
    a = d.analysis or {}
    idts = a.get("identities", [])
    by_platform = {}
    for h in d.hits:
        by_platform[h.get("ref") or h["platform"]] = h
        if h.get("account_id"):
            by_platform[h["account_id"]] = h

    if not idts:
        _head("NO SUBJECT ESTABLISHED")
        console.print("  " + escape(str(a.get("summary", "Nothing could be tied to the subject."))))
        return

    for idt in idts:
        conf = int(idt.get("evidence_score", 0) or 0)
        is_subj = idt.get("selected")
        status = str(idt.get("status", "unresolved"))
        # Unresolved hypotheses are candidates, never asserted as other people.
        kind = "SUBJECT" if is_subj else "CANDIDATE"
        title = f"{kind} {idt.get('label', '?')}  ·  {status}"
        _head(title, f"evidence score {conf}/100")

        _row(
            "name",
            f"[bold]{escape(str(idt['name']))}[/bold]" if idt.get("name") else "[dim]unnamed[/dim]",
        )
        _row("location", escape(str(idt.get("location", ""))))
        _row("occupation", escape(str(idt.get("occupation", ""))))
        _row("born", escape(str(idt.get("age_or_dob", ""))))
        if idt.get("emails"):
            _row("email", escape(", ".join(idt["emails"][:4])))
        for link in (idt.get("external_links") or [])[:4]:
            _row("link", f"[dim]{escape(_short_url(link))}[/dim]")
        if idt.get("reasoning"):
            basis = idt["reasoning"]
            _row("basis", f"[dim]{escape(str(basis[:200]))}{'…' if len(basis) > 200 else ''}[/dim]")

        console.print()
        for plat in idt.get("is_same_person_accounts", []):
            h = by_platform.get(plat)
            if not h:
                continue
            _account_line(h)
            _evidence_block(h)
            bio = h.get("bio", "")
            # skip the site's own boilerplate ("GitHub Gist: star and fork ...")
            if bio and not bio.lower().startswith(h["platform"].lower()):
                console.print(
                    f"    [dim italic]{escape(str(bio[:140]))}"
                    f"{'…' if len(bio) > 140 else ''}[/dim italic]"
                )
            console.print()


def _unassigned(d) -> None:
    claimed = {
        p
        for i in (d.analysis or {}).get("identities", [])
        for p in i.get("is_same_person_accounts", [])
    }
    rest = [
        h
        for h in d.hits
        if h.get("account_id") not in claimed and (h.get("ref") or h["platform"]) not in claimed
    ]
    if not rest:
        return
    _head("LINKED, NOT YET ATTRIBUTED", f"{len(rest)} accounts")
    for h in sorted(rest, key=lambda x: -x.get("score", 0)):
        _account_line(h)


def _discarded(d) -> None:
    if not d.discarded:
        return
    _head("DISCARDED", f"{len(d.discarded)} conflicting candidate(s)")
    for h in sorted(d.discarded, key=lambda x: -x.get("score", 0))[:20]:
        url = escape(_short_url(h["url"]))
        console.print(
            f"  [dim]{(h.get('ref') or h['platform'])[:21]:<22}{url[:33]:<34}{h.get('score', 0):>3}[/dim]"
        )
        neg = [e for e in (h.get("evidence") or []) if e["points"] <= 0]
        if neg:
            console.print(f"    [dim red]{escape(str(neg[0]['detail'][:70]))}[/dim red]")
    if len(d.discarded) > 20:
        console.print(f"  [dim]… and {len(d.discarded) - 20} more[/dim]")


def _insufficient(d) -> None:
    rows = [h for h in d.hits if h.get("verdict") == "insufficient"]
    if not rows:
        return
    _head("UNRESOLVED — INSUFFICIENT INFORMATION", f"{len(rows)} candidate(s) kept")
    for h in sorted(rows, key=lambda x: -x.get("score", 0))[:15]:
        url = escape(_short_url(h["url"]))
        console.print(
            f"  [dim]{(h.get('ref') or h['platform'])[:21]:<22}{url[:33]:<34}{h.get('score', 0):>3}[/dim]"
        )
    console.print(
        "  [dim]nothing contradicts these accounts; there was simply not enough public[/dim]"
    )
    console.print(
        "  [dim]information to score them. they remain available for follow-up.[/dim]"
    )


def _closing(d) -> None:
    a = d.analysis or {}
    if a.get("contradictions"):
        _head("CONFLICTS")
        for c in a["contradictions"]:
            console.print(f"  [red]·[/red] {escape(str(c))}")
    if a.get("next_steps"):
        _head("OPEN LEADS")
        for s in a["next_steps"]:
            console.print(f"  [dim]·[/dim] {escape(str(s))}")

    br = (d.enrichment or {}).get("breaches", {})
    if br:
        _head("BREACH EXPOSURE")
        for email, lst in br.items():
            names = ", ".join(f"{b['name']} {b['date'][:4]}" for b in lst[:10])
            console.print(f"  [bold]{email}[/bold]\n    [red]{names}[/red]")

    st = d.stats or {}
    console.print(f"\n  [dim]{st.get('elapsed_s', '?')}s   case {d.id}[/dim]\n")


def render(d) -> None:
    from dataclasses import asdict
    from types import SimpleNamespace

    from snoop.config import config
    from snoop.privacy import case_identifiers, mask_obj

    if config.presenter:
        d = SimpleNamespace(**mask_obj(asdict(d), case_identifiers(d)))
    _header(d)
    a = d.analysis or {}
    if a.get("identities") and a.get("summary"):
        _head("ASSESSMENT")
        console.print("  " + escape(str(a["summary"])))
    _identities(d)
    _unassigned(d)
    _insufficient(d)
    _discarded(d)
    _closing(d)


def render_cards(cards: list[dict]) -> None:
    from snoop.config import config
    from snoop.privacy import mask_obj

    if config.presenter:
        cards = mask_obj(cards)
    """Compact candidate list used in `snoop talk` after each turn."""
    if not cards:
        console.print("  [dim]no identities established[/dim]")
        return
    console.print()
    for c in cards:
        conf = int(c.get("evidence_score", 0) or 0)
        mark = "›" if c.get("selected") else " "
        name = c.get("name") or "unnamed"
        accts = ", ".join(c.get("is_same_person_accounts", [])[:5])
        if len(c.get("is_same_person_accounts", [])) > 5:
            accts += f" +{len(c['is_same_person_accounts']) - 5}"
        console.print(
            f"  [bold]{mark} {escape(str(c.get('label', '?')))}[/bold]  "
            f"[bold]{escape(str(name)):<26}[/bold][dim]score {conf:>3}[/dim]"
        )
        console.print(f"      [dim]{escape(accts)}[/dim]")
        if c.get("location"):
            console.print(f"      [dim]{escape(str(c['location']))}[/dim]")
        for g in (c.get("aliases_detail") or [])[:2]:
            extra = f"  also: {', '.join(g['also_seen_as'][:2])}" if g.get("also_seen_as") else ""
            console.print(
                f'      [dim italic]"{escape(str(g["name"]))}"{escape(extra)}[/dim italic]'
            )
        for o in (c.get("overlaps") or [])[:2]:
            console.print(
                f"      [yellow]shares {escape(', '.join(o['reasons']))} with {escape(str(o['with']))}[/yellow]"
            )
        for m in (c.get("membership_hypotheses") or [])[:3]:
            console.print(
                f"      [dim italic]{escape(str(m.get('account_id', '')))[:28]} — {escape(str(m.get('note', ''))[:70])}[/dim italic]"
            )
    console.print()
