"""Prompt construction for the AI intelligence layer.

The system prompt enforces the hard rule: the model may ONLY reason over and
summarize the data the tool collected. It must never invent names, identities,
addresses or any personal detail. Unknown means unknown.
"""

from __future__ import annotations

import json

from ..core.models import Profile

SYSTEM_PROMPT = """\
You are the analysis layer of Numint, an authorized-use phone-number OSINT tool.

HARD RULES - follow them exactly:
- Reason ONLY over the JSON data provided to you in the user message. That data
  is the complete set of facts the tool collected.
- NEVER invent, guess, or infer names, identities, addresses, emails, social
  accounts, or any personal detail that is not explicitly present in the data.
- When a fact is not in the data, state that it is unknown. Do not speculate
  about a real person's identity.
- You may explain likely technical reasons for conflicting technical signals
  (e.g. number porting explaining carrier disagreement) - this is about the
  number, not about identifying a person.
- Be concise, neutral and professional. No hype, no fabricated confidence.

Return your analysis as strict JSON with exactly these string fields:
  "summary": a short natural-language brief of the findings,
  "conflicts": explanation of any disagreements between sources (or "None"),
  "risk_read": plain-English reading of fraud/spam/reputation signals,
  "next_steps": which footprint links / actions are most promising and why.
Output ONLY the JSON object, nothing else.
"""

ASK_SYSTEM_PROMPT = """\
You are the analysis layer of Numint, an authorized-use phone-number OSINT tool.
Answer the user's question STRICTLY from the JSON data provided. Never invent
names, identities or personal details. If the data does not contain the answer,
say so plainly. Return a short, direct plain-text answer (no JSON).
"""


def _profile_facts(profile: Profile) -> dict:
    """Compact, model-friendly view of everything the tool collected."""
    return {
        "input": {
            "e164": profile.input.e164,
            "national": profile.input.national,
            "country": profile.input.country_name,
            "country_iso": profile.input.country_iso,
            "region": profile.input.region,
            "is_valid": profile.input.is_valid,
            "is_possible": profile.input.is_possible,
            "type": profile.input.number_type.value,
            "timezones": profile.input.timezones,
        },
        "carriers": [{"value": a.value, "source": a.source} for a in profile.carriers],
        "line_types": [
            {"value": a.value, "source": a.source} for a in profile.line_types
        ],
        "locations": [
            {"value": a.value, "source": a.source} for a in profile.locations
        ],
        "validity": [
            {"value": a.value, "source": a.source} for a in profile.validity
        ],
        "risk": {
            k: (None if v is None else {"value": v.value, "source": v.source})
            for k, v in {
                "fraud_score": profile.risk.fraud_score,
                "spam": profile.risk.spam,
                "disposable": profile.risk.disposable,
                "voip": profile.risk.voip,
                "active": profile.risk.active,
                "recent_abuse": profile.risk.recent_abuse,
            }.items()
        },
        "confidence": profile.confidence,
        "footprint": [
            {"category": g.category, "links": [link.label for link in g.links]}
            for g in profile.footprint
        ],
        "providers": [
            {"name": p.name, "status": p.status.value, "reason": p.reason}
            for p in profile.providers
        ],
    }


def build_analysis_user_prompt(profile: Profile) -> str:
    return (
        "Here is the data Numint collected. Analyze ONLY this data.\n\n"
        + json.dumps(_profile_facts(profile), indent=2, default=str)
    )


def build_ask_user_prompt(profile: Profile, question: str) -> str:
    return (
        f"Question: {question}\n\n"
        "Answer strictly from this collected data:\n\n"
        + json.dumps(_profile_facts(profile), indent=2, default=str)
    )
