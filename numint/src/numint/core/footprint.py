"""OSINT footprint layer - builds investigation links only.

This layer NEVER scrapes, automates against, or bypasses any third-party site.
It only fills URL templates so an investigator can open them manually. Templates
live in `data/footprint_links.yaml` and can be extended with no code changes.
"""

from __future__ import annotations

import re
from functools import lru_cache
from importlib import resources
from urllib.parse import quote

import yaml

from .models import FootprintGroup, FootprintLink, ParsedNumber

_CATEGORY_TITLES = {
    "search_engines": "Search Engines",
    "messaging": "Messaging Presence",
    "reverse_lookup": "Reverse Lookup / Caller-ID",
    "social": "Social Platforms",
}


@lru_cache(maxsize=1)
def _load_templates() -> dict:
    with resources.files("numint.data").joinpath(
        "footprint_links.yaml"
    ).open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _substitutions(number: ParsedNumber) -> dict[str, str]:
    natdigits = re.sub(r"\D", "", number.national)
    return {
        "e164": number.e164,
        "digits": number.digits,
        "national": number.national,
        "natdigits": natdigits,
        "plus_enc": quote(number.e164, safe=""),
        "country_iso": (number.country_iso or "").lower(),
    }


def _fill(template: str, subs: dict[str, str]) -> str | None:
    try:
        return template.format(**subs)
    except (KeyError, IndexError):
        return None


def build_footprint(number: ParsedNumber) -> list[FootprintGroup]:
    """Return grouped, ready-to-open investigation links for `number`."""
    templates = _load_templates()
    subs = _substitutions(number)
    groups: list[FootprintGroup] = []

    for category, entries in templates.items():
        links: list[FootprintLink] = []
        for entry in entries or []:
            url = _fill(entry.get("template", ""), subs)
            if url:
                links.append(FootprintLink(label=entry["label"], url=url))
        if links:
            groups.append(
                FootprintGroup(
                    category=_CATEGORY_TITLES.get(category, category),
                    links=links,
                )
            )
    return groups
