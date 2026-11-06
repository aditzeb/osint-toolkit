"""Aggregator - merges provider results into one unified profile.

Design rule: when sources disagree (carrier, line type, location) we KEEP every
value with its source tag rather than silently picking a winner. A confidence
signal reports how many sources agree on each field.
"""

from __future__ import annotations

from collections import Counter

from .models import (
    Attribute,
    ParsedNumber,
    Profile,
    ProviderResult,
    RiskProfile,
)

# mapped-key -> Profile list attribute that collects Attributes
_MULTI_FIELDS = {
    "carrier": "carriers",
    "line_type": "line_types",
    "location": "locations",
    "country": "countries",
}


def _dedupe_attrs(attrs: list[Attribute]) -> list[Attribute]:
    """Collapse identical (value) attributes, merging their sources in order."""
    seen: dict[str, Attribute] = {}
    for a in attrs:
        key = str(a.value).strip().lower()
        if key in seen:
            # append source if this exact value was seen from another provider
            existing = seen[key]
            if a.source not in existing.source:
                existing.source = f"{existing.source}, {a.source}"
        else:
            seen[key] = Attribute(value=a.value, source=a.source)
    return list(seen.values())


def aggregate(number: ParsedNumber, results: list[ProviderResult]) -> Profile:
    """Merge normalized provider results into a `Profile`."""
    profile = Profile(input=number)

    raw_multi: dict[str, list[Attribute]] = {f: [] for f in _MULTI_FIELDS}
    validity: list[Attribute] = []
    risk = RiskProfile()

    for res in results:
        if not res.ok or not res.mapped:
            continue
        m = res.mapped
        src = res.source

        for mapped_key in _MULTI_FIELDS:
            val = m.get(mapped_key)
            if val:
                raw_multi[mapped_key].append(Attribute(value=val, source=src))

        if "valid" in m and m["valid"] is not None:
            validity.append(Attribute(value=bool(m["valid"]), source=src))

        # Risk fields - first non-null wins for the slot, but tagged by source.
        if m.get("fraud_score") is not None and risk.fraud_score is None:
            risk.fraud_score = Attribute(value=m["fraud_score"], source=src)
        if m.get("spam") is not None and risk.spam is None:
            risk.spam = Attribute(value=bool(m["spam"]), source=src)
        if m.get("disposable") is not None and risk.disposable is None:
            risk.disposable = Attribute(value=bool(m["disposable"]), source=src)
        if m.get("voip") is not None and risk.voip is None:
            risk.voip = Attribute(value=bool(m["voip"]), source=src)
        if m.get("active") is not None and risk.active is None:
            risk.active = Attribute(value=bool(m["active"]), source=src)
        if m.get("recent_abuse") is not None and risk.recent_abuse is None:
            risk.recent_abuse = Attribute(
                value=bool(m["recent_abuse"]), source=src
            )

    for mapped_key, profile_attr in _MULTI_FIELDS.items():
        deduped = _dedupe_attrs(raw_multi[mapped_key])
        setattr(profile, profile_attr, deduped)

    profile.validity = _dedupe_attrs(validity)
    profile.risk = risk
    profile.confidence = _confidence(raw_multi, validity)
    return profile


def _confidence(
    raw_multi: dict[str, list[Attribute]], validity: list[Attribute]
) -> dict[str, dict[str, int]]:
    """For each field, count how many sources reported each distinct value."""
    out: dict[str, dict[str, int]] = {}
    for mapped_key, attrs in raw_multi.items():
        counts = Counter(str(a.value).strip() for a in attrs if a.value)
        if counts:
            out[mapped_key] = dict(counts)
    val_counts = Counter(str(a.value) for a in validity)
    if val_counts:
        out["valid"] = dict(val_counts)
    return out
