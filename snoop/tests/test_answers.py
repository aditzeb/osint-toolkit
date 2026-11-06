"""Analyst answers become clean profile fields; unanswered questions time out."""

from __future__ import annotations

import pytest

from snoop.core import Bus
from snoop.pipeline import Dossier


@pytest.fixture
def case(tmp_path, monkeypatch):
    from snoop import pipeline
    from snoop.config import config

    monkeypatch.setattr(pipeline, "CASES_DIR", tmp_path)
    for key in ("openai_key", "anthropic_key", "gemini_key"):
        monkeypatch.setattr(config, key, "")
    dossier = Dossier("answers-case", "Theo Lindqvist", "name", "2026-01-01T00:00:00+00:00")
    dossier.subject = {"input": "Theo Lindqvist", "name_confirmed": True}
    return dossier


def _fields(facts):
    return {(f["label"], f["value"]) for f in facts}


@pytest.mark.parametrize(("text", "qid", "expected"), [
    ("he lives in france", "", {("Currently living", "France")}),
    ("france", "context-country", {("Currently living", "France")}),
    ("i think he lives in paris and works at renault", "", {("Currently living", "Paris"), ("Works at", "Renault")}),
    ("he's a cybersecurity creator, 24 years old", "", {("Occupation", "Cybersecurity creator"), ("Age", "24")}),
    ("he is from portugal but moved to belgium", "", {("From", "Portugal"), ("Currently living", "Belgium")}),
    ("he speaks italian, french and english", "", {("Languages spoken", "Italian, French, English")}),
    ("he plays football and likes chess", "", {("Activity", "Football, Chess")}),
    ("he is a software engineer at google", "", {("Occupation", "Software engineer"), ("Works at", "Google")}),
    ("studies computer science at Sorbonne", "", {("Studies", "Computer science"), ("Education", "Sorbonne")}),
    ("whoamitang", "context-handle", {("Username", "@whoamitang")}),
    ("Yes France, Lyon area somewhere around", "context-country", {("Currently living", "Lyon area, France")}),
    ("yes france lyon area somewhere around", "context-country", {("Currently living", "Lyon area, France")}),
    ("i think he does mma and works in it", "", {("Activity", "MMA"), ("Field", "IT")}),
    ("yes on instagram he goes by theolind", "context-handle", {("Instagram", "@theolind")}),
    ("he works in it at orange", "", {("Field", "IT"), ("Works at", "Orange")}),
])
def test_answers_are_parsed_into_clean_fields(text, qid, expected):
    from snoop.answers import parse

    assert _fields(parse(text, qid)) == expected


def test_hedged_answer_is_marked_likely():
    from snoop.answers import parse

    assert parse("maybe he lives in vienna")[0]["confidence"] == "likely"


@pytest.mark.asyncio
async def test_answer_shows_as_profile_field_and_refines_search(case):
    from snoop.interview import apply_answer, next_question, set_pending
    from snoop.profile import build

    set_pending(case, {"id": "agent:x1", "kind": "agent", "text": "Where does he live?"})
    result = await apply_answer(case, "he lives in france", Bus())

    facts = build(case)["facts"]
    living = [f for f in facts if f["label"] == "Currently living"]
    assert living and living[0]["value"] == "France" and living[0]["status"] == "confirmed"
    assert living[0]["excerpt"] == "he lives in france", "the original wording stays as provenance"
    assert not [f for f in facts if f["label"] == "Known to you"]
    assert "Currently living: France" in result["text"]
    assert "Known to you" not in result["text"]
    assert any(lead["args"].get("query", "").casefold() == '"theo lindqvist" france' for lead in case.leads)

    case.leads.clear()
    question = next_question(case)
    assert not question or question["id"] != "context-country", "never ask for a country we were already told"


@pytest.mark.asyncio
async def test_unparseable_answer_still_kept_verbatim(case):
    from snoop.interview import apply_answer, set_pending
    from snoop.profile import build

    set_pending(case, {"id": "distinguish-what", "kind": "context", "text": "What distinguishes them?"})
    await apply_answer(case, "the one with the black hoodie", Bus())
    assert any(f["label"] == "Known to you" for f in build(case)["facts"])


@pytest.mark.asyncio
async def test_ai_structures_answers_when_configured(case, monkeypatch):
    import json

    from snoop.config import config
    from snoop.interview import apply_answer, set_pending
    from snoop.profile import build

    monkeypatch.setattr(config, "ai_provider", lambda: "openai")

    async def fake_call(prompt, system):
        return json.dumps({"facts": [{"category": "places", "label": "Currently living", "value": "Lyon, France",
                                      "confidence": "stated"}]})

    monkeypatch.setattr("snoop.analyst._call", fake_call)
    set_pending(case, {"id": "agent:x2", "kind": "agent", "text": "Where does he live?"})
    await apply_answer(case, "he's in lyon these days", Bus())
    assert any(f["label"] == "Currently living" and f["value"] == "Lyon, France" for f in build(case)["facts"])


@pytest.mark.asyncio
async def test_timeout_reply_skips_and_is_recorded(case):
    from snoop.interview import TIMEOUT_REPLY, apply_answer, pending, set_pending

    set_pending(case, {"id": "context-occupation", "kind": "context", "text": "Occupation?"})
    assert case.pending_question["asked_at"]
    result = await apply_answer(case, TIMEOUT_REPLY, Bus())
    assert result["timed_out"] and "no reply" in result["text"]
    assert case.interview[-1]["kind"] == "skipped"
    assert not case.context
    assert not pending(case) or pending(case)["id"] != "context-occupation"


@pytest.mark.asyncio
async def test_timeout_continues_the_investigation(case, monkeypatch):
    from snoop import registry
    from snoop.interview import TIMEOUT_REPLY, set_pending

    ran = []

    async def fake_run(ctx):
        ran.append(True)
        return {"text": "continued"}

    monkeypatch.setattr(registry, "_h_run", fake_run)
    from snoop.leads import LeadQueue

    LeadQueue(case).add("web_search", {"query": '"Theo Lindqvist" profile'}, "queued work", score=5.0)
    set_pending(case, {"id": "context-occupation", "kind": "context", "text": "Occupation?"})
    result = await registry.execute("answer " + '"' + TIMEOUT_REPLY + '"', case, Bus(), runtime="cli")
    assert ran and "continued" in result["text"]


@pytest.mark.asyncio
async def test_fact_check_question_confirms_or_rejects_a_found_fact(case, monkeypatch):
    from snoop import interview, profile

    fact = {"id": "f_based", "label": "Based in", "value": "Vienna", "status": "unreviewed", "origin": "rule",
            "confidence": "likely", "sources": ["example.org"], "category": "places"}
    monkeypatch.setattr(profile, "build", lambda d: {"facts": [fact]})
    reviewed = []

    async def fake_review(d, fid, status, bus=None, note=""):
        reviewed.append((fid, status))
        return f"{fid} {status}"

    monkeypatch.setattr(profile, "review", fake_review)
    question = interview.next_question(case)
    assert question["kind"] == "fact-check" and "Vienna" in question["text"]
    interview.set_pending(case, question)
    await interview.apply_answer(case, "no, that's wrong", Bus())
    assert reviewed == [("f_based", "rejected")]
    assert interview.next_question(case) is None or interview.next_question(case)["id"] != question["id"]


@pytest.mark.asyncio
async def test_named_platform_handle_is_checked(case):
    from snoop.interview import apply_answer, set_pending

    set_pending(case, {"id": "context-handle", "kind": "context", "text": "Known username?"})
    await apply_answer(case, "yes on instagram he goes by theolind", Bus())
    assert any(lead["type"] == "probe_handles" and lead["args"]["handles"] == ["theolind"] for lead in case.leads)
