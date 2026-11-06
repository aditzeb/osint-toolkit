"""Tests for the aggregator merge and conflict logic."""

from __future__ import annotations

from numint.core.aggregator import aggregate
from numint.core.models import ProviderResult
from numint.core.parser import parse_number


def _num():
    return parse_number("+14155552671")


def test_merge_keeps_all_conflicting_carriers_with_sources():
    results = [
        ProviderResult(source="a", ok=True, mapped={"carrier": "Verizon"}),
        ProviderResult(source="b", ok=True, mapped={"carrier": "AT&T"}),
    ]
    profile = aggregate(_num(), results)
    carriers = {a.value: a.source for a in profile.carriers}
    assert carriers == {"Verizon": "a", "AT&T": "b"}


def test_agreeing_sources_are_merged_into_one_attribute():
    results = [
        ProviderResult(source="a", ok=True, mapped={"carrier": "Verizon"}),
        ProviderResult(source="b", ok=True, mapped={"carrier": "verizon"}),
    ]
    profile = aggregate(_num(), results)
    assert len(profile.carriers) == 1
    assert "a" in profile.carriers[0].source and "b" in profile.carriers[0].source


def test_confidence_counts_agreement():
    results = [
        ProviderResult(source="a", ok=True, mapped={"line_type": "mobile"}),
        ProviderResult(source="b", ok=True, mapped={"line_type": "mobile"}),
        ProviderResult(source="c", ok=True, mapped={"line_type": "voip"}),
    ]
    profile = aggregate(_num(), results)
    assert profile.confidence["line_type"]["mobile"] == 2
    assert profile.confidence["line_type"]["voip"] == 1


def test_primary_carrier_is_most_common():
    results = [
        ProviderResult(source="a", ok=True, mapped={"carrier": "Verizon"}),
        ProviderResult(source="b", ok=True, mapped={"carrier": "Verizon"}),
        ProviderResult(source="c", ok=True, mapped={"carrier": "AT&T"}),
    ]
    profile = aggregate(_num(), results)
    # dedupe merges the two Verizon; most_common over distinct values still Verizon
    assert profile.primary_carrier() == "Verizon"


def test_risk_fields_are_captured_with_source():
    results = [
        ProviderResult(
            source="ipqs",
            ok=True,
            mapped={"fraud_score": 88, "spam": True, "active": False},
        )
    ]
    profile = aggregate(_num(), results)
    assert profile.risk.fraud_score.value == 88
    assert profile.risk.fraud_score.source == "ipqs"
    assert profile.risk.spam.value is True
    assert profile.risk.active.value is False


def test_failed_and_empty_results_are_ignored():
    results = [
        ProviderResult(source="a", ok=False, error="boom"),
        ProviderResult(source="b", ok=True, mapped={}),
        ProviderResult(source="c", ok=True, mapped={"carrier": "T-Mobile"}),
    ]
    profile = aggregate(_num(), results)
    assert [a.value for a in profile.carriers] == ["T-Mobile"]
