"""Search-engine dork links for a number.

`--dorking` opens the top few dork searches; `--dorking-all` opens every one.
A full scan lists them as text. Templates live in `data/dorking.yaml`. Like the
other link layers, this only builds URLs; it never scrapes or searches for you.
"""

from __future__ import annotations

import re
from functools import lru_cache
from importlib import resources
from urllib.parse import quote

import yaml

from .models import FootprintGroup, FootprintLink, ParsedNumber


@lru_cache(maxsize=1)
def _load_dorks() -> dict:
    with resources.files("numint.data").joinpath("dorking.yaml").open(
        "r", encoding="utf-8"
    ) as fh:
        return yaml.safe_load(fh) or {}


def _substitutions(number: ParsedNumber) -> dict[str, str]:
    nsn = re.sub(r"\D", "", number.national)
    return {
        "plus_enc": quote(number.e164, safe=""),
        "nat_enc": quote(number.national, safe=""),
        "natdigits": nsn,
        "area": nsn[0:3],
        "prefix": nsn[3:6],
        "suffix": nsn[6:10],
        "digits": number.digits,
        "e164": number.e164,
    }


def _fill(template: str, subs: dict[str, str]) -> str | None:
    try:
        return template.format(**subs)
    except (KeyError, IndexError):
        return None


def build_dorking(
    number: ParsedNumber, *, top_only: bool = False
) -> list[FootprintGroup]:
    """Return the search-engine dork links for `number`.

    `top_only=True` keeps just the handful of best dorks (what `--dorking`
    opens); the default returns every dork (what `--dorking-all` opens and what
    a full scan lists).
    """
    subs = _substitutions(number)
    links: list[FootprintLink] = []
    for entry in _load_dorks().get("dorks", []) or []:
        if top_only and not entry.get("top"):
            continue
        url = _fill(entry.get("template", ""), subs)
        if url:
            links.append(FootprintLink(label=entry["label"], url=url))
    if not links:
        return []
    return [FootprintGroup(category="Search Engine Dorks", links=links)]


def dorking_urls(number: ParsedNumber, *, top_only: bool = False) -> list[str]:
    """Flat list of dork URLs (used by the `--dorking` tool)."""
    return [
        link.url
        for group in build_dorking(number, top_only=top_only)
        for link in group.links
    ]
