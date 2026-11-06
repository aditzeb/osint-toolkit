"""Focused regressions for the subject-preserving interview workflow."""

from __future__ import annotations

import pytest

from snoop.core import Bus
from snoop.model import ensure_account, source_record
from snoop.pipeline import Dossier


@pytest.fixture
def case_dir(tmp_path, monkeypatch):
    from snoop import pipeline

    monkeypatch.setattr(pipeline, "CASES_DIR", tmp_path)
    return tmp_path


def make_case() -> Dossier:
    return Dossier("theo-case", "Theo Lindqvist", "name", "2026-01-01T00:00:00+00:00")


def test_blocked_exact_name_result_is_saved_as_unverified_lead(case_dir):
    from snoop.workflow import Workflow

    dossier = make_case()
    url = "https://www.linkedin.com/in/theo-lindqvist"
    dossier.queries = [
        {
            "id": "qry-exact",
            "query": '"Theo Lindqvist"',
            "results": [{"title": "Theo Lindqvist - LinkedIn", "snippet": "Theo Lindqvist profile", "url": url}],
        }
    ]
    workflow = Workflow(dossier, Bus())
    source = source_record(url=url, outcome="blocked", via="search:google")
    workflow._preserve_blocked_lead(url, "google", "blocked", source)

    kept = dossier.sources[0]
    assert kept["outcome"] == "blocked"
    assert kept["extra"]["snippet_only"] is True
    assert kept["extra"]["exact_name_result"] is True
    assert kept["extra"]["verified"] is False


@pytest.mark.asyncio
async def test_unknown_answer_is_saved_once_and_confirmation_does_not_repeat(case_dir):
    from snoop.interview import apply_answer, next_question, set_pending

    dossier = make_case()
    question = next_question(dossier)
    set_pending(dossier, question)
    await apply_answer(dossier, "I don't know", Bus())

    assert dossier.interview[0]["id"] == "confirm-name"
    assert dossier.interview[0]["kind"] == "unknown"
    assert next_question(dossier)["id"] != "confirm-name"


@pytest.mark.asyncio
async def test_answers_replan_exact_and_context_searches(case_dir):
    from snoop.interview import apply_answer, next_question, set_pending

    dossier = make_case()
    set_pending(dossier, next_question(dossier))
    result = await apply_answer(dossier, "confirm", Bus())
    assert "name confirmed" in result["text"]
    assert any(lead["args"].get("query") == '"theo lindqvist"' for lead in dossier.leads)

    dossier.leads.clear()  # model a completed exact-name pass before asking for context
    dossier.interview.append({"id": "context-country", "kind": "asked"})
    set_pending(
        dossier,
        {
            "id": "context-occupation",
            "kind": "context",
            "text": "Do you know the subject's occupation or main interest?",
        },
    )
    context_result = await apply_answer(dossier, "cybersecurity", Bus())
    assert "context applied" in context_result["text"]
    assert "cybersecurity" in dossier.context
    assert any("cybersecurity" in lead["args"].get("query", "") for lead in dossier.leads)


@pytest.mark.asyncio
async def test_corrected_name_replans_and_reassesses_with_the_correct_spelling(case_dir):
    from snoop.interview import apply_answer, next_question, set_pending, subject_display_name

    dossier = Dossier("corrected-case", "Theeo Lindqvist", "name", "2026-01-01T00:00:00+00:00")
    candidate = {
        "platform": "web",
        "url": "https://example.test/theo",
        "display_name": "Theo Lindqvist",
    }
    ensure_account(candidate)
    dossier.hits = [candidate]
    set_pending(dossier, next_question(dossier))

    await apply_answer(dossier, "actually Theo Lindqvist", Bus())

    assert subject_display_name(dossier) == "Theo Lindqvist"
    assert dossier.hits[0]["score"] >= 42
    assert any(lead["args"].get("query", "").casefold() == '"theo lindqvist"' for lead in dossier.leads)


@pytest.mark.asyncio
async def test_registry_and_talk_resume_one_saved_conversation(case_dir):
    from snoop import interview, registry, talk

    dossier = make_case()
    interview.set_pending(dossier, interview.next_question(dossier))
    first = await registry.execute("confirm", dossier, Bus(), runtime="web")
    assert "name confirmed" in first["text"]
    dossier.save()

    reloaded = Dossier.load(dossier.id)
    assert reloaded is not None
    reloaded.leads.clear()
    interview.set_pending(
        reloaded,
        {"id": "context-country", "kind": "context", "text": "Do you know the subject's country or city?"},
    )
    reloaded.save()
    resumed, reply = await talk.handle(Dossier.load(dossier.id), "Skip", Bus())

    assert resumed is not None
    assert "no context added" in reply
    assert any(row["id"] == "context-country" and row["kind"] == "skipped" for row in resumed.interview)
