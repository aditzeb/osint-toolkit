"""The investigator agent: a bounded, tool-using reasoning loop over one case.

Each step the model sees a compact, factual view of the saved case, states its
reasoning, and picks ONE typed tool. The engine validates the choice against
an allowlist and the case itself, runs it through the same workflow handlers
the planner uses (same budgets, same URL policy, same provenance), and feeds
back a factual observation. When a page cannot be read, the agent can stop and
ask the analyst to look at it — that answer comes back through the normal
interview path as labelled manual assistance.

Without an AI provider the same loop runs as a deterministic "planner
autopilot": it narrates the planner's own ranked reasoning and is labelled so.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from urllib.parse import urlsplit

from snoop import search
from snoop.config import config
from snoop.core import Bus, Http
from snoop.interview import BLOCKED_OUTCOMES
from snoop.model import canonical_url, utcnow

AGENT_RULES = ""


def untrusted(text: str) -> str:
    return text


STEP_LIMITS = {"quick": 6, "standard": 10, "deep": 16}

TOOLS: dict[str, dict] = {
    "search": {"lead": "web_search", "args": ["query", "engine?"],
               "help": "web search (Google via SerpAPI / Brave Search); quote exact phrases"},
    "read_page": {"lead": "read_source", "args": ["url"],
                  "help": "open and read a page already seen in results, sources or links"},
    "read_document": {"lead": "read_document", "args": ["url"], "help": "extract a PDF/document already seen"},
    "check_profile": {"lead": "check_account", "args": ["url"],
                      "help": "validate a public profile URL already seen in the case"},
    "check_username": {"lead": "probe_handles", "args": ["handle"],
                       "help": "bounded check of a handle that appears in the case across public platforms"},
    "follow_links": {"lead": "expand_links", "args": ["ref"], "help": "follow links an account publishes (ref like H02)"},
    "archive": {"lead": "archive_lookup", "args": ["url"], "help": "Wayback/Common Crawl history of a known URL or domain"},
    "domain": {"lead": "domain_lookup", "args": ["domain"], "help": "RDAP/DNS/certificate clues for a domain seen in the case"},
    "run_planned": {"lead": "", "args": ["count?"], "help": "execute the planner's top queued actions (1-3)"},
    "inspect": {"lead": "", "args": ["ref"], "help": "read-only: evidence behind an account/source/evidence id"},
    "compare": {"lead": "", "args": ["a", "b"], "help": "read-only: compare two accounts"},
    "connections": {"lead": "", "args": [], "help": "read-only: explicit links, shared handles/sites between records"},
    "note": {"lead": "", "args": ["text", "evidence_ids"],
             "help": "record a hypothesis; must cite existing evidence ids; stored as AI inference"},
    "ask_user": {"lead": "", "args": ["question", "why", "url?"],
                 "help": "stop and ask the analyst (e.g. open a page you cannot read, or a distinguishing fact)"},
    "finish": {"lead": "", "args": ["summary", "evidence_ids"], "help": "end with a cited summary"},
}

SYSTEM = f"""You are SNOOP's investigator agent for consented public-footprint research.
You work one step at a time with typed tools. Rules:
{AGENT_RULES}
- Prefer reading a promising page over another search; prefer handles found in sources
  over guessed usernames. Do not repeat a tool call that already ran.
- If an important page is blocked (login, CAPTCHA, rate limit), use ask_user so the
  analyst can open it and paste what it shows.
- Finish when the useful frontier is exhausted or budgets are low.
Return ONLY JSON: {{"thought": "<=70 words: what you know, the uncertainty, why this tool",
"tool": "<tool name>", "args": {{...}}}}"""


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:10]


def _host(url: str) -> str:
    return (urlsplit(url or "").hostname or "").casefold().removeprefix("www.")


class AgentError(Exception):
    pass


class Agent:
    def __init__(self, dossier, bus: Bus | None = None, *, max_steps: int | None = None, goal: str = ""):
        from snoop.workflow import Workflow

        self.dossier = dossier
        self.bus = bus or Bus()
        self.wf = Workflow(dossier, self.bus)
        self.max_steps = max(1, min(int(max_steps or STEP_LIMITS[self.wf.preset]), 30))
        self.goal = (goal or "").strip()[:500]
        self.mode = config.ai_provider() or "deterministic"
        self.steps: list[dict] = []
        self.summary = ""

    # ----------------------------------------------------------------- control

    def cancel(self) -> None:
        self.wf.cancel()

    def pause(self) -> None:
        self.wf.pause()

    # --------------------------------------------------------------- the loop

    async def run(self) -> dict:
        from snoop import interview

        state = self.dossier.workflow.setdefault("agent", {})
        if interview.pending(self.dossier):
            return self._result("needs_input", "waiting for the saved question to be answered")
        state.update(status="running", mode=self.mode, goal=self.goal, started_at=utcnow())
        state.setdefault("hypotheses", [])
        self.wf._set_status("running", "")
        self.dossier.save()
        await self.bus.emit(
            "stage",
            name=f"investigator agent ({'AI: ' + self.mode if self.mode != 'deterministic' else 'planner autopilot, no AI'})",
        )
        if not self.dossier.leads and not self.dossier.queries:
            await self.wf.start()
        status, reason = "done", "agent finished"
        invalid = 0
        runs = state.get("runs") or []
        offset = len(runs[-1].get("steps", [])) if runs and runs[-1].get("open") else 0
        async with Http(concurrency=config.concurrency) as http:
            self.wf.http = http
            try:
                for index in range(1, self.max_steps + 1):
                    number = offset + index
                    if self.wf._stopped():
                        status, reason = "cancelled", "cancelled by the analyst; completed work is saved"
                        break
                    if self.wf._pause.is_set():
                        status, reason = "paused", "paused by the analyst"
                        break
                    decision = await self._decide(number)
                    if decision is None:
                        status, reason = "done", "nothing useful left for the agent to do"
                        break
                    try:
                        tool, args = self._validate(decision)
                    except AgentError as exc:
                        invalid += 1
                        self._log(number, decision, f"rejected by the engine: {exc}", valid=False)
                        await self.bus.emit("agent_observation", step=number, text=f"rejected: {exc}", ok=False)
                        if invalid >= 3:
                            status, reason = "done", "agent stopped after repeated invalid tool requests"
                            break
                        continue
                    invalid = 0
                    await self.bus.emit("agent_thought", step=number, thought=decision.get("thought", ""), mode=self.mode)
                    await self.bus.emit("agent_tool", step=number, tool=tool, args=args)
                    observation = await self._run_tool(tool, args)
                    self._log(number, {**decision, "tool": tool, "args": args}, observation)
                    await self.bus.emit("agent_observation", step=number, text=observation[:600], ok=True)
                    self.dossier.save()
                    if tool == "finish":
                        status, reason = "done", "agent finished with a cited summary"
                        break
                    if tool == "ask_user" or interview.pending(self.dossier):
                        status, reason = "needs_input", "agent is waiting for the analyst"
                        break
                else:
                    status, reason = "done", f"agent step limit reached ({self.max_steps})"
            except asyncio.CancelledError:
                self._persist("cancelled", "cancelled by the analyst; completed work is saved")
                raise
            finally:
                self.wf.http = None
        await self.wf._refresh_analysis(use_model=False)
        if status == "done" and self.mode != "deterministic":
            from snoop.profile import ai_extract

            await ai_extract(self.dossier, self.bus)
        return self._result(status, reason)

    def _result(self, status: str, reason: str) -> dict:
        steps = len(self.steps)
        self._persist(status, reason)
        return {
            "status": status,
            "reason": reason,
            "steps": steps,
            "summary": self.summary,
            "mode": self.mode,
        }

    def _persist(self, status: str, reason: str) -> None:
        state = self.dossier.workflow.setdefault("agent", {})
        state.update(status=status, reason=reason, finished_at=utcnow(), mode=self.mode)
        if self.steps:
            runs = state.setdefault("runs", [])
            run = {
                "goal": self.goal,
                "mode": self.mode,
                "at": utcnow(),
                "status": status,
                "summary": self.summary,
                "steps": self.steps,
            }
            if runs and runs[-1].get("open"):
                runs[-1]["steps"] = runs[-1].get("steps", []) + self.steps
                runs[-1].update({k: v for k, v in run.items() if k != "steps"})
            else:
                runs.append(run)
            runs[-1]["open"] = status in {"needs_input", "paused"}
            state["runs"] = runs[-6:]
            self.steps = []
        workflow_status = {"cancelled": "cancelled", "paused": "paused", "needs_input": "needs_input"}.get(status, "done")
        self.wf._set_status(workflow_status, reason)
        self.dossier.save()

    def _log(self, number: int, decision: dict, observation: str, *, valid: bool = True) -> None:
        self.steps.append(
            {
                "step": number,
                "thought": str(decision.get("thought", ""))[:600],
                "tool": str(decision.get("tool", "")),
                "args": decision.get("args") if isinstance(decision.get("args"), dict) else {},
                "observation": observation[:900],
                "valid": valid,
                "at": utcnow(),
            }
        )

    # ------------------------------------------------------------ deciding

    async def _decide(self, number: int) -> dict | None:
        if self.mode == "deterministic":
            return self._autopilot()
        from snoop.analyst import _call, _loads

        prompt = self._prompt(number)
        try:
            raw = await _call(prompt, SYSTEM)
        except Exception as exc:  # boundary: provider failure falls back honestly
            await self.bus.emit("warning", detail=f"agent model unavailable ({type(exc).__name__}); using planner autopilot")
            self.mode = "deterministic"
            return self._autopilot()
        decision = _loads(raw)
        if not isinstance(decision, dict):
            return {"thought": "", "tool": "", "args": {}, "_raw": str(raw)[:200]}
        return decision

    def _autopilot(self) -> dict | None:
        """Deterministic policy: ask about a blocked exact-name page first,
        otherwise run the planner's best-ranked lead, then finish."""
        from snoop import interview

        question = interview.blocked_source_question(self.dossier)
        if question:
            return {
                "thought": "An exact-name page could not be opened automatically. The analyst may be able to "
                "read it, which could confirm or rule out this lead.",
                "tool": "ask_user",
                "args": {"question": question["text"], "why": question["why"], "url": question.get("source_url", "")},
                "_question": question,
            }
        lead = self.wf.queue.next()
        if lead is None:
            confirmed = [h.get("ref") for h in self.dossier.hits if h.get("verdict") in {"confirmed", "probable"}]
            evidence = [r["id"] for r in self.dossier.evidence_records if r.get("supports")][:6]
            return {
                "thought": "The planner has no open leads left, so further automated steps would repeat work.",
                "tool": "finish",
                "args": {
                    "summary": (
                        f"Planner frontier exhausted. {len(self.dossier.sources)} source(s), "
                        f"{len(self.dossier.all_accounts)} account(s); supported candidates: "
                        f"{', '.join(r for r in confirmed if r) or 'none yet'}."
                    ),
                    "evidence_ids": evidence,
                },
            }
        return {
            "thought": f"Next by priority ({float(lead.get('score', 0)):.1f}): {lead['purpose']}.",
            "tool": "run_planned",
            "args": {"count": 1},
        }

    def _prompt(self, number: int) -> str:
        d = self.dossier
        from snoop.interview import subject_status

        def can_pivot(_dossier, _account) -> bool:
            return True

        subject = subject_status(d)
        budgets = {
            k: f"{self.wf.spent.get(k, 0)}/{v}"
            for k, v in self.wf.budgets.items()
            if k in {"searches", "page_fetches", "account_probes"}
        }
        accounts = [
            {
                "ref": h.get("ref"),
                "platform": h.get("platform"),
                "url": h.get("canonical_url"),
                "name": h.get("display_name", ""),
                "verdict": h.get("verdict", ""),
                "status": "EXCLUDED" if not can_pivot(d, h) else "candidate",
            }
            for h in d.all_accounts[:24]
        ]
        sources = [
            {"id": s.get("id"), "title": (s.get("title") or "")[:90], "url": s.get("url"), "outcome": s.get("outcome"),
             "transcribed_by_analyst": bool((s.get("extra") or {}).get("transcribed"))}
            for s in d.sources[-18:]
        ]
        evidence = [
            {"id": r.get("id"), "claim": r.get("claim"), "excerpt": str(r.get("excerpt", ""))[:140],
             "source": r.get("source_url"), "kind": r.get("kind")}
            for r in d.evidence_records[-28:]
        ]
        results = []
        for query in d.queries[-4:]:
            for row in query.get("results", [])[:5]:
                results.append({"query": query.get("query"), "title": str(row.get("title", ""))[:90],
                                "url": row.get("url"), "snippet": str(row.get("snippet", ""))[:140]})
        from snoop.connect import connections

        payload = {
            "subject": subject,
            "context": d.context,
            "analyst_goal": self.goal,
            "budgets_used": budgets,
            "step": f"{number}/{self.max_steps}",
            "accounts": accounts,
            "sources": sources,
            "recent_search_results": results[:16],
            "evidence": evidence,
            "queued_planner_actions": [l["purpose"] for l in self.wf.queue.pending()[:6]],
            "connections": connections(d)[:8],
            "analyst_answers": [
                {"q": a.get("question", "")[:120], "a": str(a.get("value") or a.get("kind"))[:200]}
                for a in (d.interview or [])[-5:]
            ],
            "hypotheses_so_far": [h.get("text") for h in d.workflow.get("agent", {}).get("hypotheses", [])[-5:]],
            "steps_this_run": [
                {"tool": s["tool"], "args": s["args"], "observation": s["observation"][:350]}
                for s in self.steps[-8:]
            ],
        }
        tools = "\n".join(f"- {name}({', '.join(spec['args'])}): {spec['help']}" for name, spec in TOOLS.items())
        return (
            "TOOLS:\n" + tools + "\n\nCASE:\n" + untrusted(json.dumps(payload, default=str)[:24000])
            + "\nChoose the single most useful next tool."
        )

    # ----------------------------------------------------------- validation

    def _corpus(self) -> tuple[str, set[str], set[str]]:
        return ("", set(), set())

    def _validate(self, decision: dict) -> tuple[str, dict]:
        if not isinstance(decision, dict):
            raise AgentError("no valid tool decision")
        tool = str(decision.get("tool", "")).strip()
        spec = TOOLS.get(tool)
        if spec is None:
            raise AgentError(f"unknown tool: {tool!r}")
        raw_args = decision.get("args")
        raw_args = raw_args if isinstance(raw_args, dict) else {}
        allowed = {name.rstrip("?") for name in spec.get("args", [])}
        args = {k: v for k, v in raw_args.items() if k in allowed}
        for name in spec.get("args", []):
            if name.endswith("?"):
                continue
            if not args.get(name):
                raise AgentError(f"missing required arg {name!r} for {tool}")
        if "_question" in decision:
            args["_question"] = decision["_question"]
        return tool, args

    def _can_pivot(self, account: dict) -> bool:
        return True

    # ------------------------------------------------------------- execution

    async def _run_tool(self, tool: str, args: dict) -> str:
        spec = TOOLS[tool]
        if spec["lead"]:
            lead_args = {"url": args.get("url", "")}
            purpose = ""
            if tool == "search":
                lead_args = {"query": args["query"], "engine": args.get("engine") or ""}
                purpose = f'Agent search: {args["query"]}'
            elif tool == "check_username":
                lead_args = {"handles": [args["handle"]], "origin": "agent"}
                purpose = f"Agent check of the handle {args['handle']}"
            elif tool == "follow_links":
                lead_args = {"ref": args["ref"]}
                purpose = f"Agent follows links published by {args['ref']}"
            elif tool == "domain":
                lead_args = {"domain": args["domain"]}
                purpose = f"Agent domain clues for {args['domain']}"
            else:
                purpose = f"Agent {tool.replace('_', ' ')}: {args.get('url', '')[:80]}"
            parent = self._parent_for(lead_args.get("url", ""))
            await self.wf.execute_direct(
                spec["lead"], lead_args, purpose, "agent-selected action", origin="agent", parent=parent
            )
            lead = next((l for l in reversed(self.dossier.leads) if l.get("purpose") == purpose), None)
            return self._observe(tool, lead_args, lead)
        if tool == "run_planned":
            done = []
            for _ in range(int(args.get("count", 1))):
                lead = self.wf.queue.next()
                if lead is None:
                    break
                ran = await self.wf.step()
                if not ran:
                    break
                current = next((l for l in self.dossier.leads if l.get("id") == lead["id"]), lead)
                lead_args = current.get("args", {})
                target = lead_args.get("query") or lead_args.get("url") or lead_args.get("domain") or lead_args.get("ref") \
                    or ", ".join(lead_args.get("handles", []))
                args.setdefault("ran", []).append(f"{current['type']}: {target}")
                done.append(self._observe(current["type"], lead_args, current))
            return " | ".join(done) or "no queued planner actions were runnable"
        if tool == "inspect":
            return self._inspect(args["ref"])
        if tool == "compare":
            from snoop.actions import compare

            return json.dumps(compare(self.dossier, args["a"], args["b"]), default=str)[:900]
        if tool == "connections":
            from snoop.connect import connections

            rows = connections(self.dossier)[:10]
            return "; ".join(f"{r['a']}–{r['b']} {r['kind']} ({r['strength']}): {r['detail']}" for r in rows) or "no links between records yet"
        if tool == "note":
            state = self.dossier.workflow.setdefault("agent", {})
            state.setdefault("hypotheses", []).append(
                {"text": args["text"][:500], "evidence_ids": args["evidence_ids"], "at": utcnow(),
                 "label": "AI inference", "mode": self.mode}
            )
            state["hypotheses"] = state["hypotheses"][-20:]
            return f"hypothesis recorded as AI inference citing {', '.join(args['evidence_ids'])}"
        if tool == "finish":
            self.summary = args["summary"][:1200]
            state = self.dossier.workflow.setdefault("agent", {})
            state["summary"] = {"text": self.summary, "evidence_ids": args.get("evidence_ids", []),
                                "label": "AI inference" if self.mode != "deterministic" else "planner summary",
                                "at": utcnow()}
            return "summary recorded"
        if tool == "ask_user":
            return await self._ask(args)
        return "no-op"

    def _parent_for(self, url: str) -> str:
        """The lead that surfaced this URL, so `trace` can show the path."""
        if not url:
            return ""
        target = canonical_url(url)
        for query in self.dossier.queries:
            if any(canonical_url(str(r.get("url", ""))) == target for r in query.get("results", [])):
                for lead in self.dossier.leads:
                    if lead.get("type") == "web_search" and str(lead["args"].get("query", "")).casefold() == str(
                        query.get("query", "")
                    ).casefold():
                        return lead["id"]
        for lead in self.dossier.leads:
            if canonical_url(str((lead.get("args") or {}).get("url", ""))) == target:
                continue
            for source_id in (lead.get("produced") or {}).get("sources", []):
                source = next((s for s in self.dossier.sources if s.get("id") == source_id), None)
                if source and target in str(source.get("excerpt", "")):
                    return lead["id"]
        return ""

    def _observe(self, tool: str, args: dict, lead: dict | None) -> str:
        """A factual, compact account of what the action produced."""
        d = self.dossier
        if lead is None:
            return "action did not run"
        status = lead.get("status", "")
        reason = lead.get("reason", "")
        produced = lead.get("produced") or {}
        parts: list[str] = []
        if status != "explored" or reason:
            parts.append(f"{status}{' (' + reason + ')' if reason else ''}")
        if lead.get("type") == "web_search":
            query = next((q for q in reversed(d.queries) if str(q.get("query", "")).casefold()
                          == str(args.get("query", "")).casefold()), None)
            if query:
                rows = query.get("results", [])
                parts.append(f"{len(rows)} result(s) via {query.get('provider', query.get('engine', '?'))}")
                for row in rows[:6]:
                    parts.append(f"• {str(row.get('title', ''))[:80]} — {row.get('url', '')}")
        for source_id in produced.get("sources", [])[:3]:
            source = next((s for s in d.sources if s.get("id") == source_id), None)
            if not source:
                continue
            if source.get("outcome") == "found":
                parts.append(f"read \"{str(source.get('title', ''))[:80]}\": {str(source.get('excerpt', ''))[:220]}")
            elif source.get("outcome") in BLOCKED_OUTCOMES:
                source.setdefault("extra", {})["needs_analyst"] = True
                parts.append(
                    f"could NOT open {source.get('url')} ({source.get('outcome')}) — ask_user can hand it to the analyst"
                )
            else:
                parts.append(f"{source.get('url')} returned {source.get('outcome')}")
        url = args.get("url", "")
        if url and not produced.get("sources"):
            blocked = next((s for s in d.sources if s.get("url") == canonical_url(url)
                            and s.get("outcome") in BLOCKED_OUTCOMES), None)
            if blocked:
                blocked.setdefault("extra", {})["needs_analyst"] = True
                parts.append(f"could NOT open {url} ({blocked.get('outcome')}) — ask_user can hand it to the analyst")
        for account_id in produced.get("accounts", [])[:5]:
            account = d.account(account_id)
            if account:
                parts.append(
                    f"account {account.get('ref')} {account.get('platform')} name={account.get('display_name', '')!r} "
                    f"verdict={account.get('verdict', '')}{' EXCLUDED' if not self._can_pivot(account) else ''}"
                )
        records = [r for r in d.evidence_records if r.get("id") in set(produced.get("evidence", []))]
        for record in records[:4]:
            parts.append(f"evidence {record['id']}: {record.get('claim')} — {str(record.get('excerpt', ''))[:120]}")
        queued = [l["purpose"] for l in d.leads if l.get("parent") == lead.get("id") and l.get("status") == "pending"]
        if queued:
            parts.append(f"planner queued {len(queued)} follow-up(s): " + "; ".join(q[:70] for q in queued[:4]))
        return (" | ".join(parts) or "no new records")[:1400]

    def _inspect(self, ref: str) -> str:
        from snoop.connect import resolve, trace

        kind, record = resolve(self.dossier, ref)
        if kind == "accounts":
            evidence = [r for r in self.dossier.evidence_records if r.get("account_id") == record.get("account_id")]
            lines = [(
                f"{record.get('ref')} {record.get('platform')} {record.get('canonical_url')} "
                f"name={record.get('display_name', '')!r} bio={str(record.get('bio', ''))[:120]!r} "
                f"verdict={record.get('verdict')}"
            )]
            lines += [f"{r['id']}: {r.get('claim')} — {str(r.get('excerpt', ''))[:100]}" for r in evidence[:6]]
        elif kind == "sources":
            lines = [f"{record.get('title')} {record.get('url')} ({record.get('outcome')}): {str(record.get('excerpt', ''))[:300]}"]
        else:
            lines = [f"{record.get('id')}: {record.get('claim')} — {record.get('excerpt')} [{record.get('source_url')}]"]
        path = trace(self.dossier, ref)
        if path["steps"]:
            lines.append("found via: " + " -> ".join(s["type"] + (f" '{s['query']}'" if s["query"] else "") for s in path["steps"]))
        return " | ".join(lines)[:1200]

    async def _ask(self, args: dict) -> str:
        from snoop import interview

        question = args.get("_question") or {
            "id": f"agent:{_hash(str(args.get('question', '')))}",
            "kind": "agent",
            "text": args["question"],
            "why": args.get("why", "the agent cannot resolve this alone")[:300],
            "options": ["i don't know", "skip"],
            "source_url": canonical_url(args["url"]) if args.get("url") else "",
            "manual_assist": bool(args.get("url")),
            "hint": "paste what you see, a URL, a username, or a short fact",
        }
        if question.get("source_url"):
            for source in self.dossier.sources:
                if source.get("url") == question["source_url"]:
                    source.setdefault("extra", {})["needs_analyst"] = True
        interview.set_pending(self.dossier, question)
        self.dossier.workflow["pending_question_text"] = question["text"]
        self.dossier.save()
        await self.bus.emit("question", question=question)
        return f"asked the analyst: {question['text']}"


async def run_agent(dossier, bus: Bus, *, goal: str = "", steps: int | None = None) -> dict:
    agent = Agent(dossier, bus, max_steps=steps, goal=goal)
    result = await agent.run()
    await bus.emit("agent_done", **result)
    return result


def search_ready_note() -> str:
    return "" if search.any_engine_ready() else " (web search unavailable — agent can read, check and ask, not search)"
