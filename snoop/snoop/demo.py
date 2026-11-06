"""Deterministic, clearly labelled synthetic cases for demos and offline training."""

from __future__ import annotations

import copy

from snoop.model import ensure_account, evidence_record, utcnow
from snoop.pipeline import Dossier, apply_assessments
from snoop.session import relabel


def create_demo_cases() -> dict:
    context = ["robotics", "Berlin"]
    accounts = [
        {
            "platform": "GitHub",
            "url": "https://github.com/alexexample",
            "canonical_url": "https://github.com/alexexample",
            "display_name": "Alex Example",
            "bio": "Robotics builder in Berlin",
            "location": "Berlin",
            "links": ["https://dev.to/alexexample"],
            "avatar": "",
            "joined": "2020-01-10",
            "extra": {"matched_handle": "alexexample"},
            "matched_handle": "alexexample",
            "discovery_source": "synthetic-fixture",
        },
        {
            "platform": "Dev.to",
            "url": "https://dev.to/alexexample",
            "canonical_url": "https://dev.to/alexexample",
            "display_name": "Alex Example",
            "bio": "Robotics notes",
            "location": "Berlin",
            "links": ["https://github.com/alexexample"],
            "avatar": "",
            "joined": "2021-03-04",
            "extra": {"matched_handle": "alexexample"},
            "matched_handle": "alexexample",
            "discovery_source": "synthetic-fixture-follow",
        },
        {
            "platform": "Steam",
            "url": "https://steamcommunity.com/id/alexexample",
            "canonical_url": "https://steamcommunity.com/id/alexexample",
            "display_name": "Morgan Other",
            "bio": "Music collector",
            "location": "Oslo",
            "links": [],
            "avatar": "",
            "extra": {"matched_handle": "alexexample"},
            "matched_handle": "alexexample",
            "discovery_source": "synthetic-fixture",
        },
    ]
    used = set()
    for account in accounts:
        ensure_account(account, used)
        used.add(account["ref"])
    before = Dossier(
        "synthetic-demo-before",
        "Alex Example",
        "name",
        utcnow(),
        context=context,
        handles_tried=["alexexample"],
    )
    counts = apply_assessments(before, accounts)
    anchor_record = evidence_record(
        account_id=before.hits[0]["account_id"],
        claim="user-supplied-anchor",
        source_url=before.hits[0]["canonical_url"],
        value=before.hits[0]["canonical_url"],
        method="synthetic-user-input",
        kind="user_hint",
        strength=0,
        limitation="Synthetic anchor establishes demo scope, not identity ownership.",
    )
    before.evidence_records.append(anchor_record)
    before.hits[0]["evidence"].append(
        {
            "points": 0,
            "label": "anchor",
            "detail": "synthetic user-provided anchor",
            "evidence_id": anchor_record["id"],
            "source_url": before.hits[0]["canonical_url"],
            "dependence": anchor_record["id"],
            "supports": None,
            "limitation": anchor_record["limitation"],
        }
    )
    linked_ids = [h["account_id"] for h in before.hits]
    before.analysis = relabel(
        {
            "identities": [
                {
                    "id": "id_synthetic_alex",
                    "label": "A",
                    "name": "Alex Example",
                    "account_ids": linked_ids,
                    "evidence_score": 80,
                    "status": "supported",
                    "selected": True,
                    "reasoning": "Synthetic profiles explicitly cross-link and independently match labelled context.",
                    "limitations": ["Synthetic fixture; not a real person."],
                }
            ],
            "summary": "Synthetic fixture: two cross-linked profiles support one identity; a namesake is conflicting.",
            "key_findings": [],
            "contradictions": [],
            "next_steps": [],
        }
    )
    before.hits[0]["enrichment"] = {
        "events": [
            {
                "event": "synthetic repository published",
                "event_time": "2024-04-15",
                "retrieved_at": utcnow(),
                "source_url": "https://github.com/alexexample/public-demo",
            }
        ],
        "summary": "1 synthetic public repository",
        "account_id": before.hits[0]["account_id"],
    }
    before.deep[before.hits[0]["account_id"]] = before.hits[0]["enrichment"]
    before.stats = {
        "accounts_returned": 3,
        "linked": 2,
        "discarded": 1,
        **counts,
        "attempted": 0,
        "completed": 0,
        "fixture": True,
    }
    before.record_action("load_fixture", label="synthetic; no network requests")
    before.save()

    after = copy.deepcopy(before)
    after.id = "synthetic-demo-after"
    after.created = after.updated = utcnow()
    removed = after.hits.pop(1)
    removed["observation_status"] = "not_found"
    after.discarded.append(removed)
    after.evidence_records = [
        r for r in after.evidence_records if r.get("account_id") != removed["account_id"]
    ]
    after.analysis["identities"][0]["account_ids"] = [after.hits[0]["account_id"]]
    after.analysis["identities"][0]["is_same_person_accounts"] = [after.hits[0]["account_id"]]
    after.record_action(
        "synthetic_privacy_cleanup",
        account_id=removed["account_id"],
        note="Fixture says not found; this is not inferred from a failed fetch.",
    )
    after.save()
    return {
        "fixture": True,
        "network_requests": 0,
        "before": before.id,
        "after": after.id,
        "start": "snoop resume synthetic-demo-before",
        "notice": "All people, URLs, results, and cleanup events in these cases are synthetic.",
    }
