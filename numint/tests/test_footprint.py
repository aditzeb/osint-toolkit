"""Tests for the footprint link builder (URL generation only)."""

from __future__ import annotations

from numint.core.footprint import build_footprint
from numint.core.parser import parse_number


def test_footprint_groups_and_substitution():
    number = parse_number("+14155552671")
    groups = build_footprint(number)
    cats = {g.category for g in groups}
    assert "Search Engines" in cats
    assert "Messaging Presence" in cats

    all_urls = [link.url for g in groups for link in g.links]
    # wa.me uses digits without '+'
    assert any("wa.me/14155552671" in u for u in all_urls)
    # search engines encode the E.164
    assert any("google.com/search" in u for u in all_urls)


def test_footprint_never_empty_for_valid_number():
    number = parse_number("+442079460958")
    groups = build_footprint(number)
    assert groups and all(g.links for g in groups)
