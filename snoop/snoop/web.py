"""Web workspace: one engine, the same registry, reconnectable live jobs."""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from pathlib import Path

from aiohttp import web

from snoop.config import config
from snoop.core import Bus
from snoop.pipeline import Dossier

_HTML = Path(__file__).parent / "data" / "index.html"
_CASE_TOKENS: dict[str, str] = {}


def _case_token(case_id: str) -> str:
    token = secrets.token_urlsafe(18)
    _CASE_TOKENS[token] = case_id
    if len(_CASE_TOKENS) > 256:
        del _CASE_TOKENS[next(iter(_CASE_TOKENS))]
    return token


def _case_id(value: str) -> str:
    return _CASE_TOKENS.get(value, value)


async def index(_req: web.Request) -> web.Response:
    return web.Response(
        text=_HTML.read_text("utf-8"),
        content_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


async def api_cases(req: web.Request) -> web.Response:
    out = []
    for row in Dossier.list_cases()[:60]:
        shown = dict(row)
        if config.presenter or req.query.get("redact") == "1":
            shown = {
                "id": _case_token(row["id"]),
                "target": f"CASE {row['id'][:8]}",
                "kind": row.get("kind", ""),
                "updated": row.get("updated", ""),
                "mode": row.get("mode", ""),
                "accounts": row.get("accounts", 0),
                "sources": row.get("sources", 0),
                "queries": row.get("queries", 0),
                "workflow_status": row.get("workflow_status", ""),
            }
        out.append(shown)
    return web.json_response(out)


async def api_case(req: web.Request) -> web.Response:
    d = Dossier.load(_case_id(req.match_info["id"]))
    if not d:
        return web.json_response({"error": "not found"}, status=404)
    from dataclasses import asdict

    from snoop.interview import subject_status

    data = asdict(d)
    # asdict() skips properties; the workspace needs hits + excluded together.
    data["all_accounts"] = d.all_accounts
    # ``subject`` is persisted input/answers; this computed companion carries
    # the evidence-backed verification state used by both interfaces.
    data["subject_status"] = subject_status(d)
    from snoop.briefing import build_briefing

    data["briefing"] = build_briefing(d)
    from snoop.connect import connections

    data["connections"] = connections(d)[:60]
    from snoop.profile import build as build_profile

    data["profile_view"] = build_profile(d)
    data["agent_ready"] = {"ai": config.ai_provider() or "", "mode": "ai" if config.ai_provider() else "autopilot"}
    data["question_timeout"] = config.question_timeout
    if config.presenter or req.query.get("redact") == "1":
        from snoop.privacy import case_identifiers, mask_obj

        data = mask_obj(data, case_identifiers(d), force=True)
    return web.json_response(data)


async def api_cards(req: web.Request) -> web.Response:
    from snoop.session import build_cards

    d = Dossier.load(_case_id(req.match_info["id"]))
    if not d:
        return web.json_response({"error": "not found"}, status=404)
    cards = build_cards(d)
    if config.presenter or req.query.get("redact") == "1":
        from snoop.privacy import case_identifiers, mask_obj

        cards = mask_obj(cards, case_identifiers(d), force=True)
    return web.json_response(cards)


async def api_trace(req: web.Request) -> web.Response:
    from snoop.connect import trace

    d = Dossier.load(_case_id(req.match_info["id"]))
    if not d:
        return web.json_response({"error": "not found"}, status=404)
    try:
        result = trace(d, req.query.get("ref", ""))
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=404)
    if config.presenter or req.query.get("redact") == "1":
        from snoop.privacy import case_identifiers, mask_obj

        result = mask_obj(result, case_identifiers(d), force=True)
    return web.json_response(result)


async def api_commands(_req: web.Request) -> web.Response:
    from snoop.registry import help_rows

    return web.json_response(help_rows())


async def api_providers(_req: web.Request) -> web.Response:
    from snoop.actions import providers_status

    return web.json_response(providers_status())


async def api_plan(req: web.Request) -> web.Response:
    from snoop import jobs
    from snoop.workflow import Workflow

    d = Dossier.load(_case_id(req.match_info["id"]))
    if not d:
        return web.json_response({"error": "not found"}, status=404)
    wf = Workflow(d, Bus())
    job = jobs.get_job(d.id)
    return web.json_response(
        {
            "workflow": wf.status(),
            "job": job.status() if job else None,
            "leads": [
                {
                    "id": l["id"],
                    "type": l["type"],
                    "purpose": l["purpose"],
                    "expected": l.get("expected", ""),
                    "status": l.get("status"),
                    "score": round(float(l.get("score", 0)), 1),
                    "origin": l.get("origin"),
                    "reason": l.get("reason", ""),
                }
                for l in sorted(d.leads, key=lambda x: -float(x.get("score", 0)))
            ][:80],
        }
    )


async def api_control(req: web.Request) -> web.Response:
    from snoop import jobs

    case_id = _case_id(req.match_info["id"])
    body = await req.json() if req.can_read_body else {}
    action = str(body.get("action", ""))
    if action not in {"pause", "continue", "resume", "stop", "cancel"}:
        return web.json_response({"error": "invalid action"}, status=400)
    message = await jobs.control(case_id, action)
    return web.json_response({"message": message})


async def api_job_events(req: web.Request) -> web.StreamResponse:
    """Reconnectable live event stream for a case job (?since=SEQ replays)."""
    from snoop import jobs

    case_id = _case_id(req.match_info["id"])
    since = int(req.query.get("since") or 0)
    queue = jobs.subscribe(case_id, since)
    if queue is None:
        return web.json_response({"error": "no job for this case"}, status=404)
    resp = web.StreamResponse(
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
    await resp.prepare(req)
    try:
        while True:
            try:
                row = await asyncio.wait_for(queue.get(), timeout=20)
            except TimeoutError:
                job = jobs.get_job(case_id)
                current = (
                    job.dossier.workflow.get("current_action", {}) if job else {}
                )
                row = {
                    "seq": job.seq if job else since,
                    "kind": "heartbeat",
                    "payload": {
                        "waiting_s": 20,
                        "purpose": current.get("purpose", ""),
                    },
                }
                await resp.write(f"data: {json.dumps(row, default=str)}\n\n".encode())
                continue
            await resp.write(f"data: {json.dumps(row, default=str)}\n\n".encode())
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    finally:
        jobs.unsubscribe(case_id, queue)
    return resp


async def api_investigate(req: web.Request) -> web.StreamResponse:
    """Start a complete investigation on a new subject (SSE)."""
    if req.method == "POST":
        body = await req.json()
        target = (body.get("target") or "").strip()
        kind = body.get("kind") or None
        mode = body.get("mode") or "full"
        preset = body.get("preset") or None
        exact_name = body.get("exact_name") is True
        guided = body.get("guided") is True
        context = [c for c in body.get("context", []) if str(c).strip()]
    else:
        target = (req.query.get("target") or "").strip()
        kind = req.query.get("kind") or None
        mode = req.query.get("mode") or "full"
        preset = req.query.get("preset") or None
        exact_name = req.query.get("exact_name") == "1"
        guided = req.query.get("guided") == "1"
        context = [c for c in req.query.getall("context", []) if c.strip()]
    if not target:
        return await _sse_error("no target given")

    async def drive(bus: Bus) -> None:
        from snoop.pipeline import investigate

        await investigate(target, bus, kind=kind, context=context or None, mode=mode, preset=preset,
                          exact_name=exact_name, guided=guided)

    return await _sse(req, drive, redact=req.query.get("redact") == "1")


async def api_command(req: web.Request) -> web.StreamResponse:
    """Run any registry command against a case; live events stream back.

    Long-running commands (`run`) go through the reconnectable job runner, so
    a page reload reattaches to the same investigation through
    /api/case/{id}/events.
    """
    if req.method == "POST":
        body = await req.json()
        text = (body.get("text") or "").strip()
        case_id = _case_id(str(body.get("case_id") or "").strip())
    else:
        text = (req.query.get("text") or "").strip()
        case_id = _case_id((req.query.get("id") or "").strip())
    if not text:
        return await _sse_error("no command given")

    from snoop import registry

    dossier = Dossier.load(case_id) if case_id else None

    async def drive(bus: Bus) -> None:
        nonlocal dossier
        result = await registry.execute(text, dossier, bus, runtime="web")
        new_case = result.get("case")
        if new_case is not None and new_case.id != case_id:
            await bus.emit("session", id=new_case.id)
        elif dossier:
            await bus.emit("session", id=dossier.id)

    return await _sse(req, drive, redact=req.query.get("redact") == "1")


async def _sse_error(detail: str) -> web.Response:
    return web.json_response({"error": detail}, status=400)


async def _sse(req: web.Request, drive, *, redact: bool = False) -> web.StreamResponse:
    """Run `drive(bus)` and forward every event to the client as it happens."""
    resp = web.StreamResponse(
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
    await resp.prepare(req)
    queue: asyncio.Queue = asyncio.Queue()
    request_redactions = []
    if redact:
        request_redactions.extend(req.query.getall("redact_value", []))
    bus = Bus(request_redactions, mask_events=False)

    def forward(ev) -> None:
        payload = ev.payload
        if redact or config.presenter:
            from snoop.privacy import mask_obj

            raw_id = payload.get("id") if ev.kind in {"done", "session"} else None
            payload = mask_obj(payload, bus.redact_values, force=True)
            if raw_id:
                payload["id"] = _case_token(str(raw_id))
        queue.put_nowait({"kind": ev.kind, "payload": payload})

    bus.on(forward)
    stream_started = time.monotonic()
    last_event = stream_started

    async def run() -> None:
        try:
            await drive(bus)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # pragma: no cover
            queue.put_nowait({"kind": "error", "payload": {"detail": f"{type(e).__name__}: {e}"}})
        finally:
            queue.put_nowait(None)

    task = asyncio.create_task(run())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=10)
            except TimeoutError:
                now = time.monotonic()
                item = {
                    "kind": "heartbeat",
                    "payload": {
                        "elapsed_s": round(now - stream_started),
                        "waiting_s": round(now - last_event),
                    },
                }
            if item is None:
                break
            await resp.write(f"data: {json.dumps(item, default=str)}\n\n".encode())
            if item.get("kind") != "heartbeat":
                last_event = time.monotonic()
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
    return resp


def build_app() -> web.Application:
    # Background jobs cannot survive a process restart. Repair their saved
    # state before exposing cases so the UI offers Continue instead of showing
    # a permanent activity indicator.
    from snoop import jobs

    jobs.recover_interrupted_cases()
    app = web.Application()
    app.add_routes(
        [
            web.get("/", index),
            web.route("*", "/api/investigate", api_investigate),
            web.route("*", "/api/talk", api_command),  # legacy alias
            web.route("*", "/api/command", api_command),
            web.get("/api/cases", api_cases),
            web.get("/api/case/{id}", api_case),
            web.get("/api/dossier/{id}", api_case),  # legacy alias
            web.get("/api/cards/{id}", api_cards),
            web.get("/api/case/{id}/trace", api_trace),
            web.get("/api/commands", api_commands),
            web.get("/api/providers", api_providers),
            web.get("/api/plan/{id}", api_plan),
            web.post("/api/case/{id}/control", api_control),
            web.get("/api/case/{id}/events", api_job_events),
        ]
    )
    return app


def serve(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="snoop web")
    p.add_argument("--host", default=config.web_host)
    p.add_argument("--port", type=int, default=config.web_port)
    a = p.parse_args(argv)
    print(f"  SNOOP web workspace  ->  http://{a.host}:{a.port}")
    from snoop import search

    if not search.any_engine_ready():
        print(
            "  web search unavailable — set SERPAPI_KEY (Google via SerpAPI) or "
            "BRAVE_SEARCH_API_KEY to enable discovery"
        )
    if not config.ai_provider():
        print("  (no AI key - identity fusion will be heuristic only)")
    try:
        web.run_app(build_app(), host=a.host, port=a.port, print=None)
    except KeyboardInterrupt:
        pass
    return 0
