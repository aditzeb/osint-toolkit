"""The persistent investigation loop shared by the CLI and the web app.

normalize input -> plan initial searches -> search web and check promising
accounts -> retrieve sources -> extract evidence and new leads -> resolve
identity hypotheses -> prioritize follow-up -> investigate those leads ->
update the case. Runs with finite budgets, saves completed work after every
step, cancels cleanly and keeps the remaining frontier for continuation.
"""

from __future__ import annotations

import asyncio
import time

from snoop import planner, search
from snoop.config import config
from snoop.core import Bus, Http
from snoop.leads import LeadQueue
from snoop.model import canonical_url, evidence_record, utcnow

PRESETS: dict[str, dict] = {
    "quick": {
        "searches": 8,
        "page_fetches": 12,
        "account_probes": 45,
        "model_calls": 4,
        "pivot_depth": 1,
        "sites_per_probe": 25,
        "generated_handles": 2,
    },
    "standard": {
        "searches": 18,
        "page_fetches": 30,
        "account_probes": 110,
        "model_calls": 10,
        "pivot_depth": 2,
        "sites_per_probe": 45,
        "generated_handles": 3,
    },
    "deep": {
        "searches": 40,
        "page_fetches": 60,
        "account_probes": 200,
        "model_calls": 20,
        "pivot_depth": 3,
        "sites_per_probe": 65,
        "generated_handles": 6,
    },
}

BUDGET_OF_TYPE = {
    "web_search": "searches",
    "read_source": "page_fetches",
    "crawl_site": "page_fetches",
    "read_document": "page_fetches",
    "check_account": "page_fetches",
    "expand_links": "page_fetches",
    "probe_handles": "account_probes",
    "archive_lookup": "page_fetches",
    "domain_lookup": "page_fetches",
    "image_clues": "page_fetches",
    "model_analysis": "model_calls",
    "import_lead": "searches",
}

def _subject_name(dossier) -> str:
    """Current confirmed/corrected spelling while retaining original input."""
    from snoop.interview import subject_display_name

    return subject_display_name(dossier)


def _react_to_analysis(analysis: dict) -> list[dict]:
    """Turn the model's suggested research_actions into leads to run."""
    leads: list[dict] = []
    if not isinstance(analysis, dict):
        return leads
    for action in (analysis.get("research_actions") or [])[:3]:
        if not isinstance(action, dict):
            continue
        kind = action.get("type")
        purpose = str(action.get("purpose") or f"AI-suggested {kind}")[:160]
        clues = [str(c) for c in (action.get("evidence_ids") or [])][:6]
        if kind == "web_search" and action.get("term"):
            leads.append({"type": "web_search", "args": {"query": str(action["term"])[:200]},
                          "purpose": purpose, "expected": "Additional cited evidence", "score": 6.0, "clues": clues})
        elif kind == "archive_lookup" and action.get("source_url"):
            leads.append({"type": "archive_lookup", "args": {"url": str(action["source_url"])[:500]},
                          "purpose": purpose, "expected": "Historical captures of a known page", "score": 5.0, "clues": clues})
        elif kind == "read_source" and action.get("source_url"):
            leads.append({"type": "read_source", "args": {"url": str(action["source_url"])[:500]},
                          "purpose": purpose, "expected": "Additional cited page content", "score": 5.5, "clues": clues})
    return leads


def normalize_preset(name: str | None) -> str:
    name = (name or "").strip().casefold()
    return name if name in PRESETS else "standard"


def normalize_mode(mode: str | None) -> str:
    mode = (mode or "").strip().casefold()
    if mode in {"accounts", "accounts-only", "accounts_only", "account"}:
        return "accounts"
    return "full"


class Workflow:
    """One investigation run over a saved case. Every mutation is persisted."""

    def __init__(self, dossier, bus: Bus | None = None, *, preset: str | None = None, mode: str | None = None):
        self.dossier = dossier
        self.bus = bus or Bus()
        self.preset = normalize_preset(preset or dossier.workflow.get("preset") or config.workflow_preset)
        self.mode = normalize_mode(mode or dossier.workflow.get("mode") or "full")
        self.budgets = dict(PRESETS[self.preset])
        self.spent = dict(dossier.workflow.get("spent") or {k: 0 for k in PRESETS["standard"]})
        for key in ("searches", "page_fetches", "account_probes", "model_calls"):
            self.spent.setdefault(key, 0)
        self.queue = LeadQueue(dossier)
        self.http: Http | None = None
        self.stop_reason = ""
        self._cancel = asyncio.Event()
        self._pause = asyncio.Event()
        self._stall = 0
        self._started_at = time.perf_counter()
        self._round_start = int(dossier.workflow.get("iterations", 0))

    # ------------------------------------------------------------------ control

    def cancel(self) -> None:
        self._cancel.set()
        if self.http:
            self.http.cancel()

    def pause(self) -> None:
        self._pause.set()

    def resume_loop(self) -> None:
        self._pause.clear()

    def _stopped(self) -> bool:
        return self._cancel.is_set()

    def status(self) -> dict:
        from snoop import interview

        return {
            "case_id": self.dossier.id,
            "status": self.dossier.workflow.get("status", "idle"),
            "mode": self.mode,
            "preset": self.preset,
            "budgets": self.budgets,
            "spent": self.spent,
            "stop_reason": self.stop_reason or self.dossier.workflow.get("stop_reason", ""),
            "leads": self.queue.stats(),
            "web_search_available": search.any_engine_ready(),
            "pending_question": interview.pending(self.dossier),
            "subject": interview.subject_status(self.dossier),
            "elapsed_s": round(time.perf_counter() - self._started_at, 1),
        }

    # -------------------------------------------------------------------- start

    async def start(self) -> str:
        """Normalize input and lay out the opening plan."""
        self.dossier.workflow.update(
            {
                "status": "running",
                "preset": self.preset,
                "mode": self.mode,
                "started_at": utcnow(),
                "stop_reason": "",
            }
        )
        await self.bus.emit("stage", name=f"planning investigation ({self.mode}, {self.preset})")
        if self.mode == "full" and not search.any_engine_ready():
            self.dossier.workflow["search_unavailable"] = True
            self.dossier.workflow["search_setup"] = (
                "web search unavailable — set SERPAPI_KEY (Google via SerpAPI) or "
                "BRAVE_SEARCH_API_KEY; searches stay pending and account discovery continues"
            )
            await self.bus.emit(
                "warning",
                detail="web search unavailable — set SERPAPI_KEY or BRAVE_SEARCH_API_KEY to enable discovery; "
                "continuing with the methods that remain available",
            )
        engine = ""
        actions = planner.initial_actions(
            _subject_name(self.dossier),
            self.dossier.kind,
            self.dossier.context,
            engine=engine,
            max_sites=self.budgets["sites_per_probe"],
            generated_handles=self.budgets["generated_handles"],
        )
        if self.mode == "accounts":
            actions = [a for a in actions if a["type"] == "probe_handles"]
            for action in actions:
                action["args"] = dict(action["args"])
                action["args"]["max_sites"] = 65
        added = 0
        for action in actions:
            if self.queue.add(
                action["type"],
                action["args"],
                action["purpose"],
                action.get("expected", ""),
                clues=action.get("clues"),
                origin="planner",
                score=action.get("score", 0),
            ):
                added += 1
        self.dossier.record_action("plan", preset=self.preset, mode=self.mode, leads_added=added)
        self.dossier.save()
        await self.bus.emit("plan", leads_added=added, mode=self.mode, preset=self.preset)
        return f"{added} planned action(s) ({self.mode} investigation, {self.preset} preset)"

    # ---------------------------------------------------------------------- run

    async def run(self) -> dict:
        # An unanswered question is a deliberate conversational pause. Do not
        # silently continue or duplicate its work until the analyst answers,
        # skips, or redirects it.
        from snoop import interview

        if interview.pending(self.dossier):
            self.dossier.workflow.update(preset=self.preset, mode=self.mode)
            self._set_status("needs_input", "waiting for the saved question to be answered")
            self.dossier.save()
            return self.status()
        if not self.dossier.leads and not self.dossier.workflow.get("iterations"):
            await self.start()
        else:
            # A saved frontier may be paused, cancelled, completed by a prior
            # budget, or recovered after a process exit. Once Run/Continue is
            # requested its persisted state must truthfully become running.
            self._set_status("running", "")
            self.dossier.workflow.update(preset=self.preset, mode=self.mode)
            # Retry only deferred work whose blocking condition has cleared.
            for lead in self.dossier.leads:
                if lead.get("status") != "deferred":
                    continue
                reason = lead.get("reason", "")
                key = BUDGET_OF_TYPE.get(lead["type"])
                if (("budget reached" in reason and key and self.spent.get(key, 0) < self.budgets[key])
                        or ("web search unavailable" in reason and search.any_engine_ready())
                        or "cancelled mid-flight" in reason):
                    self.queue.mark(lead["id"], "pending", "blocking condition cleared; ready to resume")
            self.dossier.workflow.pop("stopped_at", None)
            self.dossier.save()
            await self.bus.emit("stage", name="continuing from the saved frontier")
        async with Http(concurrency=config.concurrency) as http:
            self.http = http
            try:
                while not self._stopped():
                    if self._pause.is_set():
                        self._set_status("paused", "paused by the analyst")
                        self.dossier.save()
                        await self.bus.emit("paused", id=self.dossier.id)
                        return self.status()
                    if not await self.step():
                        break
                    if self.dossier.workflow.get("guided"):
                        count = self.dossier.workflow.get("iterations", 0) - self._round_start
                        interval = {"quick": 4, "standard": 6, "deep": 8}[self.preset]
                        if count >= interval:
                            self.dossier.workflow["at_checkpoint"] = True
                            await self._refresh_analysis(use_model=True)
                            await self._checkpoint()
                            question = interview.next_question(self.dossier)
                            if interview.would_unblock(self.dossier, question):
                                break
                            self.dossier.workflow.pop("at_checkpoint", None)
                            self._round_start = self.dossier.workflow.get("iterations", 0)
            except asyncio.CancelledError:
                self._set_status("cancelled", "cancelled by the analyst; completed work is saved")
                self.dossier.save()
                await self.bus.emit("cancelled", id=self.dossier.id)
                raise
            finally:
                self.dossier.stats["workflow_request_stats"] = dict(http.stats)
                self.http = None
        if self._stopped() and self.dossier.workflow.get("status") == "running":
            self._set_status("cancelled", "cancelled by the analyst; completed work is saved")
            self.dossier.save()
            await self.bus.emit("cancelled", id=self.dossier.id)
        # When clarification could unblock progress, surface one useful
        # question instead of declaring the investigation "done".
        if self.dossier.workflow.get("status") in {"running", "done"}:
            from snoop import interview

            question = interview.next_question(self.dossier)
            if interview.would_unblock(self.dossier, question):
                interview.set_pending(self.dossier, question)
                self._set_status("needs_input", f"needs input: {question['text']}")
                self.dossier.workflow["pending_question_text"] = question["text"]
                self.dossier.save()
                await self.bus.emit("question", question=question)
        self._finish()
        return self.status()

    async def step(self) -> bool:
        """Execute exactly one pending lead. Returns False when nothing ran."""
        from snoop.interview import pending

        if pending(self.dossier):
            self._set_status("needs_input", "waiting for the saved question to be answered")
            return False
        if self.http is None:
            async with Http(concurrency=config.concurrency) as http:
                self.http = http
                try:
                    return await self.step()
                finally:
                    self.http = None
        while True:
            if self._stopped():
                self._set_status("cancelled", "cancelled by the analyst; completed work is saved")
                return False
            lead = self.queue.next()
            if lead is None:
                deferred = [l for l in self.dossier.leads if l.get("status") == "deferred"]
                self._set_status(
                    "done",
                    "search deferred (web search unavailable)" if deferred else "useful leads exhausted",
                )
                return False
            budget_key = BUDGET_OF_TYPE.get(lead["type"])
            if budget_key and self.spent.get(budget_key, 0) >= self.budgets.get(budget_key, 0):
                self.queue.mark(lead["id"], "deferred", f"{budget_key} budget reached")
                continue
            await self._execute(lead)
            if self._stall >= {"quick": 3, "standard": 6, "deep": 10}[self.preset] and not any(
                row["type"] == "web_search" or float(row.get("score", 0)) >= 5
                for row in self.queue.pending()
            ):
                self._set_status("done", "progress stalled — no new information from recent leads")
                return False
            return True

    async def execute_direct(
        self,
        lead_type: str,
        args: dict,
        purpose: str = "",
        expected: str = "",
        origin: str = "user",
        parent: str = "",
    ) -> str:
        """Run one tool directly on the analyst's request (not from the queue).

        Direct commands still record themselves as case leads with their
        origin, so user-issued work is never presented as autonomous discovery.
        """
        from snoop.model import lead_record

        lead = lead_record(
            lead_type=lead_type,
            args=args,
            purpose=purpose or f"{lead_type} {args}",
            expected=expected,
            origin=origin,
        )
        if parent:
            lead["parent"] = parent
        # Lead IDs are derived from type+args. Reuse an existing record rather
        # than appending a duplicate ID that `mark()` could never address.
        existing = next((row for row in self.dossier.leads if row.get("id") == lead["id"]), None)
        if existing is not None:
            existing.update(
                purpose=lead["purpose"], expected=lead["expected"] or existing.get("expected", ""),
                origin=origin, status="pending", reason="re-run on request",
            )
            if parent:
                existing["parent"] = parent
            lead = existing
        else:
            self.dossier.leads.append(lead)
        if self.http is None:
            async with Http(concurrency=6) as http:
                self.http = http
                try:
                    await self._execute(lead)
                finally:
                    self.http = None
        else:
            await self._execute(lead)
        return lead.get("reason") or lead.get("status", "done")

    # ------------------------------------------------------------------ execute

    async def _execute(self, lead: dict) -> None:
        self.queue.mark(lead["id"], "running")
        self.dossier.workflow["current_action"] = {
            "id": lead["id"],
            "type": lead["type"],
            "purpose": lead["purpose"],
            "started_at": utcnow(),
        }
        # Persist the in-flight marker before doing network or parser work. A
        # restarted process can then explain and recover the interrupted lead.
        self.dossier.save()
        await self.bus.emit(
            "lead",
            id=lead["id"],
            type=lead["type"],
            purpose=lead["purpose"],
            status="running",
        )
        before = self._snapshot()
        known = {kind: set(ids) for kind, ids in self._record_ids().items()}
        try:
            handler = getattr(self, f"_do_{lead['type']}", None)
            if handler is None:
                self.queue.mark(lead["id"], "rejected", f"unknown lead type {lead['type']}")
                return
            async with asyncio.timeout(max(1.0, config.action_timeout)):
                await handler(lead)
            current = next(
                (l for l in self.dossier.leads if l.get("id") == lead["id"]), lead
            )
            if current.get("status") == "running":
                self.queue.mark(lead["id"], "explored")
        except asyncio.CancelledError:
            self.queue.mark(lead["id"], "deferred", "cancelled mid-flight; kept for resume")
            self.dossier.workflow.pop("current_action", None)
            raise
        except TimeoutError:
            self.queue.mark(
                lead["id"],
                "deferred",
                f"timed out after {config.action_timeout:g}s; kept for a later retry",
            )
            await self.bus.emit(
                "warning",
                detail=f"lead timed out; moving on: {lead['purpose'][:90]}",
            )
        except Exception as exc:  # boundary: one bad source must not kill the case
            self.queue.mark(lead["id"], "rejected", f"{type(exc).__name__}: {str(exc)[:120]}")
            await self.bus.emit("warning", detail=f"lead failed: {lead['purpose'][:80]} ({type(exc).__name__})")
        after = self._snapshot()
        gained = sum(after[i] - before[i] for i in range(len(before)))
        produced = {
            kind: [rid for rid in ids if rid not in known[kind]][:25]
            for kind, ids in self._record_ids().items()
        }
        if any(produced.values()):
            # Provenance for `trace`: which records this action created.
            current = next((row for row in self.dossier.leads if row.get("id") == lead["id"]), lead)
            current["produced"] = {k: v for k, v in produced.items() if v}
        self._stall = 0 if gained > 0 else self._stall + 1
        self.dossier.workflow["spent"] = self.spent
        self.dossier.workflow["iterations"] = self.dossier.workflow.get("iterations", 0) + 1
        self.dossier.workflow.pop("current_action", None)
        self.dossier.record_action(
            "lead_completed", lead_id=lead["id"], type=lead["type"], purpose=lead["purpose"],
            status=lead.get("status"), new_records=max(0, gained),
        )
        await self.bus.emit("action_complete", type=lead["type"], purpose=lead["purpose"],
                            status=lead.get("status"), new_records=max(0, gained))
        self.dossier.save()

    def _record_ids(self) -> dict[str, list[str]]:
        return {
            "sources": [s.get("id", "") for s in self.dossier.sources if s.get("id")],
            "accounts": [h.get("account_id", "") for h in self.dossier.all_accounts if h.get("account_id")],
            "evidence": [r.get("id", "") for r in self.dossier.evidence_records if r.get("id")],
        }

    def _snapshot(self) -> tuple[int, int, int, int]:
        return (
            len(self.dossier.sources),
            len(self.dossier.all_accounts),
            len(self.dossier.evidence_records),
            len(self.dossier.queries),
        )

    def _ingest_leads(self, leads: list[dict], pivot_from: dict | None = None, parent: str = "") -> int:
        depth = int((pivot_from or {}).get("pivot_depth", 0)) + 1 if pivot_from else 0
        parent = parent or str((pivot_from or {}).get("id", ""))
        added = 0
        for lead in leads:
            if self.mode == "accounts" and lead["type"] != "probe_handles":
                continue
            if depth > self.budgets["pivot_depth"]:
                continue
            row = self.queue.add(
                lead["type"],
                lead["args"],
                lead["purpose"],
                lead.get("expected", ""),
                clues=lead.get("clues"),
                origin="planner",
                score=lead.get("score", 0),
                parent=parent,
            )
            if row is not None and depth:
                row["pivot_depth"] = depth
            if row is not None and row.get("status") == "pending":
                added += 1
        if added:
            self.dossier.workflow["frontier_saved_at"] = utcnow()
        return added

    # ------------------------------------------------------------------ handlers

    async def _do_web_search(self, lead: dict) -> None:
        args = lead["args"]
        query, engine = args.get("query", ""), args.get("engine", "")
        await self.bus.emit("query", engine=engine or None, query=query, id=lead["id"])
        response = await search.web_search(query, engine or None, http=self.http, count=10)
        if response.outcome == "missing_key":
            self.queue.mark(lead["id"], "deferred", "web search unavailable — provider key not set")
            self.dossier.workflow["search_unavailable"] = True
            await self.bus.emit("warning", detail=f"web search unavailable: {response.error}")
            return
        self.spent["searches"] = self.spent.get("searches", 0) + 1
        record = search.query_record(response, via=lead.get("origin", "planner"))
        existing = next((q for q in self.dossier.queries if q.get("id") == record["id"]), None)
        if existing:
            known = {r.get("url") for r in existing.get("results", [])}
            existing["results"].extend(r for r in record["results"] if r.get("url") not in known)
        else:
            self.dossier.queries.append(record)
        self._record_rejected_search_matches(record)
        await self.bus.emit(
            "result",
            engine=response.engine,
            provider=response.provider,
            query=query,
            count=len(response.results),
            outcome=response.outcome,
            error=response.error,
        )
        self._ingest_leads(
            planner.react_to_search(record, _subject_name(self.dossier)), pivot_from=None, parent=lead["id"]
        )

    def _record_rejected_search_matches(self, record: dict) -> None:
        """Keep partial/fuzzy results inspectable without treating them as leads.

        The original query response remains in ``queries``. This small index is
        for the case UI/report, where analysts need to see why a similarly
        named person or a band was deliberately excluded.
        """
        from snoop.evidence import tokens

        target = set(tokens(_subject_name(self.dossier)))
        query_tokens = set(tokens(str(record.get("query", ""))))
        if len(target) < 2 or not target <= query_tokens:
            return
        rows = self.dossier.analysis.setdefault("rejected_matches", [])
        known = {row.get("url") for row in rows}
        for result in record.get("results", []):
            if planner.result_has_full_name(result, _subject_name(self.dossier)):
                continue
            url = str(result.get("url", ""))
            if not url or url in known:
                continue
            rows.append(
                {
                    "url": url,
                    "title": str(result.get("title", ""))[:300],
                    "snippet": str(result.get("snippet", ""))[:600],
                    "reason": "partial, surname-only, or fuzzy name match; not investigated as the subject",
                    "query_id": record.get("id", ""),
                }
            )
            known.add(url)
        self.dossier.analysis["rejected_matches"] = rows[-120:]

    async def _do_read_source(self, lead: dict) -> None:
        from snoop import discover

        url = lead["args"].get("url", "")
        engine = lead["args"].get("engine", "")
        via = f"search:{engine}" if engine else lead.get("origin", "planner")
        result = await discover.read_source(
            url, self.http, self.bus, via=via, subject=_subject_name(self.dossier)
        )
        self.spent["page_fetches"] = self.spent.get("page_fetches", 0) + 1
        source = result["source"]
        if result.get("unavailable"):
            # A relevant result whose page could not be opened stays as an
            # unverified lead with its search title/snippet — clearly marked,
            # never presented as a read page or as evidence.
            self._preserve_blocked_lead(url, engine, source.get("outcome", "unavailable"), source)
            return
        self._merge_source(source)
        page = result["page"]
        await self._record_page_evidence(source, page)
        self._ingest_leads(
            planner.react_to_page(source, page, self.dossier, _subject_name(self.dossier)), pivot_from=lead
        )

    def _preserve_blocked_lead(self, url: str, engine: str, outcome: str, source: dict | None = None) -> None:
        title = ""
        snippet = ""
        for query in self.dossier.queries:
            for result in query.get("results", []):
                if result.get("url") and result["url"].rstrip("/") == (url or "x").rstrip("/"):
                    title = str(result.get("title", ""))
                    snippet = str(result.get("snippet", ""))
                    break
            if title:
                break
        exact = planner.result_has_full_name({"title": title, "snippet": snippet}, _subject_name(self.dossier))
        record = source or {}
        record.setdefault("id", __import__("snoop.model", fromlist=["source_id"]).source_id(url))
        record.setdefault("url", url)
        record["outcome"] = outcome
        record["title"] = (title or record.get("title") or url)[:300]
        extra = record.get("extra") or {}
        extra.update(
            {
                "snippet_only": True,
                "verified": False,
                "search_title": title[:300],
                "snippet": snippet[:600],
                "engine": engine,
                "exact_name_result": exact,
                "note": "page could not be opened; the search snippet is an unverified lead, not evidence",
            }
        )
        record["extra"] = extra
        self._merge_source(record)
        self.dossier.record_action(
            "blocked_lead_preserved", url=url, outcome=outcome, exact_name_result=exact
        )

    async def _do_crawl_site(self, lead: dict) -> None:
        """Read a relevant site entry plus a few high-value internal pages."""
        from snoop import discover

        url = lead["args"].get("url", "")
        remaining = self.budgets["page_fetches"] - self.spent.get("page_fetches", 0)
        max_pages = max(1, min(int(lead["args"].get("max_pages") or 5), remaining))
        results = await discover.crawl_site(
            url,
            self.http,
            self.bus,
            via=lead.get("origin", "planner"),
            subject=_subject_name(self.dossier),
            max_pages=max_pages,
        )
        self.spent["page_fetches"] = self.spent.get("page_fetches", 0) + len(results)
        for result in results:
            source = result["source"]
            self._merge_source(source)
            if result.get("unavailable"):
                continue
            page = result["page"]
            await self._record_page_evidence(source, page)
            self._ingest_leads(
                planner.react_to_page(source, page, self.dossier, _subject_name(self.dossier)),
                pivot_from=lead,
            )

    async def _do_check_account(self, lead: dict) -> None:
        from snoop.actions import anchor
        from snoop.core import UnsafeUrl

        url = lead["args"].get("url", "")
        engine = lead["args"].get("engine", "")
        discovery = f"search:{engine}" if engine else "web-source"
        before = {h["account_id"] for h in self.dossier.all_accounts}
        try:
            await anchor(self.dossier, url, self.bus, discovery_source=discovery)
        except (ValueError, UnsafeUrl):
            self.queue.mark(lead["id"], "rejected", "not a supported public profile URL")
            return
        self.spent["page_fetches"] = self.spent.get("page_fetches", 0) + 1
        new_accounts = [h for h in self.dossier.all_accounts if h["account_id"] not in before]
        target = canonical_url(url)
        if not new_accounts and any(
            canonical_url(h.get("canonical_url", "")) == target for h in self.dossier.all_accounts
        ):
            # Already validated through another path (sameAs, a search result):
            # a repeat check is not a blocked page.
            self.queue.mark(lead["id"], "explored", "account already validated in this case")
            return
        if not new_accounts:
            # The profile page could not be validated (login wall, CAPTCHA,
            # rate limit...): keep the exact-name result inspectable instead of
            # silently dropping it.
            last = next(
                (
                    a
                    for a in reversed(self.dossier.action_history)
                    if a.get("action") == "anchor_unavailable"
                ),
                None,
            )
            outcome = str((last or {}).get("outcome", "blocked"))
            self._preserve_blocked_lead(url, engine, outcome)
            return
        for account in new_accounts:
            self._ingest_leads(planner.react_to_account(account, source_id=""), pivot_from=lead)
        await self._refresh_analysis(use_model=False)

    async def _do_probe_handles(self, lead: dict) -> None:
        from snoop import pipeline as pipeline_mod
        from snoop.enum import is_username, prioritized_sites
        from snoop.pipeline import _assign_refs, apply_assessments

        handles = [h for h in lead["args"].get("handles", []) if h][:6]
        budget = self.budgets["account_probes"]
        max_sites = min(
            int(lead["args"].get("max_sites") or self.budgets["sites_per_probe"]),
            self.budgets["sites_per_probe"],
        )
        sites = prioritized_sites(min(max_sites, budget))
        probes = {"count": 0}

        def _count(ev) -> None:
            if ev.kind == "probe":
                probes["count"] += 1

        self.bus.on(_count)
        try:
            for handle in handles:
                remaining = budget - self.spent.get("account_probes", 0) - probes["count"]
                if remaining <= 0:
                    break
                from snoop.enum import is_username

                if not is_username(handle):
                    continue
                handle_sites = sites[: max(1, remaining)]
                await self.bus.emit(
                    "stage", name=f"checking handle {handle!r} on {len(handle_sites)} platforms"
                )
                hits = await pipeline_mod.enumerate_username(
                    handle, self.bus, self.http, sites=handle_sites
                )
                await asyncio.gather(
                    *(pipeline_mod.enrich_hit(self.http, hit, self.bus) for hit in hits)
                )
                existing_ids = {h["account_id"] for h in self.dossier.all_accounts}
                fresh = []
                for hit in hits:
                    hit.matched_handle = handle
                    hit.extra["matched_handle"] = handle
                    hit.extra["alias_origin"] = lead["args"].get("origin", "generated-hypothesis")
                    if hit.account_id not in existing_ids:
                        fresh.append(hit)
                if fresh:
                    pool = self.dossier.all_accounts + [h.to_dict() for h in fresh]
                    for row in pool:
                        row.setdefault("original_search_input", self.dossier.target)
                    _assign_refs(pool, self.dossier.all_accounts)
                    apply_assessments(self.dossier, pool)
                    for hit in fresh:
                        assessed = self.dossier.account(hit.account_id)
                        if not assessed:
                            continue
                        self._ingest_leads(
                            planner.react_to_account(assessed, source_id=""), pivot_from=lead
                        )
                self.dossier.handles_tried = list(
                    dict.fromkeys([*self.dossier.handles_tried, handle])
                )
        finally:
            self.bus.off(_count)
        self.spent["account_probes"] = self.spent.get("account_probes", 0) + probes["count"]
        await self._refresh_analysis(use_model=False)

    async def _do_expand_links(self, lead: dict) -> None:
        from snoop.actions import follow

        ref = lead["args"].get("ref", "")
        account = self.dossier.account(ref)
        if lead.get("origin") == "planner" and not account:
            self.queue.mark(lead["id"], "rejected", "account is not eligible for target-directed pivots")
            return
        await follow(self.dossier, ref, self.bus, depth=1, budget=6)
        last = next(
            (a for a in reversed(self.dossier.action_history) if a.get("action") == "follow"), None
        )
        if last:
            self.spent["page_fetches"] = self.spent.get("page_fetches", 0) + int(
                last.get("attempted", 1)
            )

    async def _do_read_document(self, lead: dict) -> None:
        from snoop import discover

        url = lead["args"].get("url", "")
        result = await discover.read_document(
            url, self.http, self.bus, via=lead.get("origin", "planner")
        )
        self.spent["page_fetches"] = self.spent.get("page_fetches", 0) + 1
        source = result["source"]
        self._merge_source(source)
        if result.get("unavailable"):
            await self.bus.emit(
                "document",
                url=url,
                status="unavailable",
                method="not-read",
            )
            return
        if result.get("status") == "needs_ocr":
            await self.bus.emit(
                "warning",
                detail=f"document {url} appears scanned; install optional pypdf/OCR dependencies for text extraction",
            )
        extra = source.get("extra") or {}
        if extra.get("author"):
            record = evidence_record(
                claim="document-author-metadata",
                source_url=url,
                source_location="document metadata /Author",
                value=extra["author"],
                excerpt=f"document author metadata: {extra['author']}",
                method="document-metadata",
                kind="observation",
                supports=None,
                dependence=source["id"],
                limitation="Document metadata is a clue, not proof of authorship.",
            )
            self._merge_evidence(record)
        pages = result.get("pages") or [
            {"text": result.get("text", ""), "location": "document text"}
        ]
        for page in pages:
            mentions = discover.find_mentions(page.get("text", ""), _subject_name(self.dossier))
            for mention in mentions:
                record = evidence_record(
                    claim="mentioned-in-document",
                    source_url=url,
                    source_location=page.get("location", "document text"),
                    excerpt=mention["excerpt"],
                    method="document-text",
                    kind="observation",
                    strength=10,
                    supports=True,
                    dependence=source["id"],
                    retrieved_at=source.get("retrieved_at"),
                )
                self._merge_evidence(record)
                await self.bus.emit(
                    "evidence", id=record["id"], claim=record["claim"], source_url=url
                )
        follow_up: list[dict] = []
        if self.dossier.kind == "name" and not any(
            discover.find_mentions(page.get("text", ""), _subject_name(self.dossier)) for page in pages
        ):
            return
        for link in result.get("urls", [])[:8]:
            follow_up.append(
                {
                    "type": "read_source",
                    "args": {"url": link},
                    "purpose": f"Read page linked from document: {link[:70]}",
                    "expected": "Corroborating pages for the document's claims",
                    "score": 4.0,
                }
            )
        self._ingest_leads(follow_up, pivot_from=lead)

    async def _do_archive_lookup(self, lead: dict) -> None:
        from snoop import discover

        target = lead["args"].get("url") or lead["args"].get("domain", "")
        cdx = await discover.wayback_cdx(target, self.http, limit=6)
        self.spent["page_fetches"] = self.spent.get("page_fetches", 0) + 1
        for capture in cdx.get("captures", [])[:6]:
            record = evidence_record(
                claim="archive-capture",
                source_url=capture.get("capture_url", ""),
                value=capture.get("original", target),
                excerpt=f"archived capture ({capture.get('statuscode', '')} {capture.get('mimetype', '')})",
                method="wayback-cdx",
                kind="observation",
                supports=None,
                source_event_time=capture.get("capture_timestamp", ""),
                dependence=f"cdx:{target}",
                limitation="An archived capture proves the page existed, not who owned it.",
            )
            self._merge_evidence(record)
        if cdx.get("captures"):
            latest = cdx["captures"][-1]
            self._ingest_leads(
                [
                    {
                        "type": "read_source",
                        "args": {"url": latest["capture_url"]},
                        "purpose": "Read the latest archived capture of this URL",
                        "expected": "Content from a page that may no longer be reachable",
                        "score": 3.5,
                    }
                ],
                pivot_from=lead,
            )
        cc = await discover.common_crawl_lookup(target, self.http, limit=8)
        for row in cc.get("urls", [])[:8]:
            record = evidence_record(
                claim="common-crawl-capture",
                source_url=row.get("url", ""),
                value=cc.get("index", ""),
                excerpt="Common Crawl URL-index capture",
                method="common-crawl-index",
                kind="observation",
                supports=None,
                source_event_time=row.get("capture_timestamp", ""),
                dependence=f"cc:{target}",
                limitation="URL-index presence proves crawl coverage, not identity.",
            )
            self._merge_evidence(record)
        await self.bus.emit("archive", target=target, captures=len(cdx.get("captures", [])))

    async def _do_domain_lookup(self, lead: dict) -> None:
        from snoop import discover

        domain = lead["args"].get("domain", "")
        self.spent["page_fetches"] = self.spent.get("page_fetches", 0) + 1
        rdap = await discover.rdap_domain(domain, self.http)
        if rdap.get("outcome") == "found":
            record = evidence_record(
                claim="domain-registration",
                source_url=f"https://rdap.org/domain/{domain}",
                value=rdap.get("registered", ""),
                excerpt=f"registered {rdap.get('registered', 'unknown')}; registrar {rdap.get('registrar', 'unknown')}",
                method="rdap",
                kind="observation",
                supports=None,
                source_event_time=rdap.get("registered", ""),
                dependence=f"rdap:{domain}",
                limitation="Registration data is a clue; shared registrars and hosts prove nothing personal.",
            )
            self._merge_evidence(record)
        dns = await discover.dns_addresses(domain)
        if dns.get("outcome") == "found":
            record = evidence_record(
                claim="domain-dns",
                source_url=f"dns://{domain}",
                value=dns.get("addresses", []),
                excerpt="resolves to " + ", ".join(dns.get("addresses", [])[:4]),
                method="dns",
                kind="observation",
                supports=None,
                dependence=f"dns:{domain}",
                limitation="IP addresses are shared infrastructure clues, not ownership.",
            )
            self._merge_evidence(record)
        ct = await discover.ct_certificates(domain, self.http)
        if ct.get("outcome") == "found":
            names = sorted({n for c in ct.get("certificates", []) for n in (c.get("names", "") or "").split()})[:8]
            record = evidence_record(
                claim="ct-certificates",
                source_url=f"https://crt.sh/?q=%25.{domain}",
                value=names,
                excerpt=f"{len(ct.get('certificates', []))} public certificates; subdomains: {', '.join(names[:5])}",
                method="crt.sh",
                kind="observation",
                supports=None,
                dependence=f"ct:{domain}",
                limitation="Certificates cover hostnames, not people.",
            )
            self._merge_evidence(record)
            follow_up = []
            for name in names:
                host = name.strip("*.")
                if host and host not in {domain, f"www.{domain}"} and not host.startswith(("mail.", "smtp.")):
                    follow_up.append(
                        {
                            "type": "read_source",
                            "args": {"url": f"https://{host}"},
                            "purpose": f"Read public subdomain {host} surfaced by certificates",
                            "expected": "A related public project page, if one exists",
                            "score": 2.2,
                        }
                    )
            self._ingest_leads(follow_up[:3], pivot_from=lead)
        await self.bus.emit("domain", domain=domain, rdap=rdap.get("outcome"), dns=dns.get("outcome"))

    async def _do_image_clues(self, lead: dict) -> None:
        from snoop import discover

        url = lead["args"].get("url", "")
        reverse = bool(lead["args"].get("reverse"))
        result = await discover.image_clues(url, self.http, reverse=reverse)
        self.spent["page_fetches"] = self.spent.get("page_fetches", 0) + 1
        text = (result.get("text", "") or "").strip()
        if text:
            record = evidence_record(
                claim="image-ocr-text",
                source_url=url,
                value=text[:200],
                excerpt=text[:300],
                method="image-ocr",
                kind="observation",
                supports=None,
                limitation="OCR reads pixels; it does not identify people or prove ownership.",
            )
            self._merge_evidence(record)
        follow_up = []
        for handle in result.get("handles", [])[:6]:
            follow_up.append(
                {
                    "type": "web_search",
                    "args": {"query": f'"{handle}"'},
                    "purpose": f'Search handle "{handle}" read from image text',
                    "expected": "Accounts using this handle",
                    "score": 4.0,
                }
            )
        for link in result.get("urls", [])[:4]:
            follow_up.append(
                {
                    "type": "read_source",
                    "args": {"url": link},
                    "purpose": f"Read URL found in image text: {link[:60]}",
                    "expected": "The site the image points to",
                    "score": 3.0,
                }
            )
        self._ingest_leads(follow_up, pivot_from=lead)
        if isinstance(result.get("reverse_image"), dict):
            for match in result["reverse_image"].get("matches", [])[:6]:
                follow = {
                    "type": "read_source",
                    "args": {"url": match.get("url", "")},
                    "purpose": f"Read page reusing this image: {match.get('source', '')[:40]}",
                    "expected": "Context for image reuse (not facial identification)",
                    "score": 2.5,
                }
                self._ingest_leads([follow], pivot_from=lead)

    async def _do_model_analysis(self, lead: dict) -> None:
        await self._refresh_analysis(use_model=True)

    async def _do_import_lead(self, lead: dict) -> None:
        # Imports are handled by the import commands; the queue entry records
        # that the analyst supplied this lead explicitly.
        self.queue.mark(lead["id"], "explored", "imported by the analyst")

    # ------------------------------------------------------------------ helpers

    def _merge_source(self, source: dict) -> None:
        existing = next(
            (s for s in self.dossier.sources if s.get("url") == source.get("url")), None
        ) or next(
            (s for s in self.dossier.sources if s.get("id") == source.get("id")), None
        )
        if existing:
            if existing.get("outcome") == "found" and source.get("outcome") != "found":
                # A later failed re-read (rate limit, login wall) must not turn
                # an already-read page back into an unverified lead.
                existing.setdefault("extra", {})["last_retry_outcome"] = source.get("outcome", "")
                return
            existing.update({k: v for k, v in source.items() if v})
        else:
            self.dossier.sources.append(source)
            if len(self.dossier.sources) > 400:
                self.dossier.sources = self.dossier.sources[-400:]

    def _merge_evidence(self, record: dict) -> None:
        existing = next(
            (r for r in self.dossier.evidence_records if r.get("id") == record.get("id")), None
        )
        if existing:
            existing.update({k: v for k, v in record.items() if v})
        else:
            self.dossier.evidence_records.append(record)

    async def _record_page_evidence(self, source: dict, page: dict) -> None:
        from snoop.evidence import tokens

        for mention in page.get("mentions", [])[:5]:
            record = evidence_record(
                claim=f"mentioned-in-source ({mention.get('role', 'mentioned')})",
                source_url=source["url"],
                source_location="main page text",
                excerpt=mention.get("excerpt", ""),
                method="page-text",
                kind="observation",
                strength=8,
                supports=True,
                dependence=source["id"],
                retrieved_at=source.get("retrieved_at"),
                source_event_time=page.get("published") or None,
                limitation="A mention is a third-party statement, not account ownership.",
            )
            self._merge_evidence(record)
            await self.bus.emit("evidence", id=record["id"], claim=record["claim"], source_url=source["url"])
        for person in page.get("persons", [])[:4]:
            wanted = set(tokens(_subject_name(self.dossier)))
            if not wanted or not wanted <= set(tokens(person.get("name", ""))):
                continue
            record = evidence_record(
                claim="structured-person-assertion",
                source_url=source["url"],
                source_location="JSON-LD Person/ProfilePage",
                value=person.get("name", ""),
                excerpt=f"page structure asserts Person {person.get('name', '')}"
                + (
                    f" with aliases {', '.join(person.get('alternate_names', [])[:3])}"
                    if person.get("alternate_names")
                    else ""
                ),
                method="json-ld",
                kind="observation",
                strength=6,
                supports=True,
                dependence=source["id"],
                retrieved_at=source.get("retrieved_at"),
                limitation="Structured data is the site's own assertion (sameAs), not proof.",
            )
            self._merge_evidence(record)
            await self.bus.emit("evidence", id=record["id"], claim=record["claim"], source_url=source["url"])

    async def _refresh_analysis(self, *, use_model: bool) -> None:
        from snoop.analyst import analyze
        from snoop.pipeline import apply_assessments
        from snoop.session import deterministic_grouping, reconcile_analysis

        apply_assessments(self.dossier, self.dossier.all_accounts)
        analysis = deterministic_grouping(self.dossier)
        if (use_model and (self.dossier.hits or self.dossier.evidence_records) and config.ai_provider()
                and self.spent.get("model_calls", 0) < self.budgets["model_calls"]):
            self.spent["model_calls"] = self.spent.get("model_calls", 0) + 1
            model = await analyze(
                _subject_name(self.dossier),
                self.dossier.kind,
                self.dossier.hits,
                self.dossier.enrichment,
                self.bus,
                context=self.dossier.context,
                evidence_records=self.dossier.evidence_records,
            )
            analysis = reconcile_analysis(self.dossier, model)
            self.dossier.workflow["last_ai_review"] = {
                "at": utcnow(), "mode": analysis.get("analysis_mode", "deterministic"),
                "key_findings": analysis.get("key_findings", []),
                "contradictions": analysis.get("contradictions", []),
            }
            # Only ongoing rounds enqueue suggestions. A final report must not
            # silently add work after the workflow has declared itself done.
            if self.dossier.workflow.get("status") == "running":
                added = self._ingest_leads(_react_to_analysis(analysis))
                if added:
                    await self.bus.emit("plan", leads_added=added, mode="AI suggestions from cited evidence")
            self.dossier.workflow["spent"] = self.spent
        self.dossier.analysis = reconcile_analysis(self.dossier, analysis)
        await self.bus.emit("stage", name=f"{len(self.dossier.analysis.get('identities', []))} identity hypothesis/hypotheses")

    def _set_status(self, status: str, reason: str) -> None:
        self.stop_reason = reason
        self.dossier.workflow.update(
            {
                "status": status,
                "stop_reason": reason,
                "stopped_at": utcnow() if status != "running" else "",
                "spent": self.spent,
            }
        )

    async def _checkpoint(self) -> None:
        from snoop.briefing import build_briefing

        briefing = build_briefing(self.dossier)
        checkpoints = self.dossier.workflow.setdefault("checkpoints", [])
        row = {"round": len(checkpoints) + 1, "at": utcnow(),
               "iterations": self.dossier.workflow.get("iterations", 0),
               "coverage": briefing["coverage"], "gaps": briefing["gaps"],
               "next_actions": briefing["next_actions"]}
        checkpoints.append(row)
        self.dossier.save()
        await self.bus.emit("checkpoint", **row)

    def _finish(self) -> None:
        status = self.dossier.workflow.get("status", "running")
        if status == "running":
            self._set_status(
                "done",
                self.stop_reason
                or ("useful leads exhausted" if not self.queue.pending() else "budget reached"),
            )
        self.dossier.workflow["frontier_saved_at"] = utcnow()
        self.dossier.stats = {**self.dossier.stats, **self._stats()}
        self.dossier.record_action(
            "workflow_done",
            status=self.dossier.workflow.get("status"),
            reason=self.stop_reason,
            spent=self.spent,
        )
        self.dossier.save()

    def _stats(self) -> dict:
        return {
            "queries": len(self.dossier.queries),
            "sources": len(self.dossier.sources),
            "leads_total": len(self.dossier.leads),
            "leads_pending": len(self.queue.pending()),
            "workflow_spent": dict(self.spent),
        }

    async def finalize_analysis(self) -> dict:
        """Model-backed wrap-up when a provider is configured and budget allows."""
        if (self.dossier.workflow.get("status") != "needs_input" and config.ai_provider()
                and self.spent.get("model_calls", 0) < self.budgets["model_calls"]):
            await self._refresh_analysis(use_model=True)
        return self.dossier.analysis


def import_search(dossier, query: str, result_urls: list[str], bus: Bus | None = None, *, note: str = "", query_link: str = "") -> dict:
    """Record a manual-assistance search: the analyst ran the query and picked URLs."""
    bus = bus or Bus()
    response = search.manual_results(query, result_urls, via="manual-assistance", query_link=query_link)
    record = search.query_record(response, via="manual-assistance")
    record["note"] = note[:300]
    existing = next((q for q in dossier.queries if q.get("id") == record["id"]), None)
    if existing:
        known = {r.get("url") for r in existing.get("results", [])}
        existing["results"].extend(r for r in record["results"] if r.get("url") not in known)
    else:
        dossier.queries.append(record)
    queue = LeadQueue(dossier)
    added = 0
    from snoop.actions import _site_for

    for result in record["results"]:
        url = result.get("url", "")
        if not url:
            continue
        if _site_for(url):
            lead = queue.add(
                "check_account",
                {"url": url},
                f"Validate analyst-supplied result: {url[:70]}",
                "A validated account from a manual search result",
                origin="user",
                score=8.0,
            )
        else:
            lead = queue.add(
                "read_source",
                {"url": url},
                f"Read analyst-supplied result: {url[:70]}",
                "Mentions and profile links on a manually picked page",
                origin="user",
                score=6.0,
            )
        if lead:
            added += 1
    dossier.record_action("manual_search", query=query, results=len(result_urls), label="manual assistance")
    dossier.save()
    return {
        "query": query,
        "results": len(record["results"]),
        "leads_added": added,
        "label": "manual assistance (not an automated search)",
    }
