"""Numint CLI - the primary interface, built with Typer.

    numint <number>                 one-shot lookup (alias: numint scan <number>)
    numint web [--port 8080]        launch the web UI + API
    numint providers                list data + LLM providers and their status
    numint config set/list/path     manage persisted API keys
    numint scan --input file.txt    batch mode over a file of numbers
"""

from __future__ import annotations

import asyncio
import sys
import webbrowser
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text
from typer.core import TyperGroup

from . import __version__
from .core.config import config_path, get_settings, reset_settings_cache, write_key
from .core.engine import Engine
from .core.logging import setup_logging
from .core.parser import ParseError
from .core.report import (
    render_batch_heatmap,
    render_console,
    save_report,
    to_json,
)
from .integrations import send_discord_sync


def _ensure_utf8_output() -> None:
    """Windows consoles default to cp1252 and choke on emoji/box glyphs.

    Reconfigure stdout/stderr to UTF-8 (replacing anything truly unencodable)
    so the rich report renders everywhere. `reconfigure` mutates the existing
    stream object, so the module-level Consoles below pick it up.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


_ensure_utf8_output()


class DefaultCommandGroup(TyperGroup):
    """Route a bare number to the `scan` command.

    So both `numint +14155550123 --discord` and `numint --discord +14155550123`
    work: unless the first token is a real subcommand or one of the few options
    that belong to the top-level app, we prepend `scan`. That lets scan flags
    (`--discord`, `--presence`, `--json`, ...) appear before the number too.
    """

    #: Options handled by the top-level app callback, not by `scan`.
    _GROUP_OPTIONS = {"--web", "--version", "--help", "-h"}

    def parse_args(self, ctx, args):
        # Allow a bare `--web` (no port) to mean the default port.
        if "--web" in args:
            i = args.index("--web")
            nxt = args[i + 1] if i + 1 < len(args) else None
            if nxt is None or not nxt.isdigit():
                args = [*args[: i + 1], "8080", *args[i + 1 :]]
        if args and args[0] not in self.commands and args[0] not in self._GROUP_OPTIONS:
            args = ["scan", *args]
        return super().parse_args(ctx, args)


app = typer.Typer(
    cls=DefaultCommandGroup,
    add_completion=True,
    no_args_is_help=False,
    help=(
        "Numint: phone number OSINT and intelligence.\n\n"
        "Run [bold]numint <number>[/] to scan a number directly "
        "(e.g. numint +14155550123), or use one of the commands below. "
        "Add --lookup or --dorking to open sites, --presence to find accounts, "
        "or --web to launch the browser UI."
    ),
    rich_markup_mode="rich",
)
config_app = typer.Typer(help="Manage persisted API keys.")
app.add_typer(config_app, name="config")

console = Console()
err_console = Console(stderr=True)

ACCENT = "#38bdf8"
MUTED = "#94a3b8"


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"numint {__version__}")
        raise typer.Exit()


def _run_and_render(
    number: str,
    *,
    with_offline: bool,
    with_api: bool,
    with_ai: bool,
    with_footprint: bool,
    with_dorking: bool,
    presence: bool,
    as_json: bool,
    no_cache: bool,
    country: str | None,
    output: str | None,
    ask: str | None,
    discord: bool = False,
    discord_url: str | None = None,
) -> None:
    engine = Engine()
    try:
        profile = asyncio.run(
            engine.scan(
                number,
                default_region=country.upper() if country else None,
                use_cache=not no_cache,
                with_offline=with_offline,
                with_api=with_api,
                with_ai=with_ai,
                with_footprint=with_footprint,
                with_dorking=with_dorking,
                with_presence=presence,
                ask=ask,
            )
        )
    except ParseError as exc:
        err_console.print(f"[bold red]Error:[/] {exc}")
        raise typer.Exit(code=2) from None

    if output:
        try:
            save_report(profile, output)
        except (ValueError, RuntimeError) as exc:
            err_console.print(f"[bold red]Export failed:[/] {exc}")
            raise typer.Exit(code=1) from None
        console.print(f"[{MUTED}]Saved report to[/] {output}")

    if as_json:
        console.print_json(to_json(profile))
    elif not output:
        render_console(profile, console)

    _maybe_discord(profile, discord, discord_url)

    if not profile.input.is_possible:
        raise typer.Exit(code=1)


def _open_action(
    number: str,
    *,
    country: str | None,
    lookup: bool,
    lookup_all: bool,
    dorking: bool,
    dorking_all: bool,
) -> None:
    """Open lookup sites and/or dork searches in the browser. Does not scan.

    Lookup sites and dork searches are separate: only what was asked for is
    opened. Opening may fail on a headless box (no display), so we always print
    the links too.
    """
    from .core.dorking import build_dorking
    from .core.lookup import build_sites
    from .core.parser import parse_number

    try:
        parsed = parse_number(number, country.upper() if country else None)
    except ParseError as exc:
        err_console.print(f"[bold red]Error:[/] {exc}")
        raise typer.Exit(code=2) from None

    groups = []
    if lookup:
        groups += build_sites(parsed, top_only=True)
    if lookup_all:
        groups += build_sites(parsed, top_only=False)
    if dorking:
        groups += build_dorking(parsed, top_only=True)
    if dorking_all:
        groups += build_dorking(parsed, top_only=False)

    links = [link for group in groups for link in group.links]
    if not links:
        console.print(f"[{MUTED}]Nothing to open for this number.[/]")
        return

    console.print(
        f"[bold {ACCENT}]Opening[/] {len(links)} link(s) for {parsed.e164}:"
    )
    for group in groups:
        console.print(f"[{MUTED}]{group.category}[/]")
        for link in group.links:
            console.print(f"  {link.label}: {link.url}")

    opened = 0
    for link in links:
        try:
            if webbrowser.open(link.url, new=2):
                opened += 1
        except Exception:  # noqa: BLE001 - headless / no browser is fine
            pass
    if opened:
        console.print(f"[{MUTED}]Opened {opened} browser tab(s).[/]")
    else:
        console.print(
            f"[{MUTED}]No browser available - open the links above "
            "manually.[/]"
            )


def _maybe_discord(profile, discord: bool, discord_url: str | None) -> None:
    """Send to Discord when requested; resolve URL from flag or config."""
    url = discord_url or (get_settings().discord_webhook_url if discord else None)
    if not (discord or discord_url):
        return
    if not url:
        err_console.print(
            "[yellow]Discord:[/] no webhook URL. Pass --discord-url or set "
            "DISCORD_WEBHOOK_URL (numint config set DISCORD_WEBHOOK_URL <url>)."
        )
        return
    try:
        send_discord_sync(profile, url)
        console.print(f"[{MUTED}]Sent to Discord.[/]")
    except Exception as exc:  # noqa: BLE001 - report, never crash the scan
        err_console.print(f"[yellow]Discord send failed:[/] {exc.__class__.__name__}")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    web: int | None = typer.Option(
        None, "--web", help="Shorthand to launch the web UI on this port."
    ),
    _version: bool = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Scan a phone number: `numint <number> [flags]`, or use a subcommand."""
    setup_logging()

    if web is not None:
        _launch_web(host="127.0.0.1", port=web)
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


@app.command()
def scan(
    number: str | None = typer.Argument(None, help="Phone number to scan."),
    input: Path | None = typer.Option(
        None, "--input", help="Batch: file with one number per line."
    ),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
    no_cache: bool = typer.Option(
        False, "--no-cache", help="Skip the cache and fetch fresh results."
    ),
    no_ai: bool = typer.Option(
        False, "--no-ai", help="Skip the AI summary even if a key is set."
    ),
    presence: bool = typer.Option(
        False, "--presence",
        help="Check which sites the number is registered on "
        "(needs --yes-authorized).",
    ),
    yes_authorized: bool = typer.Option(
        False, "--yes-authorized",
        help="Confirm you are allowed to check this number (needed for "
        "--presence).",
    ),
    all_layers: bool = typer.Option(
        False, "--all",
        help="Full scan (offline + api + ai) and list the dorking links. "
        "Opens nothing.",
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Run only the offline (libphonenumber) layer."
    ),
    api: bool = typer.Option(
        False, "--api", help="Run only the API data providers. Combine freely."
    ),
    ai: bool = typer.Option(
        False, "--ai", help="Run only the AI summary. Combine freely."
    ),
    lookup: bool = typer.Option(
        False, "--lookup",
        help="Do not scan; open the top 5 reverse-lookup sites in the browser.",
    ),
    lookup_all: bool = typer.Option(
        False, "--lookup-all",
        help="Do not scan; open every reverse-lookup site in the browser.",
    ),
    dorking: bool = typer.Option(
        False, "--dorking",
        help="Do not scan; open the top 5 search-engine dorks in the browser.",
    ),
    dorking_all: bool = typer.Option(
        False, "--dorking-all",
        help="Do not scan; open every search-engine dork in the browser.",
    ),
    heatmap: bool = typer.Option(
        False, "--heatmap",
        help="Batch only: show just the colored risk grid.",
    ),
    discord: bool = typer.Option(
        False, "--discord",
        help="Send the result to your Discord webhook (DISCORD_WEBHOOK_URL).",
    ),
    discord_url: str | None = typer.Option(
        None, "--discord-url", help="Discord webhook URL (overrides config)."
    ),
    country: str | None = typer.Option(
        None, "--country", help="Country hint (ISO) for a local-format number, e.g. GB."
    ),
    output: str | None = typer.Option(
        None, "--output", "-o", help="Save a report to a file (.json, .md, or .pdf)."
    ),
    ask: str | None = typer.Option(
        None, "--ask", help="Ask a question, answered only from what was found."
    ),
) -> None:
    """Look up a phone number (or a whole file with --input).

    A full scan (default, or --all) runs offline + api + ai and lists the
    dorking links. Pick single layers with --offline, --api, --ai (combine
    them). The --lookup / --dorking flags do NOT scan; they open sites in your
    browser. Flags can go before or after the number. Examples:

      numint +14155550123                     full scan, lists dorking links

      numint +14155550123 --api --ai          only API data + AI summary

      numint +14155550123 --offline           only offline basics

      numint +14155550123 --lookup            open the top 5 lookup sites

      numint +14155550123 --lookup-all        open every lookup site

      numint +14155550123 --dorking           open the top 5 dork searches

      numint +14155550123 --dorking-all       open every dork search

      numint +14155550123 --presence --yes-authorized

      numint scan --input numbers.txt --heatmap
    """
    setup_logging()

    # --lookup / --dorking are actions, not scans: open sites and stop.
    if lookup or lookup_all or dorking or dorking_all:
        if not number:
            err_console.print(
                "[bold red]Error:[/] --lookup / --dorking need a number."
            )
            raise typer.Exit(code=2)
        _open_action(
            number, country=country,
            lookup=lookup, lookup_all=lookup_all,
            dorking=dorking, dorking_all=dorking_all,
        )
        return

    if presence and not yes_authorized:
        err_console.print(
            "[bold red]Refused:[/] --presence actively probes third-party "
            "sites. Re-run with [bold]--yes-authorized[/] to confirm you are "
            "authorized to investigate this number."
        )
        raise typer.Exit(code=2)

    if input:
        _batch(
            input, as_json, no_cache, no_ai, country,
            presence=presence, heatmap=heatmap,
            discord=discord, discord_url=discord_url,
        )
        return
    if not number:
        err_console.print("[bold red]Error:[/] provide a number or --input file.")
        raise typer.Exit(code=2)

    # No selector (or --all) means a full scan that also lists the dork links;
    # otherwise run only the layers the user asked for.
    selective = any([offline, api, ai])
    if all_layers or not selective:
        w_offline, w_api, w_ai, w_dorking = True, True, True, True
    else:
        w_offline, w_api, w_ai, w_dorking = offline, api, ai, False
    if no_ai:
        w_ai = False

    _run_and_render(
        number,
        with_offline=w_offline,
        with_api=w_api,
        with_ai=w_ai,
        with_footprint=False,
        with_dorking=w_dorking,
        presence=presence,
        as_json=as_json,
        no_cache=no_cache,
        country=country,
        output=output,
        ask=ask,
        discord=discord,
        discord_url=discord_url,
    )


def _batch(
    input: Path,
    as_json: bool,
    no_cache: bool,
    no_ai: bool,
    country: str | None,
    *,
    presence: bool = False,
    heatmap: bool = False,
    discord: bool = False,
    discord_url: str | None = None,
) -> None:
    if not input.exists():
        err_console.print(f"[bold red]Error:[/] file not found: {input}")
        raise typer.Exit(code=2)
    numbers = [
        line.strip()
        for line in input.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not numbers:
        err_console.print("[bold red]Error:[/] no numbers in file.")
        raise typer.Exit(code=2)

    engine = Engine()

    async def run_all() -> list:
        profiles = []
        # Sequential across numbers so per-provider rate limits are respected.
        for num in numbers:
            try:
                profiles.append(
                    await engine.scan(
                        num,
                        default_region=country.upper() if country else None,
                        use_cache=not no_cache,
                        with_footprint=False,
                        with_presence=presence,
                        with_ai=not no_ai,
                    )
                )
            except ParseError as exc:
                err_console.print(f"[yellow]Skipped[/] {num}: {exc}")
        return profiles

    profiles = asyncio.run(run_all())

    if as_json:
        import json

        console.print_json(
            json.dumps([p.model_dump(mode="json") for p in profiles], default=str)
        )
    elif heatmap:
        render_batch_heatmap(profiles, console)
    else:
        for p in profiles:
            render_console(p, console)
            console.rule(style=MUTED)
        # Trailing heatmap gives an at-a-glance triage view after the cards.
        render_batch_heatmap(profiles, console)

    for p in profiles:
        _maybe_discord(p, discord, discord_url)

    # In --json mode stdout must stay pure JSON, so the summary goes to stderr.
    summary_console = err_console if as_json else console
    summary_console.print(
        f"[{MUTED}]Scanned {len(profiles)} of {len(numbers)} numbers.[/]"
    )


@app.command()
def providers() -> None:
    """List every data + LLM provider and whether each is configured."""
    setup_logging()
    settings = get_settings()
    engine = Engine()

    table = Table(title="Data Providers", title_style=f"bold {ACCENT}")
    table.add_column("Provider")
    table.add_column("Key")
    table.add_column("Status")
    table.add_column("Get a free key", style=MUTED)
    for info in engine.provider_infos():
        if info["configured"]:
            status = Text("● active", style="green")
        elif not info["requires_key"]:
            status = Text("● active (no key)", style="green")
        else:
            status = Text("○ not configured", style=MUTED)
        opt = " (optional)" if info["optional"] else ""
        table.add_row(
            info["name"] + opt,
            info["env_key"] or "-",
            status,
            info["signup_url"] or "-",
        )
    console.print(table)

    # LLM providers
    from .ai.base import get_llm_classes

    ai_table = Table(title="LLM Providers (AI layer)", title_style=f"bold {ACCENT}")
    ai_table.add_column("Provider")
    ai_table.add_column("Key")
    ai_table.add_column("Status")
    active_ai = (settings.ai_provider or "").lower()
    for name, cls in get_llm_classes().items():
        inst = cls(settings)
        if inst.is_configured():
            mark = "● configured"
            if active_ai == name or (not active_ai):
                mark += " · selected"
            status = Text(mark, style="green")
        else:
            status = Text("○ not configured", style=MUTED)
        ai_table.add_row(name, cls.env_key, status)
    console.print(ai_table)
    console.print(
        Text(
            "Set AI_PROVIDER + the matching key to enable the AI Analysis section.",
            style=f"italic {MUTED}",
        )
    )


@config_app.command("set")
def config_set(
    provider: str = typer.Argument(..., help="Key name, e.g. NUMVERIFY_API_KEY."),
    key: str = typer.Argument(..., help="The API key value."),
) -> None:
    """Persist an API key to the user config file."""
    path = write_key(provider, key)
    reset_settings_cache()
    console.print(f"[green]Saved[/] {provider} to {path}")


@config_app.command("list")
def config_list() -> None:
    """Show which keys are configured (values are masked)."""
    settings = get_settings()
    engine = Engine()
    table = Table(title="Configured keys")
    table.add_column("Key")
    table.add_column("Value")
    seen = set()
    for info in engine.provider_infos():
        if not info["env_key"] or info["env_key"] in seen:
            continue
        seen.add(info["env_key"])
        val = settings.get(info["env_key"])
        table.add_row(info["env_key"], _mask(val))
    for extra in ("TWILIO_AUTH_TOKEN", "DISCORD_WEBHOOK_URL",
                  "DISCORD_BOT_TOKEN", "AI_PROVIDER", "AI_MODEL",
                  "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        table.add_row(extra, _mask(settings.get(extra)))
    console.print(table)


@config_app.command("path")
def config_path_cmd() -> None:
    """Print the config file path."""
    console.print(str(config_path()))


def _mask(value: str | None) -> str:
    if not value:
        return "[dim]-[/]"
    if len(value) <= 6:
        return "••••"
    return f"{value[:3]}••••{value[-2:]}"


@app.command("discord-bot")
def discord_bot(
    token: str | None = typer.Option(
        None, "--token", help="Bot token (overrides DISCORD_BOT_TOKEN)."
    ),
) -> None:
    """Run the Discord bot - control numint with /scan from Discord."""
    setup_logging()
    try:
        from .integrations.discord_bot import run_bot
    except ImportError:
        err_console.print(
            "[bold red]Discord extra not installed.[/] Run: "
            'pip install "numint[discord]"'
        )
        raise typer.Exit(code=1) from None
    console.print(
        f"[{ACCENT}]Numint[/] Discord bot starting… "
        f"[{MUTED}](Ctrl+C to stop)[/]"
    )
    try:
        run_bot(token)
    except RuntimeError as exc:
        err_console.print(f"[bold red]Error:[/] {exc}")
        raise typer.Exit(code=1) from None


@app.command()
def web(
    port: int = typer.Option(8080, "--port", help="Port to serve on."),
    host: str = typer.Option(
        "127.0.0.1", "--host",
        help="Host/interface to bind. Default is localhost only; use "
        "0.0.0.0 to expose it on your network.",
    ),
) -> None:
    """Launch the web UI + API."""
    _launch_web(host=host, port=port)


def _launch_web(host: str, port: int) -> None:
    if port < 1024:
        err_console.print(
            f"[yellow]Note:[/] port {port} is privileged; you may need "
            "elevated privileges (sudo / admin) to bind it."
        )
    try:
        import uvicorn

        from .web.app import create_app
    except ImportError:
        err_console.print(
            "[bold red]Web extras not installed.[/] Run: "
            "pip install 'numint[web]'"
        )
        raise typer.Exit(code=1) from None

    console.print(
        f"[{ACCENT}]Numint[/] web UI running at [bold]http://{host}:{port}[/]  "
        f"[{MUTED}](Ctrl+C to stop)[/]"
    )
    uvicorn.run(create_app(), host=host, port=port, log_level="warning")


if __name__ == "__main__":  # pragma: no cover
    app()
