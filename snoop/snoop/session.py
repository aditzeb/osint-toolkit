"""Interactive case mutations. User decisions are reversible constraints."""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from difflib import SequenceMatcher

from snoop.analyst import analyze, answer_question
from snoop.core import Bus, Http
from snoop.enum import enumerate_username
from snoop.evidence import normalize_context
from snoop.extract import enrich_hit
from snoop.model import new_identity
from snoop.pipeline import apply_assessments


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").casefold())


def relabel(analysis: dict) -> dict:
    identities = analysis.get("identities", []) if isinstance(analysis, dict) else []
    # Migrate legacy model output once: rank, resolve duplicate claims, and then
    # persist IDs/labels so later analysis cannot silently renumber decisions.
    if identities and not any(i.get("id") for i in identities):
        identities.sort(key=lambda i: -float(i.get("confidence", 0) or 0))
        claimed = set()
        kept = []
        for identity in identities:
            accounts = [x for x in identity.get("is_same_person_accounts", []) if x not in claimed]
            claimed.update(accounts)
            if accounts:
                identity["is_same_person_accounts"] = accounts
                kept.append(identity)
        identities = kept
        for index, identity in enumerate(identities):
            identity["label"] = chr(ord("A") + index)
    used_labels = {i.get("label") for i in identities if i.get("label")}
    next_no = 0
    for identity in identities:
        identity.setdefault("id", "legacy-" + _norm(identity.get("name", "identity")))
        accounts = identity.get("account_ids", identity.get("is_same_person_accounts", []))
        identity["account_ids"] = list(dict.fromkeys(accounts))
        identity["is_same_person_accounts"] = identity["account_ids"]
        if not identity.get("label"):
            while chr(ord("A") + next_no) in used_labels:
                next_no += 1
            identity["label"] = chr(ord("A") + next_no)
            used_labels.add(identity["label"])
        identity["display_label"] = identity["label"]
        identity.setdefault("evidence_score", int(float(identity.pop("confidence", 0) or 0) * 100))
        identity.setdefault("status", "unresolved")
        identity.setdefault("selected", False)
        identity.setdefault("membership_hypotheses", [])
    analysis["identities"] = identities
    return analysis


def _dedupe_membership(analysis: dict) -> dict:
    """One account can sit in at most one established identity; competing claims
    survive explicitly as membership hypotheses instead of silently duplicating."""
    identities = analysis.get("identities", [])
    owner: dict[str, dict] = {}
    for identity in identities:
        identity.setdefault("membership_hypotheses", [])
        kept = []
        for account_id in identity.get("account_ids", []):
            existing = owner.get(account_id)
            if existing is None:
                owner[account_id] = identity
                kept.append(account_id)
            elif existing is not identity:
                identity["membership_hypotheses"].append(
                    {
                        "account_id": account_id,
                        "competing_identity": existing.get("label", "?"),
                        "note": (
                            f"also claimed by identity {existing.get('label', '?')}; "
                            "membership remains a competing hypothesis"
                        ),
                    }
                )
        identity["account_ids"] = kept
        identity["is_same_person_accounts"] = kept
    return analysis


def deterministic_grouping(dossier) -> dict:
    """Group accounts into identity hypotheses using explicit evidence only.

    Only strong explicit cross-links merge accounts; a shared handle, a copied
    avatar or co-occurrence never does. Namesakes stay separate hypotheses and
    accounts without readable names remain unresolved members.
    """
    from snoop.evidence import build_links, tokens
    from snoop.interview import subject_display_name

    def eligibility(_dossier, _hit) -> str:
        return "exact"

    def exact_name(a: str, b: str) -> bool:
        return True

    hits = [h for h in dossier.hits if eligibility(dossier, h) not in {"different", "unknown"}]
    parent: dict[str, str] = {h["account_id"]: h["account_id"] for h in hits}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    by_ref = {h.get("ref"): h for h in hits}
    for index, evs in build_links(hits).items():
        for ev in evs:
            if ev.label == "cross-link" and ev.points >= 18 and "explicitly links to" in ev.detail:
                other = by_ref.get(ev.detail.rsplit(" ", 1)[-1])
                if other:
                    union(hits[index]["account_id"], other["account_id"])

    groups: dict[str, list[dict]] = {}
    for hit in hits:
        groups.setdefault(find(hit["account_id"]), []).append(hit)

    target_tokens = set(tokens(subject_display_name(dossier)))
    identities = []
    for members in groups.values():
        names = [m.get("display_name", "") for m in members if m.get("display_name")]
        # The card shows the profile's own name. An identity is only described
        # by the subject name when a member's name matches it EXACTLY; a
        # surname or fuzzy overlap ("Bena Lindqvist") never renames an unrelated
        # profile to the searched name.
        exact = [n for n in names if exact_name(n, subject_display_name(dossier))] if target_tokens else []
        name = (exact or names or [""])[0]
        identities.append(
            {
                "id": "grp_" + _norm(name or "identity")[:24] + str(len(identities)),
                "label": "",
                "name": name,
                "exact_name_match": bool(exact),
                "evidence_score": max(int(m.get("evidence_score", 0) or 0) for m in members),
                "status": "unresolved",
                "account_ids": [m["account_id"] for m in members],
                "reasoning": "Deterministic grouping from explicit cross-links only; "
                "unlinked accounts stay separate hypotheses.",
                "evidence_ids": sorted(
                    {e.get("evidence_id") for m in members for e in m.get("evidence", []) if e.get("evidence_id")}
                )[:12],
                "limitations": [
                    "Grouped by explicit profile cross-links; ownership remains unverified."
                ],
                "selected": False,
                "membership_hypotheses": [],
            }
        )
    return relabel(
        {
            "identities": identities,
            "key_findings": [],
            "contradictions": [],
            "next_steps": [],
            "summary": (
                f"{len(identities)} identity hypothesis/hypotheses from {len(hits)} candidate account(s); "
                "grouped only by explicit cross-links."
            ),
            "analysis_mode": "deterministic",
        }
    )


def _hit_map(dossier) -> dict:
    output = {}
    for hit in dossier.all_accounts if hasattr(dossier, "all_accounts") else dossier.hits:
        for key in (hit.get("account_id"), hit.get("ref"), hit.get("platform")):
            if key:
                output.setdefault(key, hit)
    return output


def alias_variants(dossier, identity: dict) -> list[dict]:
    hits = _hit_map(dossier)
    groups: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for account in identity.get("account_ids", identity.get("is_same_person_accounts", [])):
        hit = hits.get(account)
        if hit and hit.get("display_name"):
            groups[_norm(hit["display_name"])].append(
                (hit.get("ref", account), hit["display_name"])
            )
    return [
        {
            "name": rows[0][1],
            "platforms": [r[0] for r in rows],
            "also_seen_as": sorted({r[1] for r in rows[1:]}),
        }
        for rows in groups.values()
    ]


def compare_identities(dossier) -> list[dict]:
    hits = _hit_map(dossier)
    identities = dossier.analysis.get("identities", [])
    output = []
    for left in identities:
        overlaps = []
        left_hits = [
            hits[x]
            for x in left.get("account_ids", left.get("is_same_person_accounts", []))
            if x in hits
        ]
        for right in identities:
            if right is left:
                continue
            right_hits = [
                hits[x]
                for x in right.get("account_ids", right.get("is_same_person_accounts", []))
                if x in hits
            ]
            reasons = []
            if {h.get("avatar") for h in left_hits if h.get("avatar")} & {
                h.get("avatar") for h in right_hits if h.get("avatar")
            }:
                reasons.append("same profile picture")
            if (
                left.get("name")
                and right.get("name")
                and SequenceMatcher(None, left["name"].casefold(), right["name"].casefold()).ratio()
                > 0.75
            ):
                reasons.append("similar display name (ambiguous)")
            if reasons:
                overlaps.append({"with": right.get("label"), "reasons": reasons})
        output.append({"label": left.get("label"), "overlaps": overlaps})
    return output


def build_cards(dossier) -> list[dict]:
    overlap = {x["label"]: x["overlaps"] for x in compare_identities(dossier)}
    return [
        {
            **identity,
            "aliases_detail": alias_variants(dossier, identity),
            "overlaps": overlap.get(identity.get("label"), []),
        }
        for identity in dossier.analysis.get("identities", [])
    ]


def disambiguation_question(dossier) -> str | None:
    identities = dossier.analysis.get("identities", [])
    return (
        None
        if len(identities) < 2
        else "Candidates are unresolved. Use evidence H03, compare H03 H07, pick A, merge A B, or split A H03."
    )


def _identity(dossier, label: str):
    key = label.strip().casefold()
    return next(
        (
            i
            for i in dossier.analysis.get("identities", [])
            if key in {str(i.get("label", "")).casefold(), str(i.get("id", "")).casefold()}
        ),
        None,
    )


def reconcile_analysis(dossier, analysis: dict) -> dict:
    """Preserve identity IDs, labels, selection and active manual constraints."""
    analysis = relabel(analysis)
    old = dossier.analysis.get("identities", [])
    # Search-result exclusions are analyst-visible collection state, not model
    # conclusions. Keep them when a fresh identity grouping is calculated.
    if dossier.analysis.get("rejected_matches"):
        analysis["rejected_matches"] = list(dossier.analysis["rejected_matches"])
    for current in analysis.get("identities", []):
        accounts = set(current.get("account_ids", []))
        previous = max(
            old, key=lambda x: len(accounts & set(x.get("account_ids", []))), default=None
        )
        if previous and accounts & set(previous.get("account_ids", [])):
            for key in ("id", "label", "display_label", "selected"):
                if key in previous:
                    current[key] = previous[key]
    identities = analysis.get("identities", [])
    for constraint in dossier.constraints:
        if not constraint.get("active", True):
            continue
        if constraint.get("type") == "selection":
            selected_accounts = set(constraint.get("account_ids", []))
            for identity in identities:
                identity["selected"] = bool(
                    selected_accounts & set(identity.get("account_ids", []))
                )
        elif constraint.get("type") == "merge":
            wanted = set(constraint.get("account_ids", []))
            matches = [i for i in identities if wanted & set(i.get("account_ids", []))]
            if len(matches) > 1:
                primary = matches[0]
                for other in matches[1:]:
                    primary["account_ids"] = list(
                        dict.fromkeys(primary["account_ids"] + other["account_ids"])
                    )
                    identities.remove(other)
                primary["is_same_person_accounts"] = primary["account_ids"]
                primary["status"] = "user-merged"
        elif constraint.get("type") == "split":
            account_id = constraint.get("account_id")
            for identity in list(identities):
                if (
                    account_id in identity.get("account_ids", [])
                    and len(identity["account_ids"]) > 1
                ):
                    identity["account_ids"].remove(account_id)
                    identity["is_same_person_accounts"] = identity["account_ids"]
                    identities.append(new_identity([account_id]))
    return _dedupe_membership(relabel(analysis))


async def pick(dossier, label: str) -> str:
    chosen = _identity(dossier, label)
    if not chosen:
        return f"no identity {label!r}"
    for identity in dossier.analysis.get("identities", []):
        identity["selected"] = identity is chosen
    dossier.constraints.append(
        {
            "id": f"constraint-{len(dossier.constraints) + 1}",
            "type": "selection",
            "identity_id": chosen["id"],
            "account_ids": chosen.get("account_ids", []),
            "active": True,
        }
    )
    dossier.record_action("pick", identity_id=chosen["id"])
    dossier.save()
    return (
        f"selected {chosen['label']}; selection records your decision and does not verify identity"
    )


async def merge(dossier, a: str, b: str) -> str:
    left, right = _identity(dossier, a), _identity(dossier, b)
    if not left or not right or left is right:
        return "couldn't find two distinct identities"
    left["account_ids"] = list(
        dict.fromkeys(left.get("account_ids", []) + right.get("account_ids", []))
    )
    left["is_same_person_accounts"] = left["account_ids"]
    left["status"] = "user-merged"
    left.setdefault("limitations", []).append(
        "Merged by the user; this is not independent verification."
    )
    dossier.analysis["identities"].remove(right)
    dossier.constraints.append(
        {
            "id": f"constraint-{len(dossier.constraints) + 1}",
            "type": "merge",
            "identity_ids": [left["id"], right["id"]],
            "account_ids": left["account_ids"],
            "active": True,
        }
    )
    dossier.record_action("merge", identity_ids=[left["id"], right["id"]])
    dossier.save()
    return f"merged {a} and {b} by user constraint; evidence status is unchanged"


async def split_out(dossier, label: str, account_ref: str) -> str:
    identity = _identity(dossier, label)
    account = dossier.account(account_ref) if hasattr(dossier, "account") else None
    if not account:
        matches = [
            h
            for h in dossier.all_accounts
            if h.get("platform", "").casefold() == account_ref.casefold()
        ]
        account = matches[0] if len(matches) == 1 else None
    if not identity or not account or account["account_id"] not in identity.get("account_ids", []):
        return f"{account_ref!r} is not part of {label}"
    identity["account_ids"].remove(account["account_id"])
    identity["is_same_person_accounts"] = identity["account_ids"]
    new = new_identity([account["account_id"]], account.get("display_name", ""))
    dossier.analysis["identities"].append(new)
    relabel(dossier.analysis)
    dossier.constraints.append(
        {
            "id": f"constraint-{len(dossier.constraints) + 1}",
            "type": "split",
            "from_identity": identity["id"],
            "account_id": account["account_id"],
            "active": True,
        }
    )
    dossier.record_action("split", identity_id=identity["id"], account_id=account["account_id"])
    dossier.save()
    return f"split {account['ref']} into {new['label']} by user constraint"


async def add_handle(dossier, handle: str, bus: Bus) -> str:
    handle = handle.strip().lstrip("@")
    existing_ids = {h["account_id"] for h in dossier.all_accounts}
    async with Http() as http:
        fresh = await enumerate_username(handle, bus, http)
        for hit in fresh:
            hit.matched_handle = handle
            hit.extra["matched_handle"] = handle
        await asyncio.gather(*(enrich_hit(http, hit, bus) for hit in fresh))
    pool = dossier.all_accounts + [h.to_dict() for h in fresh if h.account_id not in existing_ids]
    apply_assessments(dossier, pool)
    dossier.handles_tried = list(dict.fromkeys(dossier.handles_tried + [handle]))
    dossier.analysis = reconcile_analysis(
        dossier,
        await analyze(
            dossier.target,
            dossier.kind,
            dossier.hits,
            dossier.enrichment,
            bus,
            context=dossier.context,
            evidence_records=dossier.evidence_records,
        ),
    )
    dossier.record_action("add_handle", handle=handle)
    dossier.save()
    return f"checked {handle!r}; added {len({h['account_id'] for h in dossier.all_accounts} - existing_ids)} unique account(s)"


async def deepen(dossier, platform_or_ref: str, bus: Bus) -> str:
    from snoop.actions import deepen_account

    account = dossier.account(platform_or_ref)
    if not account:
        matches = [
            h
            for h in dossier.hits
            if h.get("platform", "").casefold() == platform_or_ref.casefold()
        ]
        if len(matches) != 1:
            return "use an account reference such as 'deepen H03' when a platform is missing or ambiguous"
        account = matches[0]
    return await deepen_account(dossier, account["ref"], bus)


async def add_context(dossier, fact: str, bus: Bus) -> str:
    normalized = normalize_context(dossier.context + [fact])
    if normalized == dossier.context:
        return "that context hint is already recorded; scores are unchanged"
    dossier.context = normalized
    apply_assessments(dossier, dossier.all_accounts)
    dossier.analysis = reconcile_analysis(
        dossier,
        await analyze(
            dossier.target,
            dossier.kind,
            dossier.hits,
            dossier.enrichment,
            bus,
            context=dossier.context,
            evidence_records=dossier.evidence_records,
        ),
    )
    dossier.record_action("context", value=normalized[-1])
    dossier.save()
    return f"added context {normalized[-1]!r}; re-scored with duplicate hints counted once"


async def ask(dossier, question: str) -> str:
    return await answer_question(dossier, question)


async def account_decision(dossier, ref: str, decision: str) -> str:
    account = dossier.account(ref)
    if not account or decision not in {"keep", "discard"}:
        return f"unknown account reference {ref!r}"
    dossier.constraints.append(
        {
            "id": f"constraint-{len(dossier.constraints) + 1}",
            "type": "account",
            "account_id": account["account_id"],
            "decision": decision,
            "active": True,
        }
    )
    apply_assessments(dossier, dossier.all_accounts)
    dossier.record_action(decision, account_id=account["account_id"])
    dossier.save()
    return f"{decision} constraint recorded for {account['ref']}; use undo to reverse it"


async def undo(dossier) -> str:
    constraint = next((c for c in reversed(dossier.constraints) if c.get("active", True)), None)
    if not constraint:
        return "no active user constraint to undo"
    constraint["active"] = False
    apply_assessments(dossier, dossier.all_accounts)
    dossier.record_action("undo", constraint_id=constraint["id"])
    dossier.save()
    return f"reversed {constraint['id']} ({constraint['type']})"
