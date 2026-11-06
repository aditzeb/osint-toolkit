"""Offline contract tests for strict matching, guided rounds and model requests."""

import json

import pytest

from snoop.core import Bus
from snoop.model import ensure_account, evidence_record, source_record
from snoop.pipeline import Dossier, apply_assessments


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setattr("snoop.pipeline.CASES_DIR", tmp_path)
    monkeypatch.setattr("snoop.config.config.ai_provider", lambda: None)
    d = Dossier("guided-test", "Theo Lindqvist", "name", "2026-09-14")
    d.subject = {"input": d.target, "name_confirmed": True, "exact_name": True}
    return d


def account(name, index=0):
    h = {"platform": "Example", "url": f"https://example.test/profile/{index}",
         "display_name": name, "matched_handle": "theolindqvist", "bio": "robotics Toronto",
         "links": [], "extra": {}}
    ensure_account(h)
    return h




def _removed_test_exact_names_preserve_initials_particles_unicode():
    from snoop.policy import exact_name

    # DELETE_ME_1
    assert exact_name("Jose\u0301 van A. Berg", "José van A Berg")
    # DELETE_ME_3




@pytest.mark.parametrize("text", ["not relevant", "that's not my subject", "no, that's him in a different case"])
async def test_negative_answer_never_keeps_candidate(case, text):
    from snoop.interview import apply_answer

    apply_assessments(case, [account("Theo Lindqvist")])
    h = case.hits[0]
    case.pending_question = {"id": "distinguish:test", "kind": "distinguish", "account_ref": h["ref"]}
    await apply_answer(case, text)
    assert case.interview[-1]["kind"] == "not-relevant"
    assert not case.hits


async def test_web_natural_reply_accepts_apostrophes(case):
    from snoop.registry import execute

    case.pending_question = {"id": "context-country", "kind": "context", "text": "Country?"}
    await execute("I don't know", case, runtime="web")
    assert case.interview[0]["kind"] == "unknown"


async def test_correction_preserves_input_and_supersedes_old_frontier(case):
    from snoop.interview import apply_answer
    from snoop.leads import LeadQueue

    case.subject["name_confirmed"] = None
    case.pending_question = {"id": "confirm-name", "kind": "confirm-name", "text": "Correct name?"}
    LeadQueue(case).add("web_search", {"query": '"Theo Lindqvist"'}, "Old spelling")
    await apply_answer(case, "actually Jonas Feldmark")
    assert case.target == "Theo Lindqvist"
    assert case.subject["corrected_name"] == "Jonas Feldmark"
    assert case.leads[0]["status"] == "rejected"
    assert any('jonas feldmark' in l["args"].get("query", "") for l in case.leads if l["status"] == "pending")


async def test_correction_button_requests_the_name(case):
    from snoop.interview import apply_answer

    case.pending_question = {"id": "confirm-name", "kind": "confirm-name", "text": "Correct?"}
    await apply_answer(case, "correct")
    assert "corrected full name" in case.pending_question["text"]
    assert not case.interview
    await apply_answer(case, "Jonas Feldmark")
    assert case.subject["corrected_name"] == "Jonas Feldmark"


async def test_guided_rounds_pause_and_natural_answer_resumes_same_case(case, monkeypatch):
    from snoop import registry, talk
    from snoop.leads import LeadQueue
    from snoop.workflow import Workflow

    case.workflow.update(guided=True, preset="quick")
    for i in range(7):
        LeadQueue(case).add("web_search", {"query": f'"Theo Lindqvist" topic{i}'}, "Research", score=8)

    async def search(self, lead):
        self.dossier.queries.append({"id": lead["id"], "query": lead["args"]["query"], "results": []})
        self.spent["searches"] += 1

    monkeypatch.setattr(Workflow, "_do_web_search", search)
    result = await Workflow(case).run()
    assert result["status"] == "needs_input"
    assert len(case.queries) == 4
    assert len(case.workflow["checkpoints"]) == 1
    assert case.pending_question["id"] == "context-country"
    restored = Dossier.load(case.id)
    restored, _ = await talk.handle(restored, "Berlin", Bus())
    assert restored.id == case.id
    assert len(restored.queries) == 8
    assert "berlin" in restored.context
    assert restored.pending_question["id"] == "context-occupation"
    brief = await registry.execute("briefing", restored)
    assert brief["data"]["coverage"]["queries"] == 8


async def test_cli_upgrade_reactivates_only_new_budget_capacity(case, monkeypatch):
    from snoop.leads import LeadQueue
    from snoop.registry import execute
    from snoop.workflow import Workflow

    case.workflow.update(preset="quick", spent={"searches": 8}, iterations=8)
    lead = LeadQueue(case).add("web_search", {"query": "new query"}, "Deferred search")
    lead.update(status="deferred", reason="searches budget reached")

    async def search(self, lead):
        self.spent["searches"] += 1
        self.dossier.queries.append({"id": lead["id"]})

    monkeypatch.setattr(Workflow, "_do_web_search", search)
    await execute("run --preset deep", case)
    assert case.workflow["preset"] == "deep"
    assert case.workflow["spent"]["searches"] == 9
    assert lead["status"] == "explored"


def test_briefing_distinguishes_unavailable_sources_from_read_pages(case):
    from snoop.briefing import build_briefing

    case.sources = [source_record(url="https://a.example/article", outcome="found"),
                    source_record(url="https://b.example/profile", outcome="blocked")]
    data = build_briefing(case)
    assert data["coverage"]["sources_read"] == 1
    assert data["coverage"]["unavailable_sources"] == 1
    assert any("snippets are leads" in gap for gap in data["gaps"])


async def test_ai_can_analyze_sourced_mentions_without_accounts(case, monkeypatch):
    from snoop import analyst

    record = evidence_record(claim="mentioned-in-source", source_url="https://example.test/article", supports=True, method="page-text")
    monkeypatch.setattr("snoop.config.config.ai_provider", lambda: "openai")
    async def model(prompt, system):
        assert record["id"] in prompt
        return json.dumps({"identities": [], "key_findings": [{"text": "Public mention", "evidence_ids": [record["id"]]}]})
    monkeypatch.setattr(analyst, "_call", model)
    result = await analyst.analyze(case.target, "name", [], {}, Bus(), evidence_records=[record])
    assert result["analysis_mode"] == "openai"
    assert result["key_findings"][0]["evidence_ids"] == [record["id"]]


async def test_modern_model_request_has_reasoning_without_temperature(case, monkeypatch):
    from snoop import analyst
    from snoop.config import config

    monkeypatch.setattr(config, "ai_provider", lambda: "openai")
    monkeypatch.setattr(config, "openai_model", "gpt-6-astra")
    observed = {}
    class Response:
        status = 200
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def json(self):
            return {"choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}]}
    class Session(Response):
        def __init__(self, **kwargs):
            pass
        def post(self, url, **kwargs):
            observed.update(kwargs["json"])
            return Response()
    monkeypatch.setattr(analyst.aiohttp, "ClientSession", Session)
    assert await analyst._call("JSON please", "Return JSON") == '{"ok": true}'
    assert "temperature" not in observed
    assert observed["reasoning_effort"] == config.reasoning_effort
    assert observed["max_completion_tokens"] == config.ai_max_output_tokens




async def test_browser_api_flags_and_briefing_share_cli_state(case, monkeypatch):
    from aiohttp.test_utils import TestClient, TestServer

    from snoop import pipeline, registry
    from snoop.web import build_app

    received = {}
    async def investigate(target, bus, **kwargs):
        received.update(kwargs)
        await bus.emit("done", id=case.id)
        return case
    monkeypatch.setattr(pipeline, "investigate", investigate)
    case.save()
    async with TestClient(TestServer(build_app())) as client:
        response = await client.post("/api/investigate", json={"target": case.target, "exact_name": True, "guided": True})
        assert response.status == 200
        await response.text()
        assert received["exact_name"] and received["guided"]
        response = await client.get(f"/api/case/{case.id}")
        data = await response.json()
        cli = await registry.execute("briefing", Dossier.load(case.id))
        assert data["briefing"] == cli["data"]


def test_mentions_require_name_boundaries():
    from snoop.discover import find_mentions

    assert not find_mentions("XTheo Lindqvist Jr", "Theo Lindqvist")
    assert find_mentions("By Theo\nLindqvist, speaker.", "Theo Lindqvist")


def test_one_shot_cli_accepts_exact_and_guided_flags():
    from snoop.cli import _build_parser
    from snoop.registry import COMMANDS

    argv = ["Theo Lindqvist", "--exact-name", "--guided", "--mode", "deep"]
    parsed = _build_parser().parse_args(argv)
    registered = COMMANDS["investigate"].parse(argv)
    assert parsed.exact_name and parsed.guided
    assert registered["exact_name"] and registered["guided"]


def test_accounts_only_never_enqueues_web_pivots(case):
    from snoop.workflow import Workflow

    workflow = Workflow(case, mode="accounts")
    assert workflow._ingest_leads([{"type": "web_search", "args": {"query": "alias"}, "purpose": "Search"}]) == 0
    assert not case.leads
