"""Case pipeline with versioned persistence and source-backed evidence."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field

from snoop.config import CASES_DIR, config
from snoop.core import Bus, Http, detect_kind, slugify
from snoop.enrich import candidate_handles, run_email_enrichment
from snoop.enum import enumerate_username, is_username  # noqa: F401  (test seams)
from snoop.evidence import CONFLICTING, UNRELATED, assess, normalize_context, records_for, summarise
from snoop.extract import enrich_hit  # noqa: F401  (test seam)
from snoop.model import ensure_account, utcnow

SCHEMA_VERSION = 4


@dataclass
class Dossier:
    id: str
    target: str
    kind: str
    created: str
    schema_version: int = SCHEMA_VERSION
    updated: str = ""
    mode: str = "full"
    context: list[str] = field(default_factory=list)
    handles_tried: list[str] = field(default_factory=list)
    hits: list[dict] = field(default_factory=list)
    discarded: list[dict] = field(default_factory=list)
    evidence_records: list[dict] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    authorized_emails: list[str] = field(default_factory=list)
    speculative_emails: list[str] = field(default_factory=list)
    enrichment: dict = field(default_factory=dict)
    analysis: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)
    deep: dict = field(default_factory=dict)
    history: list = field(default_factory=list)
    constraints: list[dict] = field(default_factory=list)
    action_history: list[dict] = field(default_factory=list)
    snapshots: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    queries: list[dict] = field(default_factory=list)
    leads: list[dict] = field(default_factory=list)
    workflow: dict = field(default_factory=dict)
    subject: dict = field(default_factory=dict)
    pending_question: dict = field(default_factory=dict)
    interview: list[dict] = field(default_factory=list)
    presenter: bool = False
    # Persona facts: cached AI extractions and the analyst's confirm/reject reviews.
    profile: dict = field(default_factory=dict)

    @property
    def all_accounts(self) -> list[dict]:
        return self.hits + self.discarded

    def account(self, ref: str) -> dict | None:
        key = ref.strip().casefold()
        return next(
            (
                h
                for h in self.all_accounts
                if key
                in {str(h.get("ref", "")).casefold(), str(h.get("account_id", "")).casefold()}
            ),
            None,
        )

    def record_action(self, action: str, **detail) -> None:
        self.action_history.append(
            {
                "id": f"act_{len(self.action_history) + 1:04d}",
                "action": action,
                "at": utcnow(),
                **detail,
            }
        )

    def save(self) -> str:
        self.schema_version = SCHEMA_VERSION
        self.updated = utcnow()
        CASES_DIR.mkdir(parents=True, exist_ok=True)
        path = CASES_DIR / f"{self.id}.json"
        temp = path.with_suffix(".json.tmp")
        temp.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False, default=str), "utf-8"
        )
        os.replace(temp, path)
        return str(path)

    @classmethod
    def load(cls, did: str) -> Dossier | None:
        import re

        if not re.fullmatch(r"[A-Za-z0-9._-]+", did or ""):
            return None
        path = CASES_DIR / f"{did}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            return None
        return cls._migrate(data)

    @classmethod
    def _migrate(cls, data: dict) -> Dossier:
        data = dict(data)
        used: set[str] = set()
        for hit in [*data.get("hits", []), *data.get("discarded", [])]:
            ensure_account(hit, used)
            used.add(hit["ref"])
            hit.setdefault("evidence_score", hit.get("score", 0))
            for old in hit.get("evidence", []):
                old.setdefault("evidence_id", "")
        data.setdefault("schema_version", SCHEMA_VERSION)
        data.setdefault("updated", data.get("created", utcnow()))
        data["context"] = normalize_context(data.get("context", []))
        fields = cls.__dataclass_fields__
        dossier = cls(**{k: v for k, v in data.items() if k in fields})
        dossier.schema_version = SCHEMA_VERSION
        from snoop.interview import ensure_subject

        ensure_subject(dossier)
        return dossier

    @classmethod
    def list_cases(cls) -> list[dict]:
        output = []
        for path in sorted(CASES_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            loaded = cls.load(path.stem)
            if loaded:
                output.append(
                    {
                        "id": loaded.id,
                        "target": loaded.target,
                        "kind": loaded.kind,
                        "updated": loaded.updated,
                        "mode": loaded.mode,
                        "accounts": len(loaded.all_accounts),
                        "sources": len(loaded.sources),
                        "queries": len(loaded.queries),
                        "workflow_status": loaded.workflow.get("status", ""),
                    }
                )
        return output


def _assign_refs(accounts: list[dict], existing: list[dict] | None = None) -> None:
    known = {h.get("account_id"): h.get("ref") for h in (existing or []) if h.get("ref")}
    used = set(known.values())
    next_no = 1
    for hit in accounts:
        ensure_account(hit, used)
        if hit["account_id"] in known:
            hit["ref"] = known[hit["account_id"]]
        elif not hit.get("ref") or hit["ref"] in used:
            while f"H{next_no:02d}" in used:
                next_no += 1
            hit["ref"] = f"H{next_no:02d}"
        used.add(hit["ref"])


def apply_assessments(dossier: Dossier, pool: list[dict]) -> dict:
    # A correction in the conversation is the current subject spelling for
    # evidence scoring.  Keep ``dossier.target`` unchanged as the original
    # user input/provenance, rather than silently rewriting the case.
    from snoop.interview import subject_display_name

    _assign_refs(pool, dossier.all_accounts)
    assessments = assess(
        pool,
        target=subject_display_name(dossier),
        kind=dossier.kind,
        context=dossier.context,
    )
    records: dict[str, dict] = {r["id"]: r for r in dossier.evidence_records if r.get("id")}
    constraints = {
        c.get("account_id"): c.get("decision")
        for c in dossier.constraints
        if c.get("active", True) and c.get("type") == "account"
    }
    for assessment in assessments:
        hit = pool[assessment.index]
        new_records = records_for(hit, assessment)
        records.update({r["id"]: r for r in new_records})
        for item, record in zip(assessment.evidence, new_records):
            item.evidence_id = record["id"]
        has_conflict = any(e.supports is False and e.points <= -35 for e in assessment.evidence)
        hit.update(
            score=assessment.score,
            evidence_score=assessment.score,
            verdict=assessment.verdict,
            ownership_status=CONFLICTING if has_conflict else assessment.verdict,
            evidence=[e.to_dict() for e in assessment.evidence],
            limitations=assessment.limitations,
        )
        decision = constraints.get(hit["account_id"])
        if decision == "discard":
            hit["verdict"] = hit["ownership_status"] = UNRELATED
            hit.setdefault("limitations", []).append("Discarded by an active user constraint.")
        elif decision == "keep" and hit["verdict"] == UNRELATED:
            hit["verdict"] = hit["ownership_status"] = "weak"
            hit.setdefault("limitations", []).append(
                "Kept by user selection; this is not independent verification."
            )
        hit["name_eligibility"] = "exact"
        if hit["name_eligibility"] == "different":
            hit["verdict"] = hit["ownership_status"] = UNRELATED
            hit["limitations"].append(
                "Excluded by exact-name mode: the readable profile name differs from the subject."
            )
        elif hit["name_eligibility"] == "unknown":
            hit["verdict"] = hit["ownership_status"] = "insufficient"
            hit["limitations"].append("No readable name; retained as an unresolved lead, not an exact-name candidate.")
    dossier.evidence_records = list(records.values())
    dossier.hits = [h for h in pool if h.get("verdict") not in {UNRELATED, CONFLICTING}]
    dossier.discarded = [h for h in pool if h.get("verdict") in {UNRELATED, CONFLICTING}]
    return summarise(assessments)


async def investigate(
    target: str,
    bus: Bus | None = None,
    *,
    kind: str | None = None,
    deep: bool = False,
    do_emails: bool = True,
    context: list[str] | None = None,
    authorized_emails: list[str] | None = None,
    mode: str = "full",
    preset: str | None = None,
    exact_name: bool = False,
    guided: bool = False,
) -> Dossier:
    """Start a case. The default mode runs the complete investigation loop:
    web discovery, source reading, account checks and evidence-backed follow-up.
    Pass mode="accounts" for the narrower username-enumeration operation."""
    from snoop.workflow import normalize_mode

    bus = bus or Bus()
    started = time.perf_counter()
    target = target.strip()
    kind = kind or detect_kind(target)
    if kind not in {"username", "name", "email", "domain"}:
        raise ValueError(f"unsupported target kind {kind!r}")
    mode = normalize_mode(mode)
    dossier = Dossier(
        id=f"{slugify(target)[:24]}-{int(time.time()) % 100000}",
        target=target,
        kind=kind,
        created=utcnow(),
        updated=utcnow(),
        mode=mode,
        context=normalize_context(context),
        authorized_emails=list(authorized_emails or []),
    )
    if kind == "email":
        dossier.authorized_emails.append(target)
    dossier.authorized_emails = list(dict.fromkeys(e.casefold() for e in dossier.authorized_emails))
    if config.presenter or bus.redact_values:
        bus.redact_values.extend([target])
    # Persist and announce the case before discovery begins. Web clients can
    # switch into the workspace immediately and reconnect even while the first
    # search or account probe is still running.
    from snoop.interview import ensure_subject

    ensure_subject(dossier)
    if kind == "name" and exact_name:
        dossier.subject.update(exact_name=True, name_confirmed=True)
    dossier.workflow["guided"] = guided
    dossier.save()
    await bus.emit("session", id=dossier.id)
    await bus.emit("stage", name=f"investigating {target!r} ({kind}, {mode} investigation)")

    if kind == "username":
        seed_handles = [target.lstrip("@")]
    elif kind == "email":
        local = target.split("@", 1)[0]
        seed_handles = [local, *candidate_handles(local.replace(".", " "))][:6]
    elif kind == "name":
        handles = candidate_handles(target)
        seed_handles = handles[: 12 if deep else 5]
    else:
        seed_handles = [target.split("//")[-1].split("/")[0].split(".")[0]]
    dossier.handles_tried = list(dict.fromkeys(seed_handles))
    if config.presenter or bus.redact_values:
        bus.redact_values.extend(dossier.handles_tried)

    from snoop.workflow import Workflow

    workflow = Workflow(
        dossier, bus, preset=preset or ("deep" if deep else None), mode=mode
    )
    if mode == "accounts":
        await _run_accounts_only(dossier, bus, workflow, deep=deep)
    else:
        await workflow.run()
        await workflow.finalize_analysis()

    # Only explicitly authorised addresses are enriched automatically.
    dossier.emails = list(dossier.authorized_emails)
    if do_emails and dossier.authorized_emails:
        async with Http() as http:
            dossier.enrichment = await run_email_enrichment(dossier.authorized_emails, http, bus)
        request_stats = dossier.stats.get("workflow_request_stats", {})
    else:
        request_stats = dossier.stats.get("workflow_request_stats", {})
    dossier.stats.setdefault("attempted", 0)
    for key, value in request_stats.items():
        dossier.stats[key] = dossier.stats.get(key, 0) + value

    counts = dossier.stats.get("verdict_counts") or {}
    if not counts:
        counts = summarise(assess(dossier.all_accounts, target=target, kind=kind, context=dossier.context))

    dossier.analysis.setdefault("identities", [])
    dossier.analysis["verdict_counts"] = counts
    dossier.stats = {
        **dossier.stats,
        **counts,
        "accounts_returned": len(dossier.all_accounts),
        "linked": len(dossier.hits),
        "discarded": len(dossier.discarded),
        "elapsed_s": round(time.perf_counter() - started, 2),
        "checks_run": dossier.stats.get("attempted", 0),
        "connector_definitions": len(__import__("snoop.enum", fromlist=["_SITES"])._SITES),
        "queries": len(dossier.queries),
        "sources": len(dossier.sources),
        "mode": mode,
        "preset": workflow.preset,
        "workflow_status": dossier.workflow.get("status", ""),
        "stop_reason": dossier.workflow.get("stop_reason", ""),
    }
    dossier.record_action("investigate", target=target, kind=kind, mode=mode, preset=workflow.preset)
    path = dossier.save()
    if config.presenter or bus.redact_values:
        from snoop.privacy import case_identifiers

        bus.redact_values.extend(case_identifiers(dossier))
    await bus.emit("done", id=dossier.id, path=path, stats=dossier.stats, analysis=dossier.analysis)
    return dossier


async def _run_accounts_only(dossier: Dossier, bus: Bus, workflow, *, deep: bool) -> None:
    """The narrower username-enumeration operation (no web discovery)."""
    from snoop.session import deterministic_grouping, reconcile_analysis
    from snoop.workflow import LeadQueue

    queue = LeadQueue(dossier)
    for handle in dossier.handles_tried:
        queue.add(
            "probe_handles",
            {"handles": [handle], "max_sites": 65, "origin": "user-target"},
            f"Check the supplied handle {handle!r} across supported platforms",
            "Accounts that exist under this handle",
            origin="user",
            score=6.0,
        )
    await workflow.run()
    dossier.analysis = reconcile_analysis(dossier, deterministic_grouping(dossier))
