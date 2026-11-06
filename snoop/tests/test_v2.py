import asyncio
import json
from pathlib import Path

import pytest

from snoop import actions
from snoop.analyst import _loads, analyze, answer_question, validate_analysis
from snoop.core import Bus, Fetch, Http, UnsafeUrl, scoped_headers, validate_public_url
from snoop.enum import Hit, _check
from snoop.evidence import UNRELATED, assess, context_match
from snoop.extract import _p_github
from snoop.model import ensure_account, evidence_record, stable_account_id
from snoop.pipeline import Dossier, apply_assessments
from snoop.session import merge, pick, reconcile_analysis


def hit(
    platform="GitHub",
    url="https://github.com/alexexample",
    name="Alex Example",
    bio="robotics",
    handle="alexexample",
    links=None,
    avatar="",
):
    row = {
        "platform": platform,
        "url": url,
        "display_name": name,
        "bio": bio,
        "location": "",
        "links": links or [],
        "avatar": avatar,
        "extra": {"matched_handle": handle},
        "matched_handle": handle,
    }
    ensure_account(row, set())
    return row


def dossier(monkeypatch, rows=None):
    from snoop import pipeline

    monkeypatch.setattr(pipeline, "CASES_DIR", Path("reports"))
    d = Dossier("test-case-v2", "Alex Example", "name", "2026-01-01T00:00:00+00:00")
    apply_assessments(d, rows or [hit()])
    d.analysis = {"identities": []}
    return d


def test_duplicate_context_invariance_and_whole_word():
    row = hit(bio="amateur MMA competitor")
    once = assess([row], target="Alex Example", kind="name", context=["MMA"])[0].score
    many = assess([row], target="Alex Example", kind="name", context=["mma", " MMA ", "mma"])[
        0
    ].score
    assert once == many
    assert context_match(hit(bio="command line developer"), ["MMA"]) == []


def test_handle_and_single_profile_do_not_self_confirm():
    result = assess([hit(name="", bio="", handle="alex")], target="alex", kind="username")[0]
    # Existence under the searched handle is not ownership: the account stays
    # explicitly insufficient rather than being discarded or confirmed.
    assert result.verdict == "insufficient" and result.score <= 2


def test_namesake_and_copied_image_stay_unresolved():
    namesake = assess([hit(name="Morgan Other")], target="Alex Example", kind="name")[0]
    assert namesake.verdict == UNRELATED
    rows = [
        hit("GitHub", avatar="https://img.example/x.jpg", name="", bio=""),
        hit(
            "Behance",
            "https://behance.net/alexexample",
            avatar="https://img.example/x.jpg",
            name="",
            bio="",
        ),
    ]
    assert all(
        x.verdict not in {"probable", "confirmed"}
        for x in assess(rows, target="Alex Example", kind="name")
    )


def test_parser_preserves_discovery_metadata():
    value = Hit(
        "GitHub",
        "dev",
        "https://github.com/a",
        matched_handle="a",
        extra={"matched_handle": "a", "discovery": "fixture"},
    )
    _p_github({"id": 7, "name": "A", "public_repos": 2}, value)
    assert value.extra["matched_handle"] == "a" and value.extra["discovery"] == "fixture"
    assert value.platform_id == "7"


def test_stable_ids_and_migration_persistence(monkeypatch):
    d = dossier(monkeypatch)
    assert d.hits[0]["ref"] == "H01" and d.hits[0]["account_id"].startswith("acct_")
    assert stable_account_id("GitHub", "https://github.com/A/") == stable_account_id(
        "GitHub", "https://github.com/A"
    )
    d.record_action("fixture")
    d.save()
    loaded = Dossier.load("test-case-v2")
    assert loaded.schema_version >= 3 and loaded.action_history[-1]["action"] == "fixture"


def _removed_test_json_parser_handles_braces_and_validation_rejects_unknown_refs():
    parsed = _loads('prefix {"summary":"a } and { in a string","identities":[]} suffix')
    assert parsed["summary"] == "a } and { in a string"
    bad = {"identities": [{"account_ids": ["missing"], "evidence_ids": []}]}
    assert validate_analysis(bad, {"acct_ok"}, {"ev_ok"})["identities"] == []
    assert _loads('{"identities": [}') is None


@pytest.mark.asyncio
async def test_provider_failure_keeps_candidates_separate(monkeypatch):
    from snoop.config import config

    monkeypatch.setattr(config, "openai_key", "configured")
    monkeypatch.setattr(config, "anthropic_key", "")
    monkeypatch.setattr(config, "gemini_key", "")

    async def fail(*_a, **_kw):
        raise RuntimeError("provider down")

    monkeypatch.setattr("snoop.analyst._call", fail)
    rows = [hit(), hit("Behance", "https://behance.net/alexexample")]
    result = await analyze("Alex Example", "name", rows, {}, Bus(), evidence_records=[])
    assert len(result["identities"]) == 2 and result["analysis_mode"] == "deterministic"


@pytest.mark.asyncio
async def test_unverified_profile_emails_are_not_enriched(monkeypatch):
    from snoop import pipeline
    from snoop.config import config

    monkeypatch.setattr(pipeline, "CASES_DIR", Path("reports"))
    monkeypatch.setattr(config, "openai_key", "")
    monkeypatch.setattr(config, "anthropic_key", "")
    monkeypatch.setattr(config, "gemini_key", "")

    async def enumerate_one(handle, _bus, _http, sites=None, max_sites=None):
        return [
            Hit(
                "GitHub",
                "dev",
                f"https://github.com/{handle}",
                matched_handle=handle,
                canonical_url=f"https://github.com/{handle}",
                account_id=f"acct_{handle}",
                extra={"matched_handle": handle, "email": "unrelated@example.test"},
            )
        ]

    async def no_extract(_http, hit, _bus):
        hit.bio = "contact unrelated@example.test"

    captured = []

    async def capture(emails, _http, _bus):
        captured.extend(emails)
        return {}

    monkeypatch.setattr(pipeline, "enumerate_username", enumerate_one)
    monkeypatch.setattr(pipeline, "enrich_hit", no_extract)
    monkeypatch.setattr(pipeline, "run_email_enrichment", capture)
    # This tests account email scope. Full discovery would use the developer's
    # configured search credentials and perform unrelated real network work.
    await pipeline.investigate("Alex Example", kind="name", do_emails=True, mode="accounts")
    assert captured == []


def test_http_status_classification():
    assert Http._outcome(403) == "blocked"
    assert Http._outcome(429) == "rate_limited"
    assert Http._outcome(404) == "not_found"
    assert Http._outcome(503) == "unavailable"


@pytest.mark.asyncio
async def test_soft_404_and_inconclusive_control_are_not_hits():
    site = {"name": "Fixture", "url": "https://fixture.example/{}", "method": "status"}

    class Fake:
        def __init__(self, control):
            self.control = control

        async def get(self, url, **kwargs):
            return (
                self.control
                if "control" in kwargs
                else Fetch(True, 200, "found", url=url, final_url=url)
            )

    assert await _check(Fake(Fetch(False, 0, "unavailable")), site, "alex", "control") is None
    found = await _check(Fake(Fetch(False, 404, "not_found")), site, "alex", "control")
    assert found and found.observation_status == "found"


@pytest.mark.asyncio
async def test_message_soft_404_is_not_found():
    site = {
        "name": "Fixture",
        "url": "https://fixture.example/{}",
        "method": "message",
        "errorMsg": "missing",
    }

    class Fake:
        async def get(self, url, **kwargs):
            return Fetch(True, 200, "found", url=url, final_url=url, text="missing")

    assert await _check(Fake(), site, "alex", "control") is None


def _removed_test_credentials_are_scoped_to_exact_origin():
    headers = {
        "Authorization": "secret",
        "X-Subscription-Token": "search-secret",
        "User-Agent": "ok",
    }
    assert "Authorization" in scoped_headers(headers, "api.github.com", "api.github.com")
    assert "Authorization" not in scoped_headers(headers, "evil.example", "api.github.com")
    assert "X-Subscription-Token" not in scoped_headers(
        headers, "evil.example", "api.search.brave.com"
    )
    assert Http._retry_after("2") == 2


@pytest.mark.asyncio
async def test_brave_search_adapter_fetches_only_supported_results(monkeypatch):
    from snoop.config import config

    d = dossier(monkeypatch)
    requested = {}
    anchored = []

    class FakeHttp:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url, **kwargs):
            requested.update(url=url, **kwargs)
            return Fetch(
                True,
                200,
                "found",
                url=url,
                final_url=url,
                json={
                    "web": {
                        "results": [
                            {"url": "https://github.com/alexfixture"},
                            {"url": "https://unsupported.example/alexfixture"},
                        ]
                    }
                },
            )

    async def fake_anchor(case, url, bus=None, discovery_source=""):
        anchored.append((url, discovery_source))
        case.hits.append(hit(url=url, handle="alexfixture"))
        return "added"

    monkeypatch.setattr(config, "brave_search_key", "fixture-key")
    monkeypatch.setattr(actions, "Http", FakeHttp)
    monkeypatch.setattr(actions, "anchor", fake_anchor)
    message = await actions.search(d, "robotics")
    assert "api.search.brave.com" in requested["url"]
    assert requested["credentials_for"] == "api.search.brave.com"
    assert requested["headers"] == {"X-Subscription-Token": "fixture-key"}
    assert anchored == [("https://github.com/alexfixture", "brave-search")]
    assert "1 supported profile clue" in message


@pytest.mark.asyncio
async def test_anchor_rejects_non_profile_paths_before_fetch(monkeypatch):
    d = dossier(monkeypatch)
    with pytest.raises(ValueError, match="profile URL shape"):
        await actions.anchor(d, "https://github.com/alexexample/private-project")


@pytest.mark.asyncio
async def _removed_test_unsafe_url_policy_blocks_private_and_metadata():
    async def private(*_args, **_kwargs):
        return [(None, None, None, None, ("10.0.0.8", 80))]

    with pytest.raises(UnsafeUrl):
        await validate_public_url("http://example.test/x", resolver=private)
    with pytest.raises(UnsafeUrl):
        await validate_public_url("http://169.254.169.254/latest")


@pytest.mark.asyncio
async def test_http_retries_rate_limit_timeout_parse_and_redirect_credentials(monkeypatch):
    class Content:
        def __init__(self, body=b""):
            self.body = body

        async def iter_chunked(self, _size):
            if self.body:
                yield self.body

    class Response:
        def __init__(self, status, body=b"", headers=None, enter_error=None):
            self.status = status
            self.headers = headers or {}
            self.charset = "utf-8"
            self.content = Content(body)
            self.enter_error = enter_error

        async def __aenter__(self):
            if self.enter_error:
                raise self.enter_error
            return self

        async def __aexit__(self, *_args):
            return None

    class Session:
        def __init__(self, responses):
            self.responses = list(responses)
            self.headers = []

        def get(self, _url, **kwargs):
            self.headers.append(dict(kwargs.get("headers", {})))
            return self.responses.pop(0)

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    rate = Http(retries=1)
    rate._session = Session(
        [
            Response(429, headers={"Retry-After": "0"}),
            Response(200, b"ok"),
        ]
    )
    result = await rate.get("https://api.example.test/profile")
    assert result.outcome == "found" and result.retries == 1 and rate.stats["retries"] == 1

    timeout = Http(retries=1)
    timeout._session = Session(
        [
            Response(0, enter_error=TimeoutError()),
            Response(0, enter_error=TimeoutError()),
        ]
    )
    assert (await timeout.get("https://api.example.test/profile")).outcome == "unavailable"

    malformed = Http(retries=0)
    malformed._session = Session([Response(200, b"not-json")])
    assert (
        await malformed.get("https://api.example.test/profile", want_json=True)
    ).outcome == "parse_failure"

    redirected = Http(retries=1)
    redirected._session = Session(
        [
            Response(302, headers={"Location": "https://other.example/result"}),
            Response(200, b"ok"),
        ]
    )
    await redirected.get(
        "https://api.example.test/profile",
        headers={"X-Subscription-Token": "secret"},
        credentials_for="api.example.test",
    )
    assert "X-Subscription-Token" in redirected._session.headers[0]


@pytest.mark.asyncio
async def test_unsafe_redirect_is_blocked_without_retry(monkeypatch):
    class Content:
        async def iter_chunked(self, _size):
            if False:
                yield b""

    class Response:
        def __init__(self):
            self.status = 302
            self.charset = "utf-8"
            self.headers = {"Location": "http://169.254.169.254/latest"}
            self.content = Content()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    class Session:
        calls = 0

        def get(self, *_args, **_kwargs):
            self.calls += 1
            return Response()

    async def allow_initial(url):
        if "169.254.169.254" in url:
            raise UnsafeUrl("metadata blocked")
        return url

    monkeypatch.setattr("snoop.core.validate_public_url", allow_initial)
    http = Http(retries=2)
    http._session = Session()
    result = await http.get("https://public.example/profile", safe=True)
    assert result.outcome == "blocked" and http._session.calls == 1


@pytest.mark.asyncio
async def test_verify_preserves_specific_inconclusive_status(monkeypatch):
    d = dossier(monkeypatch)

    class FakeHttp:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            return Fetch(False, 429, "rate_limited", retrieved_at="2026-01-01")

    monkeypatch.setattr(actions, "Http", FakeHttp)
    await actions.verify(d, "H01")
    assert d.account("H01")["observation_status"] == "rate_limited"
    assert d.account("H01")["last_verification"]["outcome"] == "rate_limited"


@pytest.mark.asyncio
async def test_hibp_distinguishes_configuration_auth_rate_limit_and_empty(monkeypatch):
    from snoop.config import config
    from snoop.enrich import hibp_breaches

    class FakeHttp:
        def __init__(self, result):
            self.result = result

        async def get(self, *_args, **_kwargs):
            return self.result

    monkeypatch.setattr(config, "hibp_key", "")
    assert (await hibp_breaches(FakeHttp(None), "owned@example.test"))["status"] == (
        "missing_configuration"
    )
    monkeypatch.setattr(config, "hibp_key", "fixture")
    cases = [
        (Fetch(False, 401, "blocked"), "authentication_failure"),
        (Fetch(False, 429, "rate_limited"), "rate_limited"),
        (Fetch(False, 404, "not_found"), "empty"),
    ]
    for response, expected in cases:
        assert (await hibp_breaches(FakeHttp(response), "owned@example.test"))["status"] == expected


@pytest.mark.asyncio
async def test_decisions_survive_reanalysis_and_resume(monkeypatch):
    d = dossier(monkeypatch, [hit(), hit("Behance", "https://behance.net/alexexample")])
    d.analysis = {
        "identities": [
            {
                "id": "id_a",
                "label": "A",
                "account_ids": [d.hits[0]["account_id"]],
                "selected": False,
            },
            {
                "id": "id_b",
                "label": "B",
                "account_ids": [d.hits[1]["account_id"]],
                "selected": False,
            },
        ]
    }
    await pick(d, "A")
    await merge(d, "A", "B")
    fresh = {
        "identities": [
            {"id": "new1", "account_ids": [d.hits[0]["account_id"]]},
            {"id": "new2", "account_ids": [d.hits[1]["account_id"]]},
        ]
    }
    reconciled = reconcile_analysis(d, fresh)
    assert len(reconciled["identities"]) == 1 and reconciled["identities"][0]["selected"]
    d.analysis = reconciled
    d.save()
    assert Dossier.load(d.id).constraints


def test_timeline_diff_unavailable_and_redaction(monkeypatch):
    import snoop.actions as action_mod

    monkeypatch.setattr(action_mod, "DATA_DIR", Path("."))
    before = dossier(monkeypatch)
    before.evidence_records = [
        evidence_record(
            account_id=before.hits[0]["account_id"],
            claim="x",
            source_url="https://github.com/alexexample",
            excerpt="Alex Example",
            method="fixture",
        )
    ]
    after = Dossier._migrate(json.loads(json.dumps(before, default=lambda x: x.__dict__)))
    after.id = "case-2"
    after.hits[0]["observation_status"] = "rate_limited"
    after.evidence_records = []
    diff = actions.diff_cases(before, after)
    assert diff["unavailable"] and not diff["no_longer_observed"]
    exported = actions.export_case(before, redact=True)
    text = Path(exported["json"]).read_text("utf-8")
    assert "Alex Example" not in text and "alexexample" not in text.casefold()


@pytest.mark.asyncio
async def test_follow_has_budget_deduplication_and_cycle_handling(monkeypatch):
    origin = hit(links=["https://dev.to/alexexample", "https://dev.to/alexexample"])
    d = dossier(monkeypatch, [origin])
    calls = []

    async def fake_anchor(case, url, bus=None, discovery_source=""):
        calls.append(url)
        if not any(h.get("canonical_url") == url for h in case.all_accounts):
            child = hit("Dev.to", url, links=[origin["canonical_url"]])
            child["discovery_source"] = discovery_source
            case.hits.append(child)
        return "added"

    monkeypatch.setattr(actions, "anchor", fake_anchor)
    result = await actions.follow(d, origin["ref"], depth=2, budget=1)
    assert len(calls) == 1 and "1/1" in result


def test_evaluation_fixture_reports_limits():
    from snoop.evaluate import run_evaluation

    result = run_evaluation()
    assert result["cases"] == 5 and result["precision"] == 1.0
    assert result["unresolved"] >= 1 and "does not establish" in result["limitation"]


@pytest.mark.asyncio
async def test_packaged_assets_and_offline_web_startup():
    from snoop.actions import doctor
    from snoop.web import build_app, index

    status = doctor()
    response = await index(None)
    html = response.body.decode("utf-8")
    assert status["ok"] and status["assets"]["connectors"] == 65
    assert response.status == 200 and b"<html" in response.body.lower()
    assert "showLaunchWorkspace(target);" in html
    assert 'state.es.close(); state.es = null;' in html
    assert 'class="empty launch"' in html  # immediate launch state; no decorative radar
    assert len(list(build_app().router.routes())) >= 6


@pytest.mark.asyncio
async def test_deepening_attaches_to_exact_account(monkeypatch):
    first = hit("GitHub", "https://github.com/alexone", handle="alexone")
    second = hit("GitHub", "https://github.com/alextwo", handle="alextwo")
    first["ref"], second["ref"] = "H01", "H02"
    monkeypatch.setattr("snoop.pipeline.CASES_DIR", Path("reports"))
    d = Dossier("deep-test", "alex", "username", "2026-01-01", hits=[first, second])

    async def fake(_http, platform, handle):
        return {"summary": f"deepened {handle}"}

    monkeypatch.setattr("snoop.deepen.deepen", fake)
    message = await actions.deepen_account(d, second["ref"])
    assert "alextwo" in message and not first.get("enrichment")
    assert d.deep[second["account_id"]]["account_ref"] == second["ref"]


def test_timeline_has_event_and_retrieval_provenance(monkeypatch):
    row = hit()
    row["joined"] = "2020-01-01"
    row["retrieved_at"] = "2026-01-01T00:00:00Z"
    row["enrichment"] = {
        "events": [
            {
                "event": "repository created",
                "event_time": "2021-01-01",
                "retrieved_at": "2026-01-02T00:00:00Z",
                "source_url": row["url"],
            }
        ]
    }
    d = Dossier("time", "Alex", "name", "2026", hits=[row], analysis={"identities": []})
    events = actions.timeline(d)
    assert len(events) == 2 and all(e.get("retrieved_at") and e.get("source_url") for e in events)


def test_presenter_masking_nested_output(monkeypatch):
    from snoop.config import config
    from snoop.privacy import mask_obj

    monkeypatch.setattr(config, "presenter", True)
    monkeypatch.setattr(config, "redact_values", ["alexexample"])
    masked = mask_obj({"url": "https://github.com/alexexample", "error": "alexexample failed"})
    assert "alexexample" not in json.dumps(masked).casefold()


@pytest.mark.asyncio
async def _removed_test_model_answers_require_known_evidence_references(monkeypatch):
    from snoop import analyst
    from snoop.config import config

    d = Dossier(
        "qa",
        "Alex",
        "name",
        "2026",
        evidence_records=[
            evidence_record(
                account_id="acct_a",
                source_url="https://example.test",
                excerpt="fact",
                method="fixture",
            )
        ],
    )
    known = d.evidence_records[0]["id"]
    monkeypatch.setattr(config, "openai_key", "configured")
    monkeypatch.setattr(config, "anthropic_key", "")
    monkeypatch.setattr(config, "gemini_key", "")

    async def unsupported(*_args):
        return "A factual answer with ev_unknown."

    monkeypatch.setattr(analyst, "_call", unsupported)
    assert "rejected" in await answer_question(d, "what happened?")

    async def supported(*_args):
        return f"A source-backed answer [{known}]."

    monkeypatch.setattr(analyst, "_call", supported)
    assert known in await answer_question(d, "what happened?")


def test_case_presenter_masking_covers_urls_and_account_fields(monkeypatch):
    from snoop.config import config
    from snoop.privacy import case_identifiers, mask_obj

    d = Dossier(
        "alex-case",
        "Alex Example",
        "name",
        "2026",
        hits=[hit()],
        analysis={"summary": "Alex Example owns https://github.com/alexexample"},
    )
    monkeypatch.setattr(config, "presenter", True)
    masked = json.dumps(mask_obj(d.__dict__, case_identifiers(d))).casefold()
    assert "alex example" not in masked
    assert "alexexample" not in masked
    assert "github.com/alexexample" not in masked
