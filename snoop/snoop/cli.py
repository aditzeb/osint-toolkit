"""snoop CLI - one command, one investigation.

`snoop "Full Name"` starts the complete investigation workflow (web discovery,
source reading, account checks, evidence-backed follow-up). Every case-aware
command dispatches through the shared registry, so the terminal session and the
web workspace expose the same capabilities against the same saved cases.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import ClassVar

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from snoop.config import config


def _timed_input(prompt: str, timeout: int) -> str | None:
    """input() that returns None when nothing is typed within ``timeout`` seconds.
    Once the analyst starts typing, it waits for the full line."""
    import time

    if timeout <= 0 or not sys.stdin.isatty():
        return input(prompt)
    print(prompt, end="", flush=True)
    if sys.platform == "win32":
        import msvcrt

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if msvcrt.kbhit():
                return input()
            time.sleep(0.05)
        print()
        return None
    import select

    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if not ready:
        print()
        return None
    line = sys.stdin.readline()
    if not line:
        raise EOFError
    return line.rstrip("\n")

console = Console()
_PLAIN_OUTPUT = False


def _enable_plain_output() -> None:
    """Disable ANSI styling and live animation for logs, pipes and transcripts."""
    global console, _PLAIN_OUTPUT
    _PLAIN_OUTPUT = True
    console = Console(no_color=True, force_terminal=False, highlight=False)
    # The report module owns its own Console; keep both output surfaces aligned.
    import snoop.report as report_mod

    report_mod.console = Console(no_color=True, force_terminal=False, highlight=False)


def _run_async(coro) -> int:
    """Run one async entry point; Ctrl+C cancels cleanly and keeps the case."""
    try:
        return asyncio.run(coro)
    except KeyboardInterrupt:
        console.print(
            "\n[dim]interrupted - completed work is saved; "
            "resume with [bold]snoop talk --case last[/bold][/dim]"
        )
        return 130


# ---------------------------------------------------------------- live feed


class LiveFeed:
    """Work log driven by the same backend events the web app renders."""

    _MARK: ClassVar[dict[str, tuple[str, str]]] = {
        "confirmed": ("green", "linked   "),
        "probable": ("yellow", "probable "),
        "weak": ("dim", "weak     "),
        "unrelated": ("dim red", "conflict "),
        "insufficient": ("cyan", "unresolv "),
        "conflicting": ("dim red", "conflict "),
    }

    def __init__(self) -> None:
        self.lines: list[Text] = []
        self.stage = "starting"
        self.probed = 0
        self.total = 0
        self.hits = 0
        self.queries = 0
        self.sources = 0
        self.leads = 0
        self.evidence = 0
        self._live: Live | None = None

    def _render(self) -> Table:
        t = Table.grid(padding=(0, 1))
        t.add_row(Spinner("line", style="dim"), Text(self.stage, style="bold"))
        counters = (
            f"{self.queries} quer{'y' if self.queries == 1 else 'ies'}"
            f" · {self.sources} source{'s' if self.sources != 1 else ''}"
            f" · {self.probed} check{'s' if self.probed != 1 else ''}"
            f" · {self.hits} account{'s' if self.hits != 1 else ''}"
            f" · {self.evidence} evidence"
        )
        t.add_row("", Text(counters, style="dim"))
        if self.total:
            t.add_row(
                "",
                Text(
                    f"{self.probed}/{self.total} platform probes this handle",
                    style="dim",
                ),
            )
        for ln in self.lines[-16:]:
            t.add_row("", ln)
        return t

    def _line(self, tag: str, style: str, main: str, tail: str = "") -> None:
        line = Text()
        line.append(f"  {tag:<9}", style=style)
        line.append(main[:64], style="")
        if tail:
            line.append(f" {tail[:40]}", style="dim")
        self.lines.append(line)

    async def __call__(self, ev) -> None:
        k, p = ev.kind, ev.payload
        if k == "scan_start":
            self.total += p.get("total", 0)
        elif k == "probe":
            self.probed += 1
        elif k == "hit":
            self.hits += 1
            self._line("found", "green", str(p.get("platform", "")), str(p.get("url", "")))
        elif k == "verdict":
            style, word = self._MARK.get(p["verdict"], ("dim", p["verdict"]))
            self._line(word.strip(), style, str(p.get("platform", "")), str(p.get("why", ""))[:40])
        elif k == "stage":
            self.stage = str(p.get("name", self.stage))
        elif k == "query":
            self.queries += 1
            self.stage = f"searching: {str(p.get('query', ''))[:48]}"
            self._line(
                "query", "cyan", str(p.get("query", "")), str(p.get("engine") or "auto")
            )
        elif k == "result":
            self._line(
                "results",
                "cyan",
                f"{p.get('count', 0)} via {p.get('provider', p.get('engine', '?'))}",
                str(p.get("outcome", "")),
            )
        elif k == "source":
            self.sources += 1
            self._line(
                "source",
                "magenta",
                str(p.get("title") or p.get("url", "")),
                str(p.get("outcome", "")),
            )
        elif k == "document":
            self._line(
                "document",
                "magenta",
                str(p.get("url", "")),
                f"{p.get('status', '')} {p.get('method', '')}".strip(),
            )
        elif k == "lead":
            if p.get("status") == "running":
                self.leads += 1
                self.stage = str(p.get("purpose", self.stage))[:60]
        elif k == "evidence":
            self.evidence += 1
            self._line("evidence", "green", str(p.get("claim", "")), str(p.get("source_url", "")))
        elif k == "archive":
            self._line("archive", "dim", str(p.get("target", "")), f"{p.get('captures', 0)} captures")
        elif k == "domain":
            self._line("domain", "dim", str(p.get("domain", "")), str(p.get("rdap", "")))
        elif k == "plan":
            self._line("plan", "cyan", f"{p.get('leads_added', 0)} action(s) planned", str(p.get("mode", "")))
        elif k == "checkpoint":
            self._line("round", "cyan", f"Round {p.get('round')} checkpoint",
                       f"{p.get('coverage', {}).get('sources_read', 0)} sources read")
        elif k == "action_complete":
            self._line("action", "dim", str(p.get("purpose", "")),
                       f"{p.get('status')} · {p.get('new_records', 0)} new records")
        elif k == "warning":
            self._line("note", "yellow", "", str(p.get("detail", ""))[:70])
        elif k == "insight":
            self._line("note", "italic", "", str(p.get("text", ""))[:70])
        elif k == "enrich" and p.get("sig") == "breach":
            self._line("breach", "red", str(p.get("email", "")), f"{p.get('count')} leak(s)")
        elif k in {"paused", "cancelled"}:
            self.stage = k
        elif k == "agent_thought":
            label = "planner" if p.get("mode") == "deterministic" else "reasoning"
            head = Text()
            head.append(f"\n  step {p.get('step')}", style="bold")
            head.append(f"  {label}", style="dim")
            self._print(head)
            self._print(Text(f"    {p.get('thought', '')}", style="italic"))
            self.stage = f"agent step {p.get('step')}"
        elif k == "agent_tool":
            args = p.get("args") or {}
            shown = " ".join(
                f'"{v}"' if isinstance(v, str) and " " in v else str(v)
                for key, v in args.items()
                if not str(key).startswith("_") and v not in ("", None, [])
            )
            line = Text()
            line.append("    tool  ", style="cyan")
            line.append(str(p.get("tool", "")), style="bold cyan")
            line.append(f"  {shown[:110]}", style="")
            self._print(line)
        elif k == "agent_observation":
            style = "dim" if p.get("ok", True) else "yellow"
            self._print(Text(f"    saw   {str(p.get('text', ''))[:320]}", style=style))
        elif k == "agent_done":
            self._print(Text(f"\n  agent {p.get('status')}: {p.get('reason', '')}", style="bold"))
        if self._live:
            self._live.update(self._render())

    def _print(self, renderable) -> None:
        """Persistent output above the live status (the agent's reasoning log)."""
        (self._live.console if self._live else console).print(renderable)


class TalkFeed(LiveFeed):
    """Same live feed plus conversational payloads for the REPL."""

    def __init__(self) -> None:
        super().__init__()
        self.cards: list[dict] | None = None
        self.question: str | None = None
        self.reply_text: str | None = None

    async def __call__(self, ev) -> None:
        if ev.kind == "cards":
            self.cards = ev.payload.get("identities")
        elif ev.kind in {"ask", "question"}:
            question = ev.payload.get("question")
            self.question = question.get("text") if isinstance(question, dict) else question
        elif ev.kind == "reply":
            self.reply_text = ev.payload.get("text")
        else:
            await super().__call__(ev)


# ------------------------------------------------------------------ rendering


def _table(rows: list[dict], limit: int = 25) -> Table | None:
    if not rows:
        return None
    table = Table(show_header=True, header_style="dim", box=None, padding=(0, 2))
    keys: list[str] = []
    for row in rows:
        for key in row:
            if isinstance(row.get(key), (str, int, float, bool)) and key not in keys:
                keys.append(key)
        if len(keys) >= 6:
            break
    for key in keys[:6]:
        table.add_column(key, overflow="ellipsis", max_width=44)
    for row in rows[:limit]:
        table.add_row(*[str(row.get(key, "")) for key in keys[:6]])
    if len(rows) > limit:
        table.add_row(*[f"… {len(rows) - limit} more"] + [""] * (len(keys[:6]) - 1))
    return table


def _render_result(result: dict, *, json_mode: bool, quiet: bool) -> None:
    if json_mode:
        print(json.dumps(result, indent=2, default=str))
        return
    text = result.get("text", "")
    if text and text not in {"evidence", "comparison", "case report", "diagnostics", "case diff"}:
        console.print(f"\n  {text}")
    data = result.get("data")
    if quiet or data is None:
        return
    if isinstance(data, list) and data and isinstance(data[0], dict):
        table = _table(data)
        if table:
            console.print(table)
    elif isinstance(data, dict):
        if text == "diagnostics" and isinstance(data.get("version"), dict):
            version = data["version"]
            package = data.get("package", {})
            configuration = data.get("configuration", {})
            providers = data.get("providers", {})
            console.print(f"\n  [bold]SNOOP {version.get('snoop', '?')}[/bold]")
            console.print(f"  [dim]{'running Python':<22}[/dim] {version.get('python', '?')}")
            console.print(
                f"  [dim]{'Python executable':<22}[/dim] {version.get('python_executable', '?')}"
            )
            console.print(f"  [dim]{'loaded package':<22}[/dim] {package.get('loaded_from', '?')}")
            console.print(
                f"  [dim]{'installed metadata':<22}[/dim] "
                f"{version.get('installed_package', 'none')}"
            )
            note = version.get("install_note")
            if note:
                console.print(f"  [yellow]{note}[/yellow]")
            console.print(f"  [dim]{'case directory':<22}[/dim] {configuration.get('case_dir', '?')}")
            present = configuration.get("env_files_present") or []
            checked = configuration.get("env_files_checked") or []
            env_display = ", ".join(present) if present else "none found; checked " + ", ".join(checked)
            console.print(f"  [dim]{'configuration':<22}[/dim] {env_display}")
            console.print("  [dim]provider readiness[/dim]")
            for name, state in providers.items():
                console.print(f"    [cyan]{name:<20}[/cyan] {state}")
        elif "nodes" in data and "edges" in data:
            edges = data.get("edges", [])
            console.print(f"\n  [dim]{len(data['nodes'])} nodes · {len(edges)} edges[/dim]")
            by_type: dict[str, int] = {}
            for edge in edges:
                by_type[edge.get("type", "?")] = by_type.get(edge.get("type", "?"), 0) + 1
            for edge_type, count in sorted(by_type.items()):
                console.print(f"  [cyan]{edge_type:<14}[/cyan] {count}")
            for edge in edges[:12]:
                console.print(
                    f"  [dim]{str(edge.get('from', ''))[:20]} → {str(edge.get('to', ''))[:20]} "
                    f"({edge.get('type')}) [{str(edge.get('provenance', ''))[:24]}][/dim]"
                )
        elif "identities" in data or "workflow" in data or "version" in data:
            for key, value in list(data.items())[:14]:
                if isinstance(value, (str, int, float, bool)):
                    console.print(f"  [dim]{key:<18}[/dim] {value}")
                elif isinstance(value, list) and value and isinstance(value[0], dict):
                    table = _table(value, limit=8)
                    if table:
                        console.print(f"  [dim]{key}[/dim]")
                        console.print(table)
        elif "evidence" in data and isinstance(data.get("evidence"), list):
            for record in data["evidence"][:12]:
                console.print(
                    f"  [dim]{str(record.get('id', ''))[:14]}[/dim] "
                    f"{str(record.get('excerpt') or record.get('claim', ''))[:70]}"
                )


# -------------------------------------------------------------------- help


def _print_help() -> None:
    from snoop.registry import help_rows

    console.print("\n  [bold]SNOOP[/bold]  [dim]AI investigator · evidence-backed cases[/dim]\n")
    console.print("  [dim]start a full investigation[/dim]")
    console.print('    [bold]snoop "Full Name"[/bold] [--mode quick|standard|deep|accounts] [-c "fact"]...')
    console.print('    [bold]snoop talk[/bold] [--case CASE|last] [--message "instruction"]')
    console.print("    [bold]snoop web[/bold]\n")
    grouped: dict[str, list[dict]] = {}
    for row in help_rows():
        grouped.setdefault(row["family"], []).append(row)
    for family in sorted(grouped):
        console.print(f"  [cyan]{family:<12}[/cyan]")
        for row in grouped[family]:
            needs = "" if not row["needs_case"] else " [dim](case)[/dim]"
            console.print(f"    [bold]{row['usage']}[/bold]{needs}")
            console.print(f"    [dim]{row['help']}[/dim]")
    console.print("\n  [dim]'snoop help' shows this · commands also work in 'snoop talk' and the web palette[/dim]\n")


TALK_HELP = """  plain English or exact commands - both reach the same engine.

  START      torvalds                       a handle
             "Theo Lindqvist"               a name (add -c context facts)
             investigate "Name" --mode deep full workflow with deep preset

  DRIVE      plan                           inspect the ranked plan
             run / step / pause / stop      drive the investigation loop
             search --engine google --query '"Theo Lindqvist"'
             read https://example.com/page  retrieve and investigate a source

  AGENT      agent                          AI investigator reasons and uses tools
             keep digging / figure it out   same, in plain English
             agent "find their open-source work" --steps 8
             trace H03 · connections        how it was found · how records link

  NARROW     he's from Toronto              state a fact; everything re-scores
             anchor https://github.com/you  scope + validate a profile

  DECIDE     pick A · merge A B · split A H03 · keep H03 · discard H03 · undo

  INSPECT    accounts · aliases · leads · sources · queries · evidence H03
             compare H03 H07 · verify H03 · follow H03 · deepen H03
             graph · timeline · diff CASE1 CASE2 · report · export --redact

  ASK        what's his most active site?   answered from evidence on file

  board · cases · resume last · providers · doctor · exit"""


# ------------------------------------------------------------------ talk REPL


def _parse_talk_args(argv: list[str]) -> tuple[str, list[str]]:
    """Parse talk-only flags without discarding misspelled or trailing input."""
    case_ref = ""
    messages: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in {"--case", "-C", "--message", "-m"}:
            if index + 1 >= len(argv):
                raise SystemExit(f"snoop talk: {token} needs a value")
            value = argv[index + 1]
            if token in {"--case", "-C"}:
                case_ref = value
            else:
                messages.append(value)
            index += 2
            continue
        if token.startswith("--case="):
            case_ref = token.split("=", 1)[1]
            if not case_ref:
                raise SystemExit("snoop talk: --case needs a value")
        elif token.startswith("--message="):
            message = token.split("=", 1)[1]
            if not message:
                raise SystemExit("snoop talk: --message needs a value")
            messages.append(message)
        else:
            raise SystemExit(
                f"snoop talk: unexpected argument {token!r}; pass instructions with --message"
            )
        index += 1
    return case_ref, messages


def _talk_repl(case_ref: str = "", messages: list[str] | None = None) -> int:
    """The case terminal. Restores the requested case, runs --message
    instructions, and stays interactive when stdin is a terminal. Owns its
    event loop so one Ctrl+C cancels the running action without killing the
    session; a second Ctrl+C at the idle prompt exits."""
    from snoop import talk
    from snoop.core import Bus
    from snoop.registry import resolve_case
    from snoop.report import render_cards

    # Opening the case terminal resumes the newest case by default. An explicit
    # --case value remains authoritative, including a specific stable case ID.
    dossier = resolve_case(case_ref or "last")
    if case_ref and not dossier:
        console.print(f"  [red]case {case_ref!r} not found; 'snoop cases' lists them[/red]")
        return 1
    interactive = sys.stdin.isatty() and not messages
    if interactive:
        console.print("\n  [bold]SNOOP[/bold]  [dim]case terminal · 'help' · 'exit'[/dim]")
        console.print(f"  [dim]{'─' * 74}[/dim]")
        if dossier:
            console.print(
                f"  [dim]resumed case[/dim] [bold]{dossier.id}[/bold] "
                f"[dim]({dossier.target}, {len(dossier.all_accounts)} accounts, "
                f"{len(dossier.leads)} leads)[/dim]"
            )
        else:
            console.print("  [dim]no active case - give me a name, handle or email[/dim]")
        if not config.ai_provider():
            console.print(
                "  [yellow]no AI key[/yellow] [dim]- fixed commands only, no free-form phrasing.[/dim]"
            )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def one(line: str):
        nonlocal dossier
        bus = Bus()
        feed = TalkFeed()
        bus.on(feed)
        if _PLAIN_OUTPUT or not console.is_terminal:
            dossier, _reply = await talk.handle(dossier, line, bus)
        else:
            with Live(feed._render(), console=console, refresh_per_second=12, transient=True) as live:
                feed._live = live
                try:
                    dossier, _reply = await talk.handle(dossier, line, bus)
                finally:
                    feed._live = None
        if feed.cards and len(feed.cards) > 1:
            render_cards(feed.cards)
        if feed.reply_text:
            console.print(f"  {feed.reply_text}")
        if feed.question:
            console.print(f"  [yellow]{feed.question}[/yellow]")
            if config.question_timeout and sys.stdin.isatty():
                console.print(f"  [dim]no reply within {config.question_timeout}s skips it and keeps investigating[/dim]")
            from snoop import interview as _iv

            asked = _iv.pending(dossier) if dossier else None
            if asked and asked.get("source_url"):
                console.print(f"  [dim]page: {asked['source_url']}[/dim]")
            if asked and asked.get("manual_assist"):
                console.print("  [dim]paste what it shows (several lines are fine), finish with an empty line — "
                              "or type a URL, @username, 'i don't know' or 'skip'[/dim]")

    def run_one(line: str) -> None:
        """Run one instruction; Ctrl+C cancels the action, not the session.
        The workflow's cancellation handler saves completed work first."""
        try:
            loop.run_until_complete(one(line))
        except KeyboardInterrupt:
            console.print("\n  [dim]action cancelled - completed work is saved[/dim]")

    try:
        for message in messages or []:
            run_one(message)
            if dossier:
                console.print(f"  [dim]case {dossier.id}[/dim]")
        if interactive or not messages:
            import functools

            from snoop import interview as _iv

            while True:
                waiting = _iv.pending(dossier) if dossier else None
                timeout = config.question_timeout if waiting else 0
                try:
                    line = loop.run_until_complete(
                        loop.run_in_executor(None, functools.partial(_timed_input, "\nSNOOP ▸ ", timeout))
                    )
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if line is None:
                    console.print(f"  [dim]no reply in {timeout}s — skipping that question and continuing[/dim]")
                    run_one("answer " + json.dumps(_iv.TIMEOUT_REPLY))
                    continue
                line = line.strip()
                if not line:
                    continue
                from snoop import interview as _iv
                from snoop.registry import COMMANDS as _COMMANDS

                waiting = _iv.pending(dossier) if dossier else None
                if (
                    waiting
                    and waiting.get("manual_assist")
                    and (line.split() or [""])[0].casefold() not in _COMMANDS
                    and line.casefold() not in {"skip", "i don't know", "idk", "exit", "quit"}
                ):
                    extra: list[str] = []
                    while True:
                        more = loop.run_until_complete(loop.run_in_executor(None, input, "  … "))
                        if not more.strip():
                            break
                        extra.append(more.rstrip())
                    if extra:
                        line = line + "\n" + "\n".join(extra)
                low = line.lower()
                if low in ("exit", "quit", "q"):
                    break
                if low == "help":
                    console.print(TALK_HELP)
                    continue
                if low in ("board", "cards", "status") and dossier:
                    from snoop.session import build_cards

                    render_cards(build_cards(dossier))
                    continue
                if low in ("board", "cards", "status"):
                    console.print("  [dim]nothing active yet.[/dim]")
                    continue
                if low in ("discarded", "collisions") and dossier:
                    from snoop.report import _discarded

                    _discarded(dossier)
                    continue
                if low in ("case", "report", "full") and dossier:
                    from snoop.report import render

                    render(dossier)
                    continue
                if low.startswith("new "):
                    dossier = None
                    line = line[4:].strip()
                run_one(line)
    finally:
        try:
            loop.close()
        except RuntimeError:
            pass

    if dossier:
        from snoop.config import CASES_DIR
        from snoop.privacy import case_identifiers, mask_text

        path = str(CASES_DIR / (dossier.id + ".json"))
        saved = mask_text(path, case_identifiers(dossier)) if config.presenter else path
        console.print(f"\n  [dim]saved: {saved}[/dim]")
        console.print("  [dim]resume: snoop talk --case last[/dim]")
    return 0


# ------------------------------------------------------------------- runners


async def _run_registry(argv: list[str]) -> int:
    """Execute one registry command with --case/--json/--quiet CLI flags."""
    from snoop import registry
    from snoop.core import Bus

    tokens = list(argv)
    case_ref = ""
    json_mode = "--json" in tokens
    quiet = "-q" in tokens or "--quiet" in tokens
    for flag in ("--json", "-q", "--quiet"):
        while flag in tokens:
            tokens.remove(flag)
    if "--case" in tokens:
        index = tokens.index("--case")
        if index + 1 >= len(tokens):
            raise SystemExit("usage: snoop COMMAND ... --case CASE_ID|last")
        case_ref = tokens[index + 1]
        del tokens[index : index + 2]
    if not tokens:
        raise SystemExit("no command given")
    dossier = registry.resolve_case(case_ref) if case_ref else None
    if not case_ref:
        # Case commands fall back to the most recent case when none is named.
        spec = registry.COMMANDS.get(tokens[0].casefold())
        if spec and spec.needs_case:
            dossier = registry.resolve_case("last")
            if not dossier:
                raise SystemExit(
                    f"'{tokens[0]}' needs a case: add --case CASE_ID or start one with "
                    'snoop "Full Name"'
                )
    bus = Bus()
    feed = LiveFeed()
    result: dict = {}
    if not json_mode and not quiet and not _PLAIN_OUTPUT and console.is_terminal:
        bus.on(feed)
        with Live(feed._render(), console=console, refresh_per_second=12, transient=True) as live:
            feed._live = live
            try:
                result = await registry.execute_tokens(tokens, dossier, bus, runtime="cli")
            finally:
                feed._live = None
                live.stop()
    else:
        if not json_mode and not quiet and tokens[0].casefold() == "agent":
            # Plain/non-interactive output still shows the agent's reasoning log.
            bus.on(feed)
        result = await registry.execute_tokens(tokens, dossier, bus, runtime="cli")
    if config.presenter:
        from snoop.privacy import case_identifiers, mask_obj

        cases = [result.get("case")] if result.get("case") else []
        values = [v for case in cases for v in case_identifiers(case)]
        result = mask_obj(result, values)
    _render_result(result, json_mode=json_mode, quiet=quiet)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="snoop",
        description="SNOOP - evidence-backed public-information investigation.",
    )
    p.add_argument("target", nargs="*", help="username / real name / email / domain")
    p.add_argument("--exact-name", action="store_true", help="exclude other readable names from candidates")
    p.add_argument("--guided", action="store_true", help="pause for useful interview questions between rounds")
    p.add_argument(
        "--as",
        dest="kind",
        choices=["username", "name", "email", "domain"],
        help="force how the target is interpreted",
    )
    p.add_argument(
        "-c",
        "--context",
        action="append",
        default=[],
        metavar="FACT",
        help="something you already know (city, employer, sport). Repeatable.",
    )
    p.add_argument(
        "--mode",
        default="full",
        help="full (default investigation workflow), accounts (enumeration only), "
        "or a preset name: quick, standard, deep",
    )
    p.add_argument("--preset", default=None, help="quick | standard | deep budget preset")
    p.add_argument(
        "--accounts-only",
        action="store_true",
        help="narrower operation: username enumeration without web discovery",
    )
    p.add_argument("-d", "--deep", action="store_true", help="alias for --mode deep")
    p.add_argument("--no-email", action="store_true", help="skip email / breach checks")
    p.add_argument("--json", action="store_true", help="print the dossier as JSON, nothing else")
    p.add_argument("-q", "--quiet", action="store_true", help="no live feed, just the result")
    p.add_argument("--plain", action="store_true", help="plain text with no ANSI styling or animation")
    p.add_argument(
        "--presenter",
        action="store_true",
        help="mask target and SNOOP_REDACT_VALUES across live output",
    )
    return p


async def _run(args) -> int:
    from snoop.pipeline import investigate
    from snoop.report import render

    target = " ".join(args.target).strip()
    if not target:
        _build_parser().print_help()
        return 1
    if args.presenter:
        config.presenter = True
    if config.presenter:
        config.redact_values = list(dict.fromkeys([target, *config.redact_values]))

    mode = (args.mode or "full").strip().casefold()
    preset = args.preset
    if mode in {"quick", "standard", "deep"}:
        preset = preset or mode
        mode = "full"
    if args.accounts_only:
        mode = "accounts"
    if args.deep:
        preset = "deep"

    from snoop.core import Bus

    bus = Bus()
    feed = LiveFeed()

    kw = {
        "kind": args.kind,
        "deep": bool(args.deep),
        "do_emails": not args.no_email,
        "context": args.context,
        "mode": mode,
        "preset": preset,
        "exact_name": args.exact_name,
        "guided": args.guided,
    }

    if args.json or args.quiet or _PLAIN_OUTPUT or not console.is_terminal:
        d = await investigate(target, bus, **kw)
    else:
        bus.on(feed)
        if args.kind == "name" and not args.context:
            console.print(
                '[dim]tip: -c "city" -c "employer" makes matches real evidence[/dim]'
            )
        with Live(feed._render(), console=console, refresh_per_second=12) as live:
            feed._live = live
            d = await investigate(target, bus, **kw)

    if args.json:
        from dataclasses import asdict

        from snoop.privacy import case_identifiers, mask_obj

        print(json.dumps(mask_obj(asdict(d), case_identifiers(d)), indent=2, default=str))
    else:
        render(d)
        if d.workflow.get("search_unavailable"):
            console.print(
                "  [yellow]web search unavailable[/yellow] [dim]- set SERPAPI_KEY or "
                "BRAVE_SEARCH_API_KEY for full discovery; pending searches are preserved[/dim]\n"
            )
        console.print(
            "  [dim]snoop talk --case last[/dim] to continue this case\n"
        )
    return 0


# ---------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    while "--plain" in argv:
        argv.remove("--plain")
        _enable_plain_output()

    if "--presenter" in argv:
        config.presenter = True
        argv.remove("--presenter")

    if not argv:
        if sys.stdin.isatty():
            return _run_async(_talk_repl())
        _print_help()
        return 1

    head = argv[0].casefold()

    if head in {"web", "serve", "ui"}:
        from snoop.web import serve

        try:
            return serve(argv[1:])
        except KeyboardInterrupt:
            return 0

    if head in {"help", "-h", "--help"}:
        _print_help()
        return 0

    if head in {"-V", "--version", "version"}:
        from snoop import __version__

        print(f"snoop {__version__}")
        return 0

    if head in {"talk", "chat", "interactive", "-i", "--talk"}:
        case_ref, messages = _parse_talk_args(argv[1:])
        return _talk_repl(case_ref, messages)

    if head in {"evaluate", "demo"}:
        from snoop.cli_legacy import run_utility

        return _run_async(run_utility(argv))

    from snoop.registry import COMMANDS

    if head in COMMANDS or head in {"use", "list-cases", "import-search"}:
        return _run_async(_run_registry(argv))

    args = _build_parser().parse_args(argv)
    return _run_async(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
