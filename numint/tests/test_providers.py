"""Tests for the provider interface and a representative provider, using mocks."""

from __future__ import annotations

import httpx
import pytest

from numint.core.config import Settings
from numint.core.parser import parse_number
from numint.core.registry import discover
from numint.providers.base import BaseProvider
from numint.providers.numverify import NumverifyProvider
from numint.providers.offline import OfflineProvider


class _FakeSettings(Settings):
    def __init__(self, values: dict):
        self._values = values
        self._file = {}

    def get(self, key, default=None):
        return self._values.get(key, default)


def test_discover_finds_all_providers():
    classes = discover()
    names = {c.name for c in classes}
    assert {"offline", "numverify", "veriphone", "ipqs"} <= names


def test_offline_provider_is_always_configured():
    prov = OfflineProvider(_FakeSettings({}))
    assert prov.is_configured() is True


def test_key_provider_requires_key():
    assert NumverifyProvider(_FakeSettings({})).is_configured() is False
    assert (
        NumverifyProvider(_FakeSettings({"NUMVERIFY_API_KEY": "x"})).is_configured()
        is True
    )


@pytest.mark.asyncio
async def test_offline_lookup_maps_fields():
    prov = OfflineProvider(_FakeSettings({}))
    number = parse_number("+14155552671")
    async with httpx.AsyncClient() as client:
        res = await prov.lookup(number, client)
    assert res.ok
    assert res.mapped["valid"] is True
    assert res.mapped["country_iso"] == "US"
    assert res.elapsed_ms is not None


@pytest.mark.asyncio
async def test_provider_error_is_swallowed_into_result():
    class Boom(BaseProvider):
        name = "boom"
        requires_key = False

        async def _lookup(self, number, client):
            raise RuntimeError("kaboom")

    number = parse_number("+14155552671")
    async with httpx.AsyncClient() as client:
        res = await Boom(_FakeSettings({})).lookup(number, client)
    assert res.ok is False
    assert "kaboom" in res.error


@pytest.mark.asyncio
async def test_numverify_maps_response():
    prov = NumverifyProvider(_FakeSettings({"NUMVERIFY_API_KEY": "k"}))
    number = parse_number("+14155552671")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "valid": True,
                "carrier": "AT&T Mobility",
                "line_type": "mobile",
                "location": "Novato",
                "country_name": "United States",
                "country_code": "US",
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        res = await prov.lookup(number, client)
    assert res.ok
    assert res.mapped["carrier"] == "AT&T Mobility"
    assert res.mapped["line_type"] == "mobile"
    assert res.mapped["country_iso"] == "US"
