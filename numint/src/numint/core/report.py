"""Rendering: `rich` CLI report, Markdown export, JSON export, optional PDF.

Aesthetic goal: clean, sectioned, professional. No ASCII banners, no neon.
A neutral slate palette with one cyan accent, strong section headers, tidy
tables. This is the CLI counterpart to the web UI cards.
"""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import Attribute, Profile

ACCENT = "#38bdf8"  # cyan-400
MUTED = "#94a3b8"  # slate-400
GOOD = "#4ade80"
BAD = "#f87171"
WARN = "#fbbf24"


def _sources(attrs: list[Attribute]) -> str:
    return ", ".join(f"[{MUTED}]{a.source}[/]" for a in attrs)


def _attr_lines(attrs: list[Attribute]) -> Text:
    if not attrs:
        return Text("unknown", style=MUTED)
    t = Text()
    for i, a in enumerate(attrs):
        if i:
            t.append("\n")
        t.append(str(a.value))
        t.append(f"  ({a.source})", style=MUTED)
    return t


def _risk_color(score) -> str:
    try:
        s = float(score)
    except (TypeError, ValueError):
        return MUTED
    if s >= 75:
        return BAD
    if s >= 40:
        return WARN
    return GOOD


def _header_panel(profile: Profile) -> Panel:
    n = profile.input
    flag = _flag(n.country_iso)
    valid = (
        Text("VALID", style=f"bold {GOOD}")
        if n.is_valid
        else Text("INVALID", style=f"bold {BAD}")
    )
    grid = Table.grid(padding=(0, 2))
    grid.add_column(justify="right", style=MUTED)
    grid.add_column()
    grid.add_row("Number", Text(n.e164, style=f"bold {ACCENT}"))
    grid.add_row("National", n.national)
    grid.add_row("Country", f"{flag} {n.country_name or 'unknown'}")
    grid.add_row("Type", n.number_type.value.replace("_", " "))
    grid.add_row("Validity", valid)
    carrier = profile.primary_carrier() or n.carrier or "unknown"
    grid.add_row("Carrier", carrier)
    if profile.risk.fraud_score is not None:
        score = profile.risk.fraud_score.value
        grid.add_row(
            "Risk",
            Text(f"{score}/100", style=f"bold {_risk_color(score)}"),
        )
    return Panel(grid, title="[bold]Intelligence Profile[/]", border_style=ACCENT)


def _flag(iso: str | None) -> str:
    if not iso or len(iso) != 2:
        return "🏳"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso.upper())


def _validity_card(profile: Profile) -> Panel:
    n = profile.input
    t = Table.grid(padding=(0, 2))
    t.add_column(style=MUTED, justify="right")
    t.add_column()
    t.add_row("E.164", n.e164)
    t.add_row("International", n.international)
    t.add_row("National", n.national)
    t.add_row("RFC3966", n.rfc3966)
    t.add_row("Possible", "yes" if n.is_possible else "no")
    t.add_row("Valid", "yes" if n.is_valid else "no")
    return Panel(t, title="Validity & Format", border_style=MUTED)


def _carrier_card(profile: Profile) -> Panel:
    t = Table.grid(padding=(0, 2))
    t.add_column(style=MUTED, justify="right")
    t.add_column()
    t.add_row("Carrier", _attr_lines(profile.carriers))
    t.add_row("Line type", _attr_lines(profile.line_types))
    return Panel(t, title="Carrier & Line Type", border_style=MUTED)


def _location_card(profile: Profile) -> Panel:
    n = profile.input
    t = Table.grid(padding=(0, 2))
    t.add_column(style=MUTED, justify="right")
    t.add_column()
    t.add_row("Location", _attr_lines(profile.locations))
    t.add_row("Region", n.region or Text("unknown", style=MUTED))
    t.add_row(
        "Timezones",
        ", ".join(n.timezones) if n.timezones else Text("unknown", style=MUTED),
    )
    return Panel(t, title="Location & Timezone", border_style=MUTED)


def _risk_card(profile: Profile) -> Panel | None:
    r = profile.risk
    if all(
        v is None
        for v in (r.fraud_score, r.spam, r.disposable, r.voip, r.active, r.recent_abuse)
    ):
        return None
    t = Table.grid(padding=(0, 2))
    t.add_column(style=MUTED, justify="right")
    t.add_column()

    def flag_row(label: str, attr: Attribute | None, bad_is_true=True):
        if attr is None:
            return
        val = attr.value
        if isinstance(val, bool):
            color = (BAD if val else GOOD) if bad_is_true else (GOOD if val else BAD)
            text = Text("yes" if val else "no", style=color)
        else:
            text = Text(str(val))
        text.append(f"  ({attr.source})", style=MUTED)
        t.add_row(label, text)

    if r.fraud_score is not None:
        s = r.fraud_score.value
        txt = Text(f"{s}/100", style=f"bold {_risk_color(s)}")
        txt.append(f"  ({r.fraud_score.source})", style=MUTED)
        t.add_row("Fraud score", txt)
    flag_row("Spam", r.spam)
    flag_row("Disposable", r.disposable)
    flag_row("VoIP", r.voip)
    flag_row("Recent abuse", r.recent_abuse)
    flag_row("Active", r.active, bad_is_true=False)
    return Panel(t, title="Risk & Reputation", border_style=WARN)


def _ai_card(profile: Profile) -> Panel | None:
    ai = profile.ai_analysis
    if ai is None:
        return None
    body = Table.grid(padding=(0, 1))
    body.add_column()
    if ai.error:
        body.add_row(Text(ai.error, style=BAD))
    elif ai.answer is not None:
        body.add_row(Text(ai.answer))
    else:
        for label, val in (
            ("Summary", ai.summary),
            ("Conflicts", ai.conflicts),
            ("Risk read", ai.risk_read),
            ("Next steps", ai.next_steps),
        ):
            if val and val.strip().lower() not in ("none", ""):
                body.add_row(Text(label, style=f"bold {ACCENT}"))
                body.add_row(Text(val))
                body.add_row("")
    title = f"AI Analysis  [{MUTED}]· {ai.provider}/{ai.model}[/]"
    return Panel(body, title=title, border_style=ACCENT)


def _presence_card(profile: Profile) -> Panel | None:
    if not profile.presence:
        return None
    t = Table(show_edge=False, expand=True)
    t.add_column("Site")
    t.add_column("Registered")
    t.add_column("Leaked / hint", style=MUTED)
    t.add_column("Via", style=MUTED)
    for r in profile.presence:
        if r.registered == "yes":
            reg = Text("● yes", style=f"bold {GOOD}")
        elif r.registered == "no":
            reg = Text("○ no", style=MUTED)
        elif r.registered in ("error", "rate_limited"):
            reg = Text(f"● {r.registered}", style=BAD)
        else:
            reg = Text("· unknown", style=MUTED)
        leaked = " ".join(
            x for x in (r.masked_email, r.masked_phone, r.hint) if x
        ) or (r.error or "")
        t.add_row(r.site, reg, leaked, r.method)
    return Panel(
        t,
        title="Accounts On This Number",
        border_style=WARN,
    )


def _footprint_card(profile: Profile) -> Panel | None:
    if not profile.footprint:
        return None
    body = Table.grid(padding=(0, 1))
    body.add_column()
    for group in profile.footprint:
        body.add_row(Text(group.category, style=f"bold {ACCENT}"))
        for link in group.links:
            line = Text("  • ")
            line.append(link.label, style=MUTED)
            line.append("  ")
            line.append(link.url, style="underline")
            body.add_row(line)
        body.add_row("")
    return Panel(body, title="OSINT Footprint (open manually)", border_style=MUTED)


def _dorking_card(profile: Profile) -> Panel | None:
    if not profile.dorking:
        return None
    body = Table.grid(padding=(0, 1))
    body.add_column()
    for group in profile.dorking:
        for link in group.links:
            line = Text("  • ")
            line.append(link.label, style=MUTED)
            line.append("  ")
            line.append(link.url, style="underline")
            body.add_row(line)
    return Panel(body, title="Dorking (search-engine links)", border_style=MUTED)


def _providers_card(profile: Profile) -> Panel:
    t = Table(show_edge=False, expand=True)
    t.add_column("Provider")
    t.add_column("Status")
    t.add_column("Detail", style=MUTED)
    for p in profile.providers:
        if p.status.value == "ran":
            status = Text("● ran", style=GOOD)
        elif p.status.value == "skipped":
            status = Text("○ no key", style=MUTED)
        else:
            status = Text("● error", style=BAD)
        detail = p.reason or (f"{p.elapsed_ms} ms" if p.elapsed_ms else "")
        t.add_row(p.name, status, str(detail))
    return Panel(t, title="Provider Status", border_style=MUTED)


def render_console(profile: Profile, console: Console | None = None) -> None:
    console = console or Console()
    cards = [
        _header_panel(profile),
        _validity_card(profile),
        _carrier_card(profile),
        _location_card(profile),
    ]
    for maybe in (
        _risk_card(profile),
        _presence_card(profile),
        _ai_card(profile),
        _dorking_card(profile),
        _footprint_card(profile),
    ):
        if maybe is not None:
            cards.append(maybe)
    cards.append(_providers_card(profile))
    console.print(Group(*cards))


def render_batch_heatmap(
    profiles: list[Profile], console: Console | None = None
) -> None:
    """Render a colored risk grid across many numbers (batch mode).

    One row per number; risk-bearing cells are background-shaded so a whole
    list can be triaged at a glance.
    """
    console = console or Console()
    t = Table(title="Batch Risk Heatmap", title_style=f"bold {ACCENT}", expand=True)
    t.add_column("Number", no_wrap=True)
    t.add_column("Valid", justify="center")
    t.add_column("Type")
    t.add_column("Carrier")
    t.add_column("Country", justify="center")
    t.add_column("Risk", justify="center")
    t.add_column("Spam", justify="center")
    t.add_column("VoIP", justify="center")
    t.add_column("Presence", justify="center")

    def risk_cell(profile: Profile) -> Text:
        fs = profile.risk.fraud_score
        if fs is None:
            return Text("-", style=MUTED)
        try:
            s = float(fs.value)
        except (TypeError, ValueError):
            return Text(str(fs.value), style=MUTED)
        bg = "#14532d" if s < 40 else ("#78350f" if s < 75 else "#7f1d1d")
        return Text(f" {int(s)} ", style=f"bold white on {bg}")

    def bool_cell(attr, bad_is_true=True) -> Text:
        if attr is None:
            return Text("-", style=MUTED)
        v = attr.value
        if isinstance(v, bool):
            hot = v if bad_is_true else not v
            return Text("yes" if v else "no", style=BAD if hot else GOOD)
        return Text(str(v), style=MUTED)

    for p in profiles:
        n = p.input
        valid = Text("✓", style=GOOD) if n.is_valid else Text("✗", style=BAD)
        carrier = p.primary_carrier() or n.carrier or "-"
        registered = [r.site for r in p.presence if r.registered == "yes"]
        pres = (
            Text(str(len(registered)), style=f"bold {WARN}")
            if registered
            else Text("-", style=MUTED)
        )
        t.add_row(
            n.e164,
            valid,
            (n.number_type.value or "").replace("_", " "),
            carrier,
            n.country_iso or "-",
            risk_cell(p),
            bool_cell(p.risk.spam),
            bool_cell(p.risk.voip),
            pres,
        )
    console.print(t)


# --- exports ---------------------------------------------------------------
def to_json(profile: Profile, indent: int = 2) -> str:
    return json.dumps(profile.model_dump(mode="json"), indent=indent, default=str)


def to_markdown(profile: Profile) -> str:
    n = profile.input
    lines: list[str] = []
    lines.append(f"# Numint report: {n.e164}\n")
    lines.append("## Summary\n")
    lines.append(f"- **Number:** {n.e164} ({n.national})")
    iso = n.country_iso or "?"
    lines.append(f"- **Country:** {n.country_name or 'unknown'} ({iso})")
    lines.append(f"- **Type:** {n.number_type.value.replace('_', ' ')}")
    lines.append(f"- **Valid:** {'yes' if n.is_valid else 'no'}")
    carrier = profile.primary_carrier() or n.carrier or "unknown"
    lines.append(f"- **Carrier:** {carrier}")
    if profile.risk.fraud_score is not None:
        lines.append(f"- **Fraud score:** {profile.risk.fraud_score.value}/100")
    lines.append("")

    def attr_md(attrs: list[Attribute]) -> str:
        if not attrs:
            return "unknown"
        return "; ".join(f"{a.value} ({a.source})" for a in attrs)

    lines.append("## Carrier & Line Type\n")
    lines.append(f"- **Carrier:** {attr_md(profile.carriers)}")
    lines.append(f"- **Line type:** {attr_md(profile.line_types)}\n")

    lines.append("## Location & Timezone\n")
    lines.append(f"- **Location:** {attr_md(profile.locations)}")
    lines.append(f"- **Timezones:** {', '.join(n.timezones) or 'unknown'}\n")

    if profile.ai_analysis and not profile.ai_analysis.error:
        ai = profile.ai_analysis
        lines.append(f"## AI Analysis ({ai.provider}/{ai.model})\n")
        if ai.answer:
            lines.append(ai.answer + "\n")
        else:
            for label, val in (
                ("Summary", ai.summary),
                ("Conflicts", ai.conflicts),
                ("Risk read", ai.risk_read),
                ("Next steps", ai.next_steps),
            ):
                if val:
                    lines.append(f"**{label}:** {val}\n")

    if profile.presence:
        lines.append("## Accounts on this number\n")
        lines.append("| Site | Registered | Leaked / hint | Via |")
        lines.append("| --- | --- | --- | --- |")
        for r in profile.presence:
            leaked = " ".join(
                x for x in (r.masked_email, r.masked_phone, r.hint) if x
            ) or (r.error or "")
            lines.append(f"| {r.site} | {r.registered} | {leaked} | {r.method} |")
        lines.append("")

    if profile.footprint:
        lines.append("## OSINT Footprint (open manually)\n")
        for group in profile.footprint:
            lines.append(f"### {group.category}\n")
            for link in group.links:
                lines.append(f"- [{link.label}]({link.url})")
            lines.append("")

    lines.append("## Provider Status\n")
    lines.append("| Provider | Status | Detail |")
    lines.append("| --- | --- | --- |")
    for p in profile.providers:
        detail = p.reason or (f"{p.elapsed_ms} ms" if p.elapsed_ms else "")
        lines.append(f"| {p.name} | {p.status.value} | {detail} |")

    return "\n".join(lines) + "\n"


def save_report(profile: Profile, path: str | Path) -> None:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        path.write_text(to_json(profile), encoding="utf-8")
    elif suffix in (".md", ".markdown"):
        path.write_text(to_markdown(profile), encoding="utf-8")
    elif suffix == ".pdf":
        _save_pdf(profile, path)
    else:
        raise ValueError(
            f"Unsupported output format '{suffix}'. Use .json, .md or .pdf."
        )


def _save_pdf(profile: Profile, path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "PDF export needs the 'reportlab' package. "
            "Install with: pip install 'numint[pdf]'"
        ) from exc

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    flow = []
    md = to_markdown(profile)
    for block in md.split("\n"):
        if not block.strip():
            flow.append(Spacer(1, 6))
            continue
        style = styles["Normal"]
        text = block
        if block.startswith("# "):
            style, text = styles["Title"], block[2:]
        elif block.startswith("## "):
            style, text = styles["Heading2"], block[3:]
        elif block.startswith("### "):
            style, text = styles["Heading3"], block[4:]
        # escape angle brackets for reportlab's minimal markup
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        flow.append(Paragraph(text, style))
    doc.build(flow)
