"""One typed command registry for the CLI, the talk session and the web palette.

CLI commands, natural-language actions, web buttons and the web command
composer all dispatch through this table, so both interfaces expose the same
investigation capabilities against the same case state. The registry carries
arguments, help text, required capabilities, availability, result shape,
progress events and cancellation behaviour — help and capability displays are
generated from it rather than hand-maintained.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Any

from snoop.config import config
from snoop.core import Bus
from snoop.model import utcnow
from snoop.pipeline import Dossier


@dataclass
class Arg:
    name: str
    help: str = ""
    flag: str = ""  # option form, e.g. "--engine"
    short: str = ""  # short alias, e.g. "-c"
    takes_value: bool = True
    positional: bool = False
    greedy: bool = False  # join all remaining tokens (question/target text)
    multiple: bool = False
    default: Any = None
    choices: list[str] | None = None
    required: bool = False


@dataclass
class Command:
    name: str
    family: str
    usage: str
    help: str
    args: list[Arg] = field(default_factory=list)
    needs_case: bool = True
    capability: str = ""  # empty means always available
    events: list[str] = field(default_factory=list)
    cancellable: bool = False

    def parse(self, tokens: list[str]) -> dict:
        values: dict[str, Any] = {}
        positional_specs = [a for a in self.args if a.positional]
        by_flag: dict[str, Arg] = {}
        for spec in self.args:
            if spec.flag:
                by_flag[spec.flag] = spec
            if spec.short:
                by_flag[spec.short] = spec
        index = 0
        position = 0
        unknown: list[str] = []
        while index < len(tokens):
            token = tokens[index]
            if token in by_flag:
                spec = by_flag[token]
                if spec.takes_value:
                    index += 1
                    if index >= len(tokens):
                        raise CommandError(f"{self.name}: {token} needs a value")
                    value: Any = tokens[index]
                    if spec.choices and value not in spec.choices:
                        raise CommandError(
                            f"{self.name}: {value!r} must be one of {', '.join(spec.choices)}"
                        )
                else:
                    value = True
                if spec.multiple:
                    values.setdefault(spec.name, []).append(value)
                else:
                    values[spec.name] = value
            elif positional_specs and position < len(positional_specs):
                spec = positional_specs[position]
                if spec.greedy:
                    parts: list[str] = []
                    while index < len(tokens) and tokens[index] not in by_flag:
                        parts.append(tokens[index])
                        index += 1
                    joined = " ".join(parts)
                    if spec.multiple:
                        values.setdefault(spec.name, []).append(joined)
                    else:
                        values[spec.name] = joined
                    position += 1
                    continue
                if spec.multiple:
                    values.setdefault(spec.name, []).append(token)
                else:
                    values[spec.name] = token
                    position += 1
            else:
                unknown.append(token)
            index += 1
        if unknown:
            raise CommandError(
                f"{self.name}: unexpected argument(s): {' '.join(unknown)}; usage: {self.usage}"
            )
        for spec in self.args:
            if spec.name not in values:
                values[spec.name] = list(spec.default or []) if spec.multiple else spec.default
            if spec.required and not values.get(spec.name):
                raise CommandError(f"{self.name}: --{spec.name.replace('_', '-')} is required")
        return values


class CommandError(ValueError):
    pass


class Context:
    def __init__(self, dossier: Dossier | None, bus: Bus, args: dict, runtime: str = "cli"):
        self.dossier = dossier
        self.bus = bus
        self.args = args
        self.runtime = runtime  # "cli" | "talk" | "web"

    @property
    def case(self) -> Dossier:
        if not self.dossier:
            raise CommandError("no active case — start one with: investigate NAME")
        return self.dossier


COMMANDS: dict[str, Command] = {}


def command(cmd: Command) -> Command:
    COMMANDS[cmd.name] = cmd
    return cmd


def _workflow(ctx: Context):
    from snoop.workflow import Workflow

    return Workflow(ctx.case, ctx.bus)


# ------------------------------------------------------------------- registry


command(
    Command(
        "investigate",
        family="investigate",
        usage='investigate "Full Name" [--mode full|accounts|quick|standard|deep] [--exact-name] [--guided] [-c FACT]... [--as username|name|email|domain]',
        help="start a complete investigation (web discovery, sources, accounts, follow-up)",
        args=[
            Arg("target", positional=True, greedy=True, required=True, help="who to investigate"),
            Arg("exact_name", flag="--exact-name", takes_value=False, default=False, help="exclude other readable names from candidates"),
            Arg("guided", flag="--guided", takes_value=False, default=False, help="pause for evidence-based interview rounds"),
            Arg("mode", flag="--mode", choices=["full", "accounts", "quick", "standard", "deep"], default="full"),
            Arg("preset", flag="--preset", choices=["quick", "standard", "deep"], default=None),
            Arg("kind", flag="--as", choices=["username", "name", "email", "domain"]),
            Arg("context", flag="--context", short="-c", multiple=True, help="known facts"),
        ],
        needs_case=False,
        events=["stage", "query", "result", "source", "hit", "evidence", "done"],
        cancellable=True,
    )
)

command(Command("questions", family="conversation", usage="questions", help="show the one saved clarification question"))
command(Command("briefing", family="conversation", usage="briefing", help="show coverage, cited observations, gaps and next actions"))
command(
    Command(
        "answer",
        family="conversation",
        usage="answer TEXT",
        help="answer, correct, skip, or mark the saved question unknown",
        args=[Arg("text", positional=True, greedy=True, required=True)],
        events=["answer", "question"],
    )
)

command(
    Command(
        "plan",
        family="workflow",
        usage="plan",
        help="inspect the current plan, budgets and remaining frontier",
        events=[],
    )
)

command(
    Command(
        "run",
        family="workflow",
        usage="run [--preset quick|standard|deep] [--mode full|accounts]",
        help="run the investigation loop automatically until stop or budget",
        args=[
            Arg("preset", flag="--preset", choices=["quick", "standard", "deep"], default=None),
            Arg("mode", flag="--mode", choices=["full", "accounts"], default=None),
        ],
        events=["stage", "query", "result", "source", "hit", "evidence", "lead", "done"],
        cancellable=True,
    )
)

command(
    Command(
        "step",
        family="workflow",
        usage="step",
        help="execute exactly one planned action",
        events=["lead", "query", "result", "source"],
    )
)

command(
    Command(
        "pause",
        family="workflow",
        usage="pause",
        help="pause the running investigation (current step finishes)",
        events=["paused"],
    )
)

command(
    Command(
        "continue",
        family="workflow",
        usage="continue",
        help="continue a paused or stopped investigation from its saved frontier",
        events=["stage", "query", "result", "source", "done"],
        cancellable=True,
    )
)

command(
    Command(
        "stop",
        family="workflow",
        usage="stop",
        help="cancel the running investigation; completed work stays saved",
        events=["cancelled"],
    )
)

command(
    Command(
        "cases",
        family="case",
        usage="cases",
        help="list saved cases",
        needs_case=False,
    )
)

command(
    Command(
        "resume",
        family="case",
        usage="resume CASE | last",
        help="select and restore a saved case (state, decisions, frontier)",
        args=[Arg("case", positional=True, required=True, help="case id or 'last'")],
        needs_case=False,
    )
)

command(
    Command(
        "case",
        family="case",
        usage="case",
        help="overview of the active case",
    )
)

command(
    Command(
        "anchor",
        family="accounts",
        usage="anchor URL",
        help="record a user-supplied profile URL as scope and validate it",
        args=[Arg("url", positional=True, required=True)],
        events=["source", "hit"],
    )
)

command(
    Command(
        "context",
        family="workflow",
        usage='context "known fact"',
        help="add a known fact; every account is re-scored against it",
        args=[Arg("fact", positional=True, greedy=True, required=True)],
    )
)

command(
    Command(
        "deepen",
        family="accounts",
        usage="deepen REF",
        help="platform deep-dive for one exact account",
        args=[Arg("ref", positional=True, required=True)],
        events=["deepen"],
    )
)

command(
    Command(
        "search",
        family="search",
        usage='search --query QUERY [--engine google|brave] [--count N] | search --context "facts"',
        help="run an explicit web query through a selected engine",
        args=[
            Arg("query", flag="--query", short="-q", help="query text (quotes/operators allowed)"),
            Arg("engine", flag="--engine", choices=["google", "brave"], default=None),
            Arg("count", flag="--count", default=10),
            Arg("context", flag="--context", help="legacy form: query the target plus these facts"),
        ],
        capability="web search",
        events=["query", "result"],
    )
)

command(
    Command(
        "manual-search",
        family="search",
        usage='manual-search --query QUERY --url URL [--url URL...] [--query-link URL] [--note TEXT]',
        help="record results you found yourself (labelled manual assistance)",
        args=[
            Arg("query", flag="--query", required=True),
            Arg("url", flag="--url", multiple=True, required=True, help="result URL(s) you picked"),
            Arg("query_link", flag="--query-link", default=""),
            Arg("note", flag="--note", default=""),
        ],
        events=["query"],
    )
)

command(
    Command(
        "import",
        family="frontier",
        usage="import [--url URL]... [--domain DOMAIN]... [--document URL]... "
        "[--authorized-email EMAIL]... [--search-email] [--text TEXT]",
        help="add explicitly supplied public leads with user-import provenance",
        args=[
            Arg("url", flag="--url", multiple=True),
            Arg("domain", flag="--domain", multiple=True),
            Arg("document", flag="--document", multiple=True),
            Arg("authorized_email", flag="--authorized-email", multiple=True),
            Arg("search_email", flag="--search-email", takes_value=False, default=False),
            Arg("text", flag="--text", default=""),
        ],
    )
)

command(
    Command("accounts", family="accounts", usage="accounts [REF]", help="list accounts found (or inspect one)",
            args=[Arg("ref", positional=True)]),
)

command(Command("aliases", family="accounts", usage="aliases", help="aliases and handles with their origins"))

command(
    Command(
        "read",
        family="read",
        usage="read URL",
        help="retrieve a source and investigate its links",
        args=[Arg("url", positional=True, required=True)],
        events=["source", "evidence"],
    )
)

command(
    Command(
        "follow",
        family="read",
        usage="follow REF [--depth 1|2]",
        help="follow links published by one account",
        args=[
            Arg("ref", positional=True, required=True),
            Arg("depth", flag="--depth", default=1),
        ],
        events=["hit"],
    )
)

command(
    Command(
        "document",
        family="documents",
        usage="document URL",
        help="read a public PDF/document (text, author fields, links)",
        args=[Arg("url", positional=True, required=True)],
        events=["document"],
    )
)

command(
    Command(
        "archive",
        family="documents",
        usage="archive URL|DOMAIN",
        help="Wayback CDX/Common Crawl history for a URL or domain",
        args=[Arg("target", positional=True, required=True)],
        events=["archive"],
    )
)

command(
    Command(
        "domain",
        family="documents",
        usage="domain DOMAIN",
        help="public RDAP/DNS/certificate records for a domain",
        args=[Arg("domain", positional=True, required=True)],
        events=["domain"],
    )
)

command(
    Command(
        "image",
        family="documents",
        usage="image URL [--reverse]",
        help="extract text/handles from an image; --reverse submits it to Google Lens",
        args=[
            Arg("url", positional=True, required=True),
            Arg("reverse", flag="--reverse", takes_value=False, default=False),
        ],
        capability="reverse image needs SERPAPI_KEY",
    )
)

command(
    Command(
        "leads",
        family="frontier",
        usage="leads [--status pending|running|explored|deferred|rejected]",
        help="inspect the ranked lead frontier",
        args=[Arg("status", flag="--status", default=None)],
    )
)

command(Command("queries", family="frontier", usage="queries", help="collection history of executed searches"))

command(
    Command(
        "sources",
        family="frontier",
        usage="sources [ID]",
        help="visited sources (or one source with its excerpt)",
        args=[Arg("id", positional=True)],
    )
)

command(
    Command(
        "evidence",
        family="evidence",
        usage="evidence REF",
        help="evidence records behind one account",
        args=[Arg("ref", positional=True, required=True)],
    )
)

command(
    Command(
        "compare",
        family="evidence",
        usage="compare REF1 REF2",
        help="supporting and conflicting evidence between two accounts",
        args=[
            Arg("left", positional=True, required=True),
            Arg("right", positional=True, required=True),
        ],
    )
)

command(
    Command(
        "verify",
        family="evidence",
        usage="verify REF",
        help="fresh observation of one account",
        args=[Arg("ref", positional=True, required=True)],
        events=["source"],
    )
)

command(Command("pick", family="decisions", usage="pick A", help="select an identity (a decision, not proof)",
                args=[Arg("label", positional=True, required=True)]))
command(Command("merge", family="decisions", usage="merge A B", help="merge two identities by user constraint",
                args=[Arg("a", positional=True, required=True), Arg("b", positional=True, required=True)]))
command(Command("split", family="decisions", usage="split A REF", help="split one account out of an identity",
                args=[Arg("label", positional=True, required=True), Arg("ref", positional=True, required=True)]))
command(Command("keep", family="decisions", usage="keep REF", help="keep an account despite its score",
                args=[Arg("ref", positional=True, required=True)]))
command(Command("discard", family="decisions", usage="discard REF", help="discard an account with a recorded constraint",
                args=[Arg("ref", positional=True, required=True)]))
command(Command("undo", family="decisions", usage="undo", help="reverse the most recent decision"))

command(Command("graph", family="views", usage="graph", help="source-linked relationship graph"))
command(Command("timeline", family="views", usage="timeline [A]", help="dated events with provenance",
                args=[Arg("label", positional=True)]))
command(
    Command(
        "diff",
        family="views",
        usage="diff CASE1 CASE2",
        help="compare two case snapshots",
        args=[Arg("before", positional=True, required=True), Arg("after", positional=True, required=True)],
        needs_case=False,
    )
)

command(
    Command(
        "ask",
        family="report",
        usage="ask QUESTION",
        help="answer a question from the saved evidence",
        args=[Arg("question", positional=True, greedy=True, required=True)],
    )
)

command(
    Command(
        "agent",
        family="agent",
        usage='agent ["goal"] [--steps N]',
        help="AI investigator: reasons step by step, picks tools, asks you when it cannot see a page",
        args=[
            Arg("goal", positional=True, greedy=True, help="optional focus, e.g. find their professional work"),
            Arg("steps", flag="--steps", help="maximum agent steps (default by preset)"),
        ],
        events=["agent_thought", "agent_tool", "agent_observation", "agent_done", "question"],
        cancellable=True,
    )
)
command(
    Command(
        "trace",
        family="evidence",
        usage="trace REF",
        help="show how the investigation found an account, source or evidence record",
        args=[Arg("ref", positional=True, required=True)],
    )
)
command(
    Command(
        "profile",
        family="profile",
        usage="profile [--ai]",
        help="what the public footprint says or implies about the subject (stated / inferred / AI)",
        args=[Arg("ai", flag="--ai", takes_value=False, default=False, help="ask the AI to read the evidence for more facts")],
    )
)
command(
    Command(
        "fact",
        family="profile",
        usage="fact FACT_ID confirm|reject|reset [note]",
        help="confirm or reject a profile fact; rejecting an account fact discards that account",
        args=[
            Arg("fact_id", positional=True, required=True),
            Arg("verdict", positional=True, required=True),
            Arg("note", positional=True, greedy=True),
        ],
    )
)
command(
    Command(
        "connections",
        family="evidence",
        usage="connections",
        help="explainable links between accounts and sources (strength-labelled)",
    )
)

command(Command("report", family="report", usage="report", help="readable case report"))
command(
    Command(
        "export",
        family="report",
        usage="export [--redact]",
        help="write JSON/HTML report files",
        args=[Arg("redact", flag="--redact", takes_value=False, default=False)],
    )
)

command(Command("providers", family="config", usage="providers", help="search/AI/enrichment provider readiness", needs_case=False))
command(Command("doctor", family="config", usage="doctor", help="version, paths, configuration diagnostics", needs_case=False))


# ------------------------------------------------------------------- handlers


async def _h_investigate(ctx: Context) -> dict:
    from snoop.pipeline import investigate

    args = ctx.args
    mode = args.get("mode") or "full"
    preset = args.get("preset")
    if mode in {"quick", "standard", "deep"}:
        preset = preset or mode
        mode = "full"
    dossier = await investigate(
        args["target"],
        ctx.bus,
        kind=args.get("kind"),
        context=args.get("context") or None,
        mode=mode,
        preset=preset,
        exact_name=bool(args.get("exact_name")),
        guided=bool(args.get("guided")),
    )
    st = dossier.stats
    identities = dossier.analysis.get("identities", [])
    text = (
        f"case {dossier.id}: {st.get('queries', 0)} quer{'y' if st.get('queries') == 1 else 'ies'}, "
        f"{st.get('sources', 0)} source(s) read, {st.get('accounts_returned', 0)} account(s), "
        f"{len(identities)} identity hypothesis/hypotheses — {st.get('stop_reason', '')}"
    )
    return {"text": text, "data": {"case_id": dossier.id, "stats": st}, "case": dossier}


async def _h_plan(ctx: Context) -> dict:
    wf = _workflow(ctx)
    queue_rows = [
        {
            "id": l["id"],
            "type": l["type"],
            "purpose": l["purpose"],
            "expected": l.get("expected", ""),
            "score": round(float(l.get("score", 0)), 1),
            "status": l.get("status"),
            "origin": l.get("origin"),
        }
        for l in sorted(ctx.case.leads, key=lambda x: -float(x.get("score", 0)))
    ][:40]
    data = {"status": wf.status(), "plan": queue_rows}
    pending = [row for row in queue_rows if row["status"] == "pending"]
    text = (
        f"{len(pending)} pending action(s), {wf.spent.get('searches', 0)}/{wf.budgets['searches']} searches, "
        f"{wf.spent.get('page_fetches', 0)}/{wf.budgets['page_fetches']} fetches used"
    )
    if pending:
        text += "; next: " + pending[0]["purpose"]
    return {"text": text, "data": data}


async def _h_run(ctx: Context) -> dict:
    if ctx.runtime == "web":
        from snoop import jobs

        job = jobs.start_job(ctx.case, preset=ctx.args.get("preset"), mode=ctx.args.get("mode"))
        return {
            "text": f"investigation running; follow the live feed (job {job.id})",
            "data": {"job": job.status()},
            "case": ctx.case,
        }
    from snoop.workflow import Workflow

    wf = Workflow(ctx.case, ctx.bus, preset=ctx.args.get("preset"), mode=ctx.args.get("mode"))
    status = await wf.run()
    return {
        "text": f"run {status.get('status')}: {status.get('stop_reason', '')}",
        "data": status,
        "case": ctx.case,
    }


async def _h_step(ctx: Context) -> dict:
    wf = _workflow(ctx)
    if not ctx.case.leads:
        await wf.start()
    lead = wf.queue.next()
    if lead is None:
        return {"text": "no pending lead — the frontier is empty", "data": {"leads": wf.queue.stats()}}
    purpose = lead["purpose"]
    ran = await wf.step()
    return {
        "text": f"executed: {purpose}" if ran else "nothing executed",
        "data": {"executed": purpose if ran else None, "leads": wf.queue.stats()},
    }


async def _h_pause(ctx: Context) -> dict:
    from snoop import jobs

    if ctx.runtime == "web":
        message = await jobs.control(ctx.case.id, "pause")
        return {"text": message}
    return {"text": "pause applies to a running job (web) or between steps here; use 'step' to advance one action"}


async def _h_continue(ctx: Context) -> dict:
    from snoop import jobs

    if ctx.runtime == "web":
        message = await jobs.control(ctx.case.id, "continue")
        return {"text": message, "case": ctx.case}
    return await _h_run(ctx)


async def _h_stop(ctx: Context) -> dict:
    from snoop import jobs

    message = await jobs.control(ctx.case.id, "stop")
    if "no running job" in message:
        ctx.case.workflow.update({"status": "stopped", "stop_reason": "stopped by the analyst", "stopped_at": utcnow()})
        ctx.case.record_action("stop")
        ctx.case.save()
        message = "case marked stopped; completed work and the remaining frontier are saved"
    return {"text": message, "case": ctx.case}


async def _h_cases(_ctx: Context) -> dict:
    rows = Dossier.list_cases()
    text = f"{len(rows)} saved case(s)" + (
        "; most recent: " + rows[0]["id"] if rows else ""
    )
    return {"text": text, "data": rows}


async def _h_resume(ctx: Context) -> dict:
    ref = ctx.args["case"]
    dossier = resolve_case(ref)
    if not dossier:
        raise CommandError(f"case {ref!r} not found; use 'cases'")
    return {
        "text": (
            f"resumed {dossier.id}: {len(dossier.all_accounts)} account(s), "
            f"{len(dossier.queries)} quer{'y' if len(dossier.queries) == 1 else 'ies'}, "
            f"{len(dossier.leads)} lead(s), decisions and history restored"
        ),
        "data": {"case_id": dossier.id, "workflow": dossier.workflow},
        "case": dossier,
    }


def resolve_case(ref: str) -> Dossier | None:
    ref = (ref or "").strip()
    if ref.casefold() in {"last", "latest", "."}:
        rows = Dossier.list_cases()
        return Dossier.load(rows[0]["id"]) if rows else None
    return Dossier.load(ref)


async def _h_case(ctx: Context) -> dict:
    from snoop.actions import case_overview

    data = case_overview(ctx.case)
    cov = data["coverage"]
    text = (
        f"{ctx.case.id} — {ctx.case.target} ({ctx.case.kind}, {ctx.case.mode}): "
        f"{len(data['accounts'])} account(s), {cov['sources_read']} source(s) read, "
        f"{len(data['queries'])} quer{'y' if len(data['queries']) == 1 else 'ies'}, "
        f"status {ctx.case.workflow.get('status', 'idle')}"
    )
    return {"text": text, "data": data}


async def _h_search(ctx: Context) -> dict:
    from snoop import planner
    from snoop import search as search_mod

    query = ctx.args.get("query") or ""
    engine = ctx.args.get("engine")
    if not query and ctx.args.get("context"):
        # Legacy form: `search --context "robotics Berlin"` queries the target
        # plus those facts, preserving the documented behaviour.
        query = " ".join(x for x in [ctx.case.target, ctx.args["context"]] if x).strip()
        engine = engine or "brave"
    if not query:
        raise CommandError("search: --query is required (or --context with an active case)")
    response = await search_mod.web_search(query, engine, count=int(ctx.args.get("count") or 10))
    if response.outcome == "missing_key":
        return {
            "text": f"web search unavailable: {response.error}",
            "data": response.to_dict(),
            "status": "unavailable",
        }
    record = search_mod.query_record(response, via="explicit-command")
    existing = next((q for q in ctx.case.queries if q.get("id") == record["id"]), None)
    if not existing:
        ctx.case.queries.append(record)
    leads = planner.react_to_search(record, ctx.case.target)
    added = 0
    from snoop.leads import LeadQueue

    queue = LeadQueue(ctx.case)
    for lead in leads:
        if queue.add(
            lead["type"], lead["args"], lead["purpose"], lead.get("expected", ""),
            clues=lead.get("clues"), origin="user", score=lead.get("score", 0),
        ):
            added += 1
    ctx.case.record_action("search", query=query, engine=response.engine, results=len(response.results))
    ctx.case.save()
    text = (
        f"{response.provider}: {len(response.results)} result(s) for {query!r}; "
        f"{added} follow-up lead(s) queued"
    )
    if response.error:
        text = f"note: {response.error} — " + text
    return {"text": text, "data": record}


async def _h_manual_search(ctx: Context) -> dict:
    from snoop.workflow import import_search

    result = import_search(
        ctx.case,
        ctx.args["query"],
        ctx.args["url"],
        ctx.bus,
        note=ctx.args.get("note", ""),
        query_link=ctx.args.get("query_link", ""),
    )
    return {
        "text": (
            f"manual assistance recorded: {result['results']} result(s) for {result['query']!r}; "
            f"{result['leads_added']} lead(s) queued — this is not an automated search"
        ),
        "data": result,
    }


async def _h_import(ctx: Context) -> dict:
    """Turn analyst-supplied public material into provenance-labelled leads."""
    import re

    from snoop.actions import _site_for
    from snoop.leads import LeadQueue
    from snoop.model import evidence_record

    args = ctx.args
    supplied = any(
        args.get(key) for key in ("url", "domain", "document", "authorized_email", "text")
    )
    if not supplied:
        raise CommandError("import: supply --url, --domain, --document, --authorized-email, or --text")
    queue = LeadQueue(ctx.case)
    added = 0

    def add(kind: str, values: dict, purpose: str, expected: str, score: float) -> None:
        nonlocal added
        row = queue.add(
            kind,
            values,
            purpose,
            expected,
            clues=["user-import"],
            origin="user-import",
            score=score,
        )
        if row and row.get("status") == "pending":
            added += 1

    for url in args.get("url") or []:
        if _site_for(url):
            add(
                "check_account",
                {"url": url},
                f"Validate analyst-supplied profile {url[:70]}",
                "Public profile observations; supply is not independent discovery",
                9.0,
            )
        else:
            add(
                "read_source",
                {"url": url},
                f"Read analyst-supplied page {url[:70]}",
                "Evidence and follow-up clues on the supplied public page",
                8.0,
            )
    for url in args.get("document") or []:
        add(
            "read_document",
            {"url": url},
            f"Read analyst-supplied document {url[:65]}",
            "Document text, metadata and links",
            8.0,
        )
    for domain in args.get("domain") or []:
        domain = domain.strip().casefold().removeprefix("www.").rstrip(".")
        if not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", domain):
            raise CommandError(f"import: invalid public domain {domain!r}")
        add(
            "crawl_site",
            {"url": f"https://{domain}"},
            f"Read analyst-supplied domain {domain}",
            "Relevant public site pages and explicit profile links",
            7.0,
        )
        add(
            "domain_lookup",
            {"domain": domain},
            f"Inspect public records for analyst-supplied domain {domain}",
            "RDAP, DNS and certificate clues (not ownership proof)",
            3.0,
        )
    emails = []
    for email in args.get("authorized_email") or []:
        email = email.strip().casefold()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise CommandError(f"import: invalid authorized email {email!r}")
        emails.append(email)
        if email not in ctx.case.authorized_emails:
            ctx.case.authorized_emails.append(email)
        if args.get("search_email"):
            add(
                "web_search",
                {"query": f'"{email}"'},
                "Search an explicitly authorized email as an exact public identifier",
                "Public pages containing the exact authorized address",
                8.5,
            )
    text_value = str(args.get("text") or "").strip()
    if text_value:
        source_url = f"user://{ctx.case.id}/pasted-text/{len(ctx.case.action_history) + 1}"
        record = evidence_record(
            claim="user-supplied-text",
            source_url=source_url,
            excerpt=text_value[:500],
            value=text_value[:2000],
            method="analyst-import",
            kind="user_statement",
            supports=None,
            dependence=source_url,
            limitation="Supplied by the analyst; not independently discovered or verified.",
        )
        if not any(r.get("id") == record["id"] for r in ctx.case.evidence_records):
            ctx.case.evidence_records.append(record)
        for url in re.findall(r"https?://[^\s\"'<>]+", text_value)[:8]:
            add(
                "read_source",
                {"url": url.rstrip(".,;)")},
                "Read a public URL present in analyst-supplied text",
                "Source observations for the supplied clue",
                6.0,
            )
        for handle in re.findall(r"(?<![\w@])@([A-Za-z0-9][A-Za-z0-9._-]{2,30})", text_value)[:8]:
            add(
                "web_search",
                {"query": f'"{handle}"'},
                f"Search handle {handle!r} present in analyst-supplied text",
                "Public accounts and pages using the supplied handle",
                5.0,
            )
    ctx.case.record_action(
        "import",
        urls=len(args.get("url") or []),
        domains=len(args.get("domain") or []),
        documents=len(args.get("document") or []),
        authorized_emails=len(emails),
        pasted_text=bool(text_value),
        leads_added=added,
    )
    ctx.case.save()
    return {
        "text": f"recorded analyst import; {added} follow-up lead(s) queued",
        "data": {"leads_added": added, "authorized_emails_added": len(emails)},
    }


async def _h_accounts(ctx: Context) -> dict:
    from snoop.actions import case_overview

    if ctx.args.get("ref"):
        from snoop.actions import show_evidence

        return {"text": "evidence", "data": show_evidence(ctx.case, ctx.args["ref"])}
    data = case_overview(ctx.case)["accounts"]
    return {
        "text": f"{len(data)} account(s); {sum(1 for a in data if a['verdict'] == 'insufficient')} unresolved (insufficient information)",
        "data": data,
    }


async def _h_aliases(ctx: Context) -> dict:
    from snoop.actions import list_aliases

    rows = list_aliases(ctx.case)
    return {"text": f"{len(rows)} alias(es) with origins", "data": rows}


async def _h_read(ctx: Context) -> dict:
    wf = _workflow(ctx)
    await wf.execute_direct(
        "read_source",
        {"url": ctx.args["url"]},
        purpose=f"read {ctx.args['url'][:80]} (analyst request)",
        origin="user",
    )
    source = next(
        (s for s in ctx.case.sources if s.get("requested_url") == ctx.args["url"]
         or s.get("url") == ctx.args["url"]),
        None,
    )
    if source and source.get("outcome") != "found":
        return {"text": f"source is {source.get('outcome')} ({source.get('error', '')})", "status": "unavailable"}
    return {
        "text": f"read {ctx.args['url'][:80]}; evidence and follow-up leads recorded",
        "data": source,
    }


async def _h_follow(ctx: Context) -> dict:
    from snoop.actions import follow

    message = await follow(ctx.case, ctx.args["ref"], ctx.bus, depth=int(ctx.args.get("depth") or 1))
    return {"text": message}


async def _h_document(ctx: Context) -> dict:
    wf = _workflow(ctx)
    await wf.execute_direct(
        "read_document", {"url": ctx.args["url"]}, purpose=f"read document {ctx.args['url'][:80]}", origin="user"
    )
    return {"text": f"document processed: {ctx.args['url'][:80]}"}


async def _h_archive(ctx: Context) -> dict:
    wf = _workflow(ctx)
    await wf.execute_direct(
        "archive_lookup",
        {"url": ctx.args["target"]},
        purpose=f"archive history for {ctx.args['target'][:60]}",
        origin="user",
    )
    return {"text": f"archive history recorded for {ctx.args['target'][:60]}"}


async def _h_domain(ctx: Context) -> dict:
    wf = _workflow(ctx)
    await wf.execute_direct(
        "domain_lookup", {"domain": ctx.args["domain"]}, purpose=f"public records for {ctx.args['domain']}", origin="user"
    )
    return {"text": f"domain records recorded for {ctx.args['domain']}"}


async def _h_image(ctx: Context) -> dict:
    wf = _workflow(ctx)
    await wf.execute_direct(
        "image_clues",
        {"url": ctx.args["url"], "reverse": bool(ctx.args.get("reverse"))},
        purpose=f"image clues for {ctx.args['url'][:60]}"
        + (" (reverse image search explicitly requested)" if ctx.args.get("reverse") else ""),
        origin="user",
    )
    return {"text": f"image processed: {ctx.args['url'][:80]}"}


async def _h_leads(ctx: Context) -> dict:
    status = ctx.args.get("status")
    rows = [
        {
            "id": l["id"],
            "type": l["type"],
            "purpose": l["purpose"],
            "expected": l.get("expected", ""),
            "status": l.get("status"),
            "score": round(float(l.get("score", 0)), 1),
            "reason": l.get("reason", ""),
            "origin": l.get("origin"),
        }
        for l in sorted(ctx.case.leads, key=lambda x: -float(x.get("score", 0)))
        if not status or l.get("status") == status
    ]
    from snoop.leads import LeadQueue

    text = f"{len(rows)} lead(s)" + (f" with status {status}" if status else "") + f"; {LeadQueue(ctx.case).stats()}"
    return {"text": text, "data": rows[:60]}


async def _h_queries(ctx: Context) -> dict:
    rows = [
        {
            "id": q.get("id"),
            "engine": q.get("engine"),
            "provider": q.get("provider"),
            "query": q.get("query"),
            "outcome": q.get("outcome"),
            "results": len(q.get("results", [])),
            "via": q.get("via"),
            "retrieved_at": q.get("retrieved_at"),
        }
        for q in ctx.case.queries
    ]
    return {"text": f"{len(rows)} executed quer{'y' if len(rows) == 1 else 'ies'}", "data": rows}


async def _h_sources(ctx: Context) -> dict:
    if ctx.args.get("id"):
        source = next((s for s in ctx.case.sources if s.get("id") == ctx.args["id"]), None)
        if not source:
            raise CommandError(f"unknown source {ctx.args['id']!r}")
        return {"text": source.get("title") or source.get("url"), "data": source}
    rows = [
        {
            "id": s.get("id"),
            "url": s.get("url"),
            "title": s.get("title"),
            "outcome": s.get("outcome"),
            "via": s.get("via"),
            "content_type": s.get("content_type"),
            "retrieved_at": s.get("retrieved_at"),
        }
        for s in ctx.case.sources
    ]
    return {"text": f"{len(rows)} source(s) collected", "data": rows}


async def _h_evidence(ctx: Context) -> dict:
    from snoop.actions import show_evidence

    return {"text": f"evidence for {ctx.args['ref']}", "data": show_evidence(ctx.case, ctx.args["ref"])}


async def _h_compare(ctx: Context) -> dict:
    from snoop.actions import compare

    return {"text": "comparison", "data": compare(ctx.case, ctx.args["left"], ctx.args["right"])}


async def _h_verify(ctx: Context) -> dict:
    from snoop.actions import verify

    message = await verify(ctx.case, ctx.args["ref"], ctx.bus)
    return {"text": message}


async def _h_pick(ctx: Context) -> dict:
    from snoop import session as sess

    return {"text": await sess.pick(ctx.case, ctx.args["label"])}


async def _h_merge(ctx: Context) -> dict:
    from snoop import session as sess

    return {"text": await sess.merge(ctx.case, ctx.args["a"], ctx.args["b"])}


async def _h_split(ctx: Context) -> dict:
    from snoop import session as sess

    return {"text": await sess.split_out(ctx.case, ctx.args["label"], ctx.args["ref"])}


async def _h_keep(ctx: Context) -> dict:
    from snoop import session as sess

    return {"text": await sess.account_decision(ctx.case, ctx.args["ref"], "keep")}


async def _h_discard(ctx: Context) -> dict:
    from snoop import session as sess

    return {"text": await sess.account_decision(ctx.case, ctx.args["ref"], "discard")}


async def _h_undo(ctx: Context) -> dict:
    from snoop import session as sess

    return {"text": await sess.undo(ctx.case)}


async def _h_graph(ctx: Context) -> dict:
    from snoop.actions import build_graph

    graph = build_graph(ctx.case)
    return {
        "text": f"{len(graph['nodes'])} node(s), {len(graph['edges'])} source-linked edge(s)",
        "data": graph,
    }


async def _h_timeline(ctx: Context) -> dict:
    from snoop.actions import timeline

    events = timeline(ctx.case, ctx.args.get("label") or "")
    return {"text": f"{len(events)} dated event(s)", "data": events}


async def _h_diff(ctx: Context) -> dict:
    from snoop.actions import diff_cases

    before, after = Dossier.load(ctx.args["before"]), Dossier.load(ctx.args["after"])
    if not before or not after:
        raise CommandError("both case IDs must exist")
    return {"text": "case diff", "data": diff_cases(before, after)}


async def _h_ask(ctx: Context) -> dict:
    from snoop import session as sess

    answer = await sess.ask(ctx.case, ctx.args["question"])
    return {"text": answer}


async def _h_questions(ctx: Context) -> dict:
    from snoop import interview

    question = interview.pending(ctx.case) or interview.next_question(ctx.case)
    if question and not interview.pending(ctx.case):
        interview.set_pending(ctx.case, question)
        ctx.case.workflow.update({"status": "needs_input", "stop_reason": f"needs input: {question['text']}"})
        ctx.case.save()
    if not question:
        return {"text": "no clarification is needed right now", "data": {"question": None}, "case": ctx.case}
    await ctx.bus.emit("question", question=question)
    return {"text": question["text"], "data": {"question": question}, "case": ctx.case}


async def _h_answer(ctx: Context) -> dict:
    from snoop import interview

    agent_waiting = (ctx.case.workflow.get("agent") or {}).get("status") == "needs_input"
    result = await interview.apply_answer(ctx.case, ctx.args["text"], ctx.bus)
    if agent_waiting and not interview.pending(ctx.case):
        # The agent asked; its answer resumes the same agent run.
        continued = await _h_agent(Context(ctx.case, ctx.bus, {"goal": (ctx.case.workflow.get("agent") or {}).get("goal", "")}, ctx.runtime))
        result["text"] += "; " + continued["text"]
    elif (ctx.case.workflow.get("guided") or result.get("timed_out")) and not interview.pending(ctx.case):
        # An unanswered question was skipped by the timer: keep investigating.
        continued = await _h_run(Context(ctx.case, ctx.bus, {}, ctx.runtime))
        result["text"] += "; " + continued["text"]
    return {"text": result["text"], "data": result, "case": ctx.case}


async def _h_agent(ctx: Context) -> dict:
    from snoop import interview

    goal = (ctx.args.get("goal") or "").strip()
    steps = ctx.args.get("steps")
    try:
        steps = int(steps) if steps else None
    except ValueError as exc:
        raise CommandError("agent: --steps must be a number") from exc
    if interview.pending(ctx.case):
        question = interview.pending(ctx.case)
        return {"text": f"answer the saved question first: {question['text']}", "data": {"question": question},
                "case": ctx.case}
    mode = config.ai_provider() or "planner autopilot (no AI key configured)"
    if ctx.runtime == "web":
        from snoop import jobs

        job = jobs.start_agent_job(ctx.case, goal=goal, steps=steps)
        return {"text": f"investigator agent running ({mode}); follow its reasoning in the feed",
                "data": {"job": job.status()}, "case": ctx.case}
    from snoop.agent import run_agent

    result = await run_agent(ctx.case, ctx.bus, goal=goal, steps=steps)
    text = f"agent {result['status']} after {result['steps']} step(s) ({mode}): {result['reason']}"
    if result.get("summary"):
        text += f"\n  summary ({'AI inference' if config.ai_provider() else 'planner'}): {result['summary']}"
    question = interview.pending(ctx.case)
    if question:
        text += f"\n  question: {question['text']}"
    return {"text": text, "data": result, "case": ctx.case}


async def _h_trace(ctx: Context) -> dict:
    from snoop.connect import render_trace, trace

    try:
        result = trace(ctx.case, ctx.args["ref"])
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    return {"text": render_trace(result), "data": result}


async def _h_profile(ctx: Context) -> dict:
    from snoop import profile

    note = ""
    if ctx.args.get("ai"):
        note = (await profile.ai_extract(ctx.case, ctx.bus))["note"]
    data = profile.build(ctx.case)
    text = profile.render(data) + (f"\n{note}" if note else "")
    return {"text": text, "data": data, "case": ctx.case}


async def _h_fact(ctx: Context) -> dict:
    from snoop import profile

    verdict = {"confirm": "confirmed", "confirmed": "confirmed", "yes": "confirmed", "true": "confirmed",
               "reject": "rejected", "rejected": "rejected", "wrong": "rejected", "no": "rejected", "false": "rejected",
               "reset": "unreviewed", "undo": "unreviewed"}.get(str(ctx.args["verdict"]).casefold())
    if not verdict:
        raise CommandError("fact: verdict must be confirm, reject or reset")
    try:
        text = await profile.review(ctx.case, ctx.args["fact_id"], verdict, ctx.bus, ctx.args.get("note") or "")
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    return {"text": text, "case": ctx.case}


async def _h_connections(ctx: Context) -> dict:
    from snoop.connect import connections

    rows = connections(ctx.case)
    text = f"{len(rows)} explainable link(s)" + (
        f"; top ({rows[0]['strength']}): {rows[0]['detail']}" if rows
        else " — none yet (links appear as sources and accounts are read)"
    )
    return {"text": text, "data": rows}


async def _h_briefing(ctx: Context) -> dict:
    from snoop.briefing import build_briefing, render_briefing

    data = build_briefing(ctx.case)
    return {"text": render_briefing(data), "data": data}


async def _h_report(ctx: Context) -> dict:
    from snoop.actions import case_report

    return {"text": "case report", "data": case_report(ctx.case)}


async def _h_export(ctx: Context) -> dict:
    from snoop.actions import export_case

    result = export_case(ctx.case, bool(ctx.args.get("redact")) or config.presenter)
    return {"text": f"exported {'redacted' if result['redacted'] else 'full'} report", "data": result}


async def _h_providers(_ctx: Context) -> dict:
    from snoop.actions import providers_status

    data = providers_status()
    engines = ", ".join(
        f"{e['label']} ({'ready' if e['ready'] else e['reason']})" for e in data["search"]["engines"]
    )
    return {"text": f"search: {engines}", "data": data}


async def _h_doctor(_ctx: Context) -> dict:
    from snoop.actions import doctor

    return {"text": "diagnostics", "data": doctor()}


async def _h_anchor(ctx: Context) -> dict:
    from snoop.actions import anchor
    from snoop.core import UnsafeUrl

    try:
        message = await anchor(ctx.case, ctx.args["url"], ctx.bus, discovery_source="user-anchor")
    except (ValueError, UnsafeUrl) as exc:
        raise CommandError(f"anchor rejected: {exc}") from exc
    return {"text": message}


async def _h_context(ctx: Context) -> dict:
    from snoop import session as sess

    return {"text": await sess.add_context(ctx.case, ctx.args["fact"], ctx.bus)}


async def _h_deepen(ctx: Context) -> dict:
    from snoop import session as sess

    return {"text": await sess.deepen(ctx.case, ctx.args["ref"], ctx.bus)}


HANDLERS = {
    "investigate": _h_investigate,
    "plan": _h_plan,
    "run": _h_run,
    "step": _h_step,
    "pause": _h_pause,
    "continue": _h_continue,
    "stop": _h_stop,
    "cases": _h_cases,
    "resume": _h_resume,
    "case": _h_case,
    "search": _h_search,
    "manual-search": _h_manual_search,
    "import": _h_import,
    "accounts": _h_accounts,
    "aliases": _h_aliases,
    "anchor": _h_anchor,
    "context": _h_context,
    "deepen": _h_deepen,
    "read": _h_read,
    "follow": _h_follow,
    "document": _h_document,
    "archive": _h_archive,
    "domain": _h_domain,
    "image": _h_image,
    "leads": _h_leads,
    "queries": _h_queries,
    "sources": _h_sources,
    "evidence": _h_evidence,
    "compare": _h_compare,
    "verify": _h_verify,
    "pick": _h_pick,
    "merge": _h_merge,
    "split": _h_split,
    "keep": _h_keep,
    "discard": _h_discard,
    "undo": _h_undo,
    "graph": _h_graph,
    "timeline": _h_timeline,
    "diff": _h_diff,
    "ask": _h_ask,
    "questions": _h_questions,
    "briefing": _h_briefing,
    "answer": _h_answer,
    "agent": _h_agent,
    "trace": _h_trace,
    "connections": _h_connections,
    "profile": _h_profile,
    "fact": _h_fact,
    "report": _h_report,
    "export": _h_export,
    "providers": _h_providers,
    "doctor": _h_doctor,
}


async def execute(text: str, dossier: Dossier | None, bus: Bus | None = None, *, runtime: str = "cli") -> dict:
    """Parse and run one command line (quoted arguments supported)."""
    from snoop.interview import pending

    first = (text.strip().split() or [""])[0].casefold()
    if dossier and pending(dossier) and first not in COMMANDS:
        return await execute_tokens(["answer", text], dossier, bus, runtime=runtime)
    if first == "answer":
        # Answers are natural language (apostrophes, pasted page text), not
        # shell syntax: keep them raw; accept one JSON/quoted wrapper.
        rest = text.strip()[len("answer"):].strip()
        if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in "\"'":
            import json

            try:
                rest = json.loads(rest) if rest[0] == '"' else rest[1:-1]
            except ValueError:
                rest = rest[1:-1]
        return await execute_tokens(["answer", str(rest)], dossier, bus, runtime=runtime)
    try:
        tokens = shlex.split(text)
    except ValueError as exc:
        raise CommandError(f"could not parse the command ({exc}); check quotes") from exc
    return await execute_tokens(tokens, dossier, bus, runtime=runtime)


async def execute_tokens(
    tokens: list[str], dossier: Dossier | None, bus: Bus | None = None, *, runtime: str = "cli"
) -> dict:
    """Run one command from pre-split tokens (the CLI passes argv directly so
    shell quoting survives; nothing the user typed is silently discarded)."""
    if not tokens:
        raise CommandError("empty command")
    name = tokens[0].casefold()
    aliases = {"list-cases": "cases", "use": "resume", "import-search": "manual-search", "status": "case"}
    name = aliases.get(name, name)
    bus = bus or Bus()
    command_spec = COMMANDS.get(name)
    if not command_spec:
        # The web composer and CLI share this fallback: ordinary language is a
        # reply when (and only when) the case has one pending question.
        if dossier is not None:
            from snoop import interview

            if interview.pending(dossier):
                result = await _h_answer(Context(dossier, bus, {"text": " ".join(tokens)}, runtime))
                await bus.emit("reply", text=result.get("text", ""), command="answer")
                return result
        raise CommandError(f"unknown command {tokens[0]!r}; 'help' lists everything")
    args = command_spec.parse(tokens[1:])
    if command_spec.needs_case and dossier is None:
        raise CommandError(f"{name} needs an active case — start one with: investigate NAME")
    handler = HANDLERS[name]
    ctx = Context(dossier, bus, args, runtime)
    result = await handler(ctx)
    await bus.emit(
        "reply",
        text=result.get("text", ""),
        command=name,
    )
    return result


def help_rows(family: str | None = None) -> list[dict]:
    rows = []
    for spec in COMMANDS.values():
        if family and spec.family != family:
            continue
        rows.append(
            {
                "name": spec.name,
                "family": spec.family,
                "usage": spec.usage,
                "help": spec.help,
                "needs_case": spec.needs_case,
                "capability": spec.capability,
            }
        )
    return rows


def families() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for spec in COMMANDS.values():
        out.setdefault(spec.family, []).append(spec.name)
    return out
