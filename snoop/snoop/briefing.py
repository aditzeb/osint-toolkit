"""A source-grounded investigation briefing shared by web, CLI and checkpoints."""

from __future__ import annotations

from collections import Counter
from urllib.parse import urlsplit


def build_briefing(dossier) -> dict:
    from snoop.interview import subject_status
    from snoop.workflow import PRESETS, normalize_preset

    def eligibility(_dossier, _hit) -> str:
        return "exact"

    def strict(_dossier) -> bool:
        return False

    budgets = PRESETS[normalize_preset(dossier.workflow.get("preset"))]
    spent = dossier.workflow.get("spent", {})
    sources = dossier.sources
    read = [s for s in sources if s.get("outcome") == "found" and not (s.get("extra") or {}).get("snippet_only")]
    blocked = [s for s in sources if s.get("outcome") in {"blocked", "rate_limited", "unavailable", "timeout"}]
    evidence = [e for e in dossier.evidence_records if e.get("source_url") and e.get("supports") is True]
    pending = sorted([l for l in dossier.leads if l.get("status") == "pending"], key=lambda l: -float(l.get("score", 0)))
    gaps = []
    if not dossier.queries:
        gaps.append("No web search has been recorded.")
    if not read:
        gaps.append("No successfully read original source is available yet.")
    if blocked:
        gaps.append(f"{len(blocked)} source(s) remain unavailable; their snippets are leads only.")
    unknown = sum(eligibility(dossier, h) == "unknown" for h in dossier.hits)
    if unknown:
        gaps.append(f"{unknown} account(s) expose no readable name and need corroboration.")
    if subject_status(dossier)["status"] != "supported":
        gaps.append("The subject's identity has not been verified by corroborating evidence.")
    return {
        "subject": subject_status(dossier),
        "exact_name": strict(dossier),
        "status": dossier.workflow.get("status", "idle"),
        "rounds": len(dossier.workflow.get("checkpoints", [])),
        "coverage": {
            "queries": len(dossier.queries), "sources_read": len(read),
            "source_domains": len({urlsplit(s.get("url", "")).hostname for s in read}),
            "unavailable_sources": len(blocked), "evidence_records": len(dossier.evidence_records),
            "candidate_accounts": len(dossier.hits) - unknown, "unresolved_accounts": unknown,
            "excluded_accounts": len(dossier.discarded),
        },
        "source_outcomes": dict(Counter(s.get("outcome", "unknown") for s in sources)),
        "resources": [{"name": key, "used": spent.get(key, 0), "limit": budgets[key]}
                      for key in ("searches", "page_fetches", "account_probes", "model_calls")],
        "observations": [{"id": e["id"], "claim": e.get("claim", ""),
                          "excerpt": e.get("excerpt", ""), "source_url": e["source_url"],
                          "limitation": e.get("limitation", "")} for e in evidence[-12:]],
        "gaps": gaps,
        "next_actions": [{"id": l["id"], "purpose": l["purpose"], "expected": l.get("expected", ""),
                          "type": l["type"], "clues": l.get("clues", [])} for l in pending[:8]],
        "frontier": dict(Counter(l.get("status", "pending") for l in dossier.leads)),
        "question": dossier.pending_question or None,
        "answers": dossier.interview,
        "ai_review": dossier.workflow.get("last_ai_review", {}),
    }


def render_briefing(data: dict) -> str:
    c = data["coverage"]
    lines = [f"Investigation briefing: {data['subject']['name']} ({data['status']})",
             (f"{c['queries']} queries; {c['sources_read']} sources read across {c['source_domains']} domains; "
             f"{c['evidence_records']} evidence records; {c['candidate_accounts']} candidates; "
             f"{c['excluded_accounts']} excluded accounts.")]
    lines.extend(f"Gap: {gap}" for gap in data["gaps"])
    lines.extend(f"Observed [{e['id']}]: {e['claim']} — {e['source_url']}" for e in data["observations"])
    lines.extend(f"Next: {a['purpose']} — {a['expected']}" for a in data["next_actions"])
    if data["question"]:
        lines.append("Question: " + data["question"]["text"])
    return "\n".join(lines)
