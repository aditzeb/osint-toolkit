"""Ranked, deduplicated lead queue persisted inside the case file.

Leads are typed investigation intentions with a user-visible purpose, an
expected useful outcome, and a lifecycle: pending -> running -> explored |
deferred | rejected (with a recorded reason). Equivalent queries, mirrored
pages and repeated account checks collapse onto one entry so the same source
is never counted twice.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from snoop.model import canonical_url, lead_record, utcnow

LEAD_TYPES = {
    "web_search",
    "read_source",
    "crawl_site",
    "check_account",
    "probe_handles",
    "expand_links",
    "read_document",
    "archive_lookup",
    "domain_lookup",
    "image_clues",
    "model_analysis",
    "import_lead",
}

OPEN_STATUSES = {"pending", "running"}

# Rejections that encode a decision, not a lack of motivation.
POLICY_REJECTIONS = (
    "superseded",
    "not eligible",
    "already collected",
    "not a supported",
    "excluded",
    "not relevant",
)

# Relative execution cost of one lead, used when ranking the frontier.
BASE_COST = {
    "web_search": 2.0,
    "read_source": 1.0,
    "crawl_site": 3.0,
    "check_account": 1.0,
    "probe_handles": 3.0,
    "expand_links": 2.0,
    "read_document": 2.0,
    "archive_lookup": 1.5,
    "domain_lookup": 1.5,
    "image_clues": 2.0,
    "model_analysis": 6.0,
    "import_lead": 0.5,
}


def _norm_query(query: str) -> str:
    return re.sub(r"\s+", " ", (query or "").strip()).casefold()


def equivalence_args(lead_type: str, args: dict) -> dict:
    """Normalised argument view used to decide whether two leads are the same."""
    args = dict(args or {})
    if lead_type == "web_search":
        args["query"] = _norm_query(str(args.get("query", "")))
        args.setdefault("engine", "")
        args["engine"] = str(args["engine"]).casefold()
        args.pop("page", None)
        args.pop("purpose", None)
    elif lead_type in {
        "read_source",
        "crawl_site",
        "read_document",
        "check_account",
        "archive_lookup",
        "image_clues",
    }:
        url = str(args.get("url", ""))
        args["url"] = canonical_url(url) or url
    elif lead_type == "probe_handles":
        args["handles"] = sorted({h.casefold().lstrip("@") for h in args.get("handles", [])})
    elif lead_type == "domain_lookup":
        args["domain"] = str(args.get("domain", "")).casefold().rstrip(".")
    return args


def _dedup_key(lead_type: str, args: dict) -> str:
    import json

    return lead_type + "|" + json.dumps(equivalence_args(lead_type, args), sort_keys=True)


def _is_same_host_mirror(left: str, right: str) -> bool:
    lh = (urlsplit(left).hostname or "").removeprefix("www.").casefold()
    rh = (urlsplit(right).hostname or "").removeprefix("www.").casefold()
    return lh == rh


class LeadQueue:
    """Frontier of the investigation, stored on the dossier."""

    def __init__(self, dossier):
        self.dossier = dossier

    def _index(self) -> dict[str, dict]:
        return {lead.get("id"): lead for lead in self.dossier.leads}

    def add(
        self,
        lead_type: str,
        args: dict,
        purpose: str,
        expected: str = "",
        *,
        clues: list[str] | None = None,
        origin: str = "planner",
        score: float = 0.0,
        reason: str = "",
        parent: str = "",
    ) -> dict | None:
        if lead_type not in LEAD_TYPES or not purpose.strip():
            return None
        args = equivalence_args(lead_type, args)
        key = _dedup_key(lead_type, args)
        existing = next((l for l in self.dossier.leads if _dedup_key(l["type"], l["args"]) == key), None)
        if existing:
            previous = float(existing.get("score", 0))
            existing["score"] = max(previous, float(score))
            for clue in clues or []:
                if clue and clue not in existing["clues"]:
                    existing["clues"].append(clue)
            # A later, better-motivated duplicate can revive a rejected lead
            # once — but never one rejected by policy (superseded spelling,
            # excluded candidate, already-read source, unsupported URL).
            reason_text = str(existing.get("reason", ""))
            if (
                existing.get("status") == "rejected"
                and float(score) > previous
                and not existing.get("reopened")
                and not any(marker in reason_text for marker in POLICY_REJECTIONS)
            ):
                existing["status"] = "pending"
                existing["reason"] = "reopened by a stronger motivation"
                existing["reopened"] = True
            existing["updated_at"] = utcnow()
            return existing
        lead = lead_record(
            lead_type=lead_type,
            args=args,
            purpose=purpose,
            expected=expected,
            clues=clues,
            origin=origin,
            score=score,
            status="pending",
            reason=reason,
        )
        if parent:
            lead["parent"] = parent
        self.dossier.leads.append(lead)
        return lead

    def next(self) -> dict | None:
        pending = [l for l in self.dossier.leads if l.get("status") == "pending"]
        if not pending:
            return None
        pending.sort(key=lambda l: (-float(l.get("score", 0)), l.get("created_at", "")))
        return pending[0]

    def mark(self, lead_id: str, status: str, reason: str = "") -> None:
        for lead in self.dossier.leads:
            if lead.get("id") == lead_id:
                lead["status"] = status
                lead["reason"] = reason or lead.get("reason", "")
                lead["updated_at"] = utcnow()
                return

    def skip_duplicate_sources(self, visited_urls: set[str]) -> int:
        """Reject pending page-read leads whose canonical URL is already read."""
        rejected = 0
        canonical_visited = {canonical_url(u) for u in visited_urls}
        for lead in self.dossier.leads:
            if lead.get("status") != "pending" or lead["type"] not in {
                "read_source",
                "crawl_site",
                "read_document",
                "check_account",
            }:
                continue
            url = canonical_url(str(lead["args"].get("url", "")))
            if url and url in canonical_visited:
                lead["status"] = "rejected"
                lead["reason"] = "source already collected in this case"
                lead["updated_at"] = utcnow()
                rejected += 1
        return rejected

    def pending(self) -> list[dict]:
        return [l for l in self.dossier.leads if l.get("status") == "pending"]

    def stats(self) -> dict:
        out: dict[str, int] = {}
        for lead in self.dossier.leads:
            out[lead.get("status", "pending")] = out.get(lead.get("status", "pending"), 0) + 1
        out["total"] = len(self.dossier.leads)
        return out

    def frontier(self) -> list[dict]:
        """The remaining work, saved for continuation when a run stops."""
        return [
            {
                "id": l["id"],
                "type": l["type"],
                "args": l["args"],
                "purpose": l["purpose"],
                "expected": l.get("expected", ""),
                "score": l.get("score", 0),
            }
            for l in self.pending()
        ]
