"""Tests for offline number parsing."""

from __future__ import annotations

import pytest

from numint.core.models import NumberType
from numint.core.parser import ParseError, parse_number


def test_parse_valid_us_number():
    p = parse_number("+14155552671")
    assert p.e164 == "+14155552671"
    assert p.country_code == 1
    assert p.country_iso == "US"
    assert p.is_valid
    assert p.is_possible
    assert "America/Los_Angeles" in p.timezones or p.timezones


def test_parse_national_with_region():
    p = parse_number("020 7946 0958", default_region="GB")
    assert p.country_code == 44
    assert p.country_iso == "GB"
    assert p.is_valid


def test_bare_international_without_plus_is_forgiving():
    p = parse_number("14155552671")
    assert p.country_code == 1
    assert p.e164 == "+14155552671"


def test_number_type_mapping_mobile():
    p = parse_number("+447911123456")  # UK mobile range
    assert p.number_type in (NumberType.MOBILE, NumberType.FIXED_OR_MOBILE)


def test_formats_present():
    p = parse_number("+14155552671")
    assert p.national
    assert p.international
    assert p.rfc3966.startswith("tel:")


def test_empty_raises():
    with pytest.raises(ParseError):
        parse_number("   ")


def test_garbage_raises():
    with pytest.raises(ParseError):
        parse_number("not-a-number-at-all")
