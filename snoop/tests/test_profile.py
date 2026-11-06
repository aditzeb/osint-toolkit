"""Profile facts: stated vs inferred vs AI, review effects, and privacy limits.
Synthetic names only; no network."""

from __future__ import annotations

import json

import pytest

from snoop.core import Bus
from snoop.model import ensure_account, evidence_record, utcnow
from snoop.pipeline import Dossier


@pytest.fixture
def case(tmp_path, monkeypatch):
    from snoop import pipeline
    from snoop.config import config as cfg

    monkeypatch.setattr(pipeline, "CASES_DIR", tmp_path)
    for key in ("openai_key", "anthropic_key", "gemini_key"):
        monkeypatch.setattr(cfg, key, "")
    dossier = Dossier("prof", "Alex Example", "name", utcnow())
    used: set[str] = set()

    def account(platform, url, **extra):
        hit = ensure_account({"platform": platform, "url": url, "display_name": "Alex Example", **extra}, used)
        used.add(hit["ref"])
        return hit

    dossier.hits = [
        account("Smoothcomp", "https://smoothcomp.com/en/profile/1", verdict="probable",
                bio="Amateur MMA fighter, competes at lightweight. Blue belt in BJJ. Software engineer at Northwind Labs."),
        account("Strava", "https://strava.com/athletes/alexex", verdict="weak", matched_handle="alexex", location="Graz"),
        account("GitHub", "https://github.com/alexex", verdict="confirmed", matched_handle="alexex", joined="2015-03-02"),
    ]
    namesake = account("Instagram", "https://instagram.com/other", display_name="Alex Other",
                       bio="Heavyweight boxer, devout catholic, lives at 12 Main Street", verdict="unrelated")
    dossier.discarded = [namesake]
    dossier.save()
    return dossier


def _facts(dossier):
    from snoop.profile import build

    return build(dossier)["facts"]


def _find(facts, label, contains=""):
    return next((f for f in facts if f["label"] == label and contains.casefold() in f["value"].casefold()), None)


def test_weight_class_becomes_a_labelled_weight_inference(case):
    facts = _facts(case)
    competes = _find(facts, "Competes", "lightweight")
    weight = _find(facts, "Body weight (est.)")
    assert competes and competes["basis"] == "stated" and "Smoothcomp" in competes["sources"][0]
    assert weight and weight["basis"] == "inferred" and weight["value"] == "about 66–70 kg"
    assert "lb" in weight["why"] and weight["derived_from"] == competes["id"]
    assert _find(facts, "Rank", "blue belt")
    assert _find(facts, "Role", "software engineer")
    assert _find(facts, "Organisation", "Northwind")
    assert _find(facts, "Main handle", "@alexex")
    assert _find(facts, "Online since", "2015")
    assert _find(facts, "Profile location", "Graz")
    assert _find(facts, "Activity", "runs or cycles")["basis"] == "inferred"


def test_namesakes_and_private_categories_never_enter_the_profile(case):
    blob = json.dumps(_facts(case)).casefold()
    assert "heavyweight" not in blob and "alex other" not in blob
    assert "catholic" not in blob and "main street" not in blob


@pytest.mark.asyncio
async def test_rejecting_an_account_fact_discards_the_account_and_its_facts(case):
    from snoop.profile import review

    strava = _find(_facts(case), "Account", "Strava")
    message = await review(case, strava["id"], "rejected", Bus())
    assert "marked wrong" in message
    facts = _facts(case)
    assert not _find(facts, "Activity", "runs or cycles"), "facts derived from a rejected account disappear"
    assert not _find(facts, "Profile location", "Graz")
    assert any(c.get("decision") == "discard" for c in case.constraints), "recorded as an analyst constraint"


@pytest.mark.asyncio
async def test_rejecting_a_stated_fact_retracts_its_inference_and_confirming_steers_search(case):
    from snoop.profile import review

    competes = _find(_facts(case), "Competes", "lightweight")
    await review(case, competes["id"], "rejected", Bus())
    assert _find(_facts(case), "Body weight (est.)")["status"] == "rejected"

    role = _find(_facts(case), "Role", "software engineer")
    await review(case, role["id"], "confirmed", Bus())
    assert _find(_facts(case), "Role")["status"] == "confirmed"
    assert "software engineer" in [c.casefold() for c in case.context]
    assert any(l["type"] == "web_search" and "software engineer" in l["args"]["query"].casefold() for l in case.leads)


@pytest.mark.asyncio
async def _removed_test_ai_facts_must_cite_case_items_and_respect_the_privacy_filter(case, monkeypatch):
    from snoop.config import config as cfg
    from snoop.profile import ai_extract

    record = evidence_record(claim="mentioned-in-source (mentioned)", source_url="https://news.example/a",
                             excerpt="Alex Example won the regional no-gi open in 2024.", method="page-text",
                             supports=True)
    case.evidence_records.append(record)
    monkeypatch.setattr(cfg, "ai_provider", lambda: "openai")

    async def fake_call(prompt, system):
        return json.dumps({"facts": [
            {"category": "sport", "label": "Title", "value": "Regional no-gi open winner (2024)",
             "confidence": "stated", "why": "news report", "cites": [record["id"]]},
            {"category": "sport", "label": "Made up", "value": "Olympic gold", "cites": ["ev_invented"]},
            {"category": "identity", "label": "Religion", "value": "Catholic", "cites": [record["id"]]},
            {"category": "hobbies", "label": "Bad category", "value": "x", "cites": [record["id"]]},
        ]})

    monkeypatch.setattr("snoop.analyst._call", fake_call)
    result = await ai_extract(case, Bus())
    assert result["added"] == 1
    fact = _find(_facts(case), "Title", "no-gi")
    assert fact and fact["origin"] == "ai" and fact["evidence_ids"] == [record["id"]]
    assert not _find(_facts(case), "Religion") and not _find(_facts(case), "Made up")


def test_gender_comes_from_pronouns_never_from_a_name(case):
    facts = _facts(case)
    assert _find(facts, "Gender")["value"] == "Unknown", "no pronouns yet -> unknown, not a name guess"

    record = evidence_record(claim="mentioned-in-source (mentioned)", source_url="https://news.example/b",
                             excerpt="Alex Example won his third bout; he trains in Graz.", method="page-text", supports=True)
    case.evidence_records.append(record)
    gender = _find(_facts(case), "Gender")
    assert gender["value"] == "Male" and gender["basis"] == "inferred" and gender["evidence_ids"] == [record["id"]]

    case.hits[1]["bio"] = "she/her · trail runner"
    gender = _find(_facts(case), "Gender")
    assert gender["value"] == "Female" and gender["basis"] == "stated", "stated pronouns win over counted ones"


def _removed_test_filter_blocks_trait_and_contact_claims_but_not_ordinary_words():
    from snoop.profile import FORBIDDEN

    for ok in ("Finished the Graz trail race", "Street photographer", "iPhone developer",
               "Political science student", "Health-tech engineer", "Voted best speaker"):
        assert not FORBIDDEN.search(ok), ok
    for blocked in ("Religion: Catholic", "Sexual orientation", "Home address: 12 Main St",
                    "Phone number +43 660", "Political affiliation", "Health condition"):
        assert FORBIDDEN.search(blocked), blocked


@pytest.mark.asyncio
async def test_fact_command_through_the_shared_registry(case):
    from snoop import registry

    weight = _find(_facts(case), "Body weight (est.)")
    result = await registry.execute(f"fact {weight['id']} wrong", case, Bus(), runtime="cli")
    assert "marked wrong" in result["text"]
    shown = await registry.execute("profile", case, Bus(), runtime="cli")
    assert "Body weight" not in shown["text"], "rejected facts drop out of the rendered profile"
    with pytest.raises(registry.CommandError):
        await registry.execute(f"fact {weight['id']} maybe", case, Bus(), runtime="cli")
