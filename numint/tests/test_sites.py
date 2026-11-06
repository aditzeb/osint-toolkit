"""Tests for the lookup-site and dorking builders (URL generation only)."""

from __future__ import annotations

from numint.core.dorking import build_dorking, dorking_urls
from numint.core.lookup import site_urls
from numint.core.parser import parse_number

US = "+14155550123"


# --- lookup sites ---------------------------------------------------------
def test_lookup_top_is_five_or_fewer():
    urls = site_urls(parse_number(US))  # top_only=True by default
    assert 0 < len(urls) <= 5
    assert any("thatsthem.com" in u for u in urls)


def test_lookup_all_is_larger_than_top():
    number = parse_number(US)
    assert len(site_urls(number, top_only=False)) > len(site_urls(number))


def test_lookup_splits_us_number():
    urls = site_urls(parse_number(US), top_only=False)
    assert any("thatsthem.com/phone/415-555-0123" in u for u in urls)


def test_lookup_skips_us_only_sites_for_other_countries():
    urls = site_urls(parse_number("+442079460958"), top_only=False)
    assert not any("thatsthem" in u for u in urls)
    assert any("sync.me" in u or "truecaller" in u for u in urls)


def test_no_sketchy_or_dead_lookup_sites():
    urls = site_urls(parse_number(US), top_only=False)
    for bad in ("dehashed", "checkleaked", "americaphonebook", "oldphonebook"):
        assert not any(bad in u for u in urls), bad


# --- dorking (separate from lookup) ---------------------------------------
def test_dorking_top_is_five_or_fewer():
    urls = dorking_urls(parse_number(US), top_only=True)
    assert 0 < len(urls) <= 5
    assert any("google.com/search" in u for u in urls)


def test_dorking_all_is_larger_than_top():
    number = parse_number(US)
    top = dorking_urls(number, top_only=True)
    everything = dorking_urls(number, top_only=False)
    assert len(everything) > len(top)


def test_dorking_group_titled():
    groups = build_dorking(parse_number(US))
    assert groups and groups[0].category == "Search Engine Dorks"


def test_dorking_and_lookup_are_disjoint():
    number = parse_number(US)
    lookup = set(site_urls(number, top_only=False))
    dorks = set(dorking_urls(number, top_only=False))
    assert not (lookup & dorks)
