"""Web search providers behind one shared, honestly-labelled interface.

Engines are identified by what actually produced the results:
``google`` is always "Google via SerpAPI", ``brave`` is "Brave Search", and
manual result imports are labelled "manual assistance", never as an automated
search that completed. Missing credentials produce explicit ``missing_key``
states instead of a silent fallback to an unlabelled engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import quote, urlencode

from snoop.config import config
from snoop.core import Http
from snoop.model import query_id, utcnow

ENGINE_LABELS = {
    "google": "Google via SerpAPI",
    "brave": "Brave Search",
    "manual": "manual assistance",
}

ENGINE_OPERATORS: dict[str, list[str]] = {
    "google": ['"exact phrase"', "site:", "intitle:", "inurl:", "filetype:", "-exclude", "OR"],
    "brave": ['"exact phrase"', "site:", "intitle:", "-exclude"],
}

MAX_COUNT = {"google": 20, "brave": 20}
MAX_PAGE = {"google": 4, "brave": 9}

SETUP_HINTS = {
    "google": "set SERPAPI_KEY (https://serpapi.com/search-api) in .env or `snoop providers`",
    "brave": "set BRAVE_SEARCH_API_KEY (https://api-dashboard.search.brave.com) in .env or `snoop providers`",
}


@dataclass
class SearchResult:
    rank: int
    title: str
    url: str
    snippet: str = ""
    source_date: str = ""
    retrieved_at: str = ""

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source_date": self.source_date,
            "retrieved_at": self.retrieved_at,
        }


@dataclass
class SearchResponse:
    engine: str
    provider: str
    query: str
    outcome: str  # found | empty | missing_key | auth_failure | rate_limited | blocked | unavailable | parse_failure | unsupported_engine
    results: list[SearchResult] = field(default_factory=list)
    error: str = ""
    retrieved_at: str = ""

    @property
    def ok(self) -> bool:
        return self.outcome == "found"

    def to_dict(self) -> dict:
        return {
            "engine": self.engine,
            "provider": self.provider,
            "query": self.query,
            "outcome": self.outcome,
            "error": self.error,
            "retrieved_at": self.retrieved_at,
            "results": [r.to_dict() for r in self.results],
        }


def engine_ready(engine: str) -> tuple[bool, str]:
    """(ready, honest reason) without ever revealing secret values."""
    config.refresh_provider_credentials()
    engine = (engine or "").casefold()
    if engine == "google":
        return (True, "key configured") if config.serpapi_key else (False, SETUP_HINTS["google"])
    if engine == "brave":
        return (
            (True, "key configured") if config.brave_search_key else (False, SETUP_HINTS["brave"])
        )
    if engine == "manual":
        return True, "no key required; results are supplied by the analyst"
    return False, f"unknown engine {engine!r}"


def available_engines() -> list[dict]:
    rows = []
    for engine, label in ENGINE_LABELS.items():
        ready, reason = engine_ready(engine)
        rows.append(
            {
                "engine": engine,
                "label": label,
                "ready": ready,
                "reason": reason,
                "operators": ENGINE_OPERATORS.get(engine, []),
            }
        )
    return rows


def any_engine_ready() -> bool:
    return any(engine_ready(e)[0] for e in ENGINE_LABELS if e != "manual")


def resolve_engine(engine: str | None = None) -> str:
    """Requested engine, else configured default, else the other real engine."""
    engine = (engine or "").strip().casefold()
    aliases = {"serpapi": "google", "google": "google", "brave": "brave"}
    engine = aliases.get(engine, engine)
    if engine in ENGINE_LABELS:
        return engine
    default = config.search_engine if config.search_engine in ENGINE_LABELS else "google"
    if default in {"google", "brave"} and not engine_ready(default)[0]:
        other = "brave" if default == "google" else "google"
        if engine_ready(other)[0]:
            return other
    return default


def fallback_engine(engine: str) -> str | None:
    """The other real engine, only when fallback is allowed and configured."""
    if not config.search_fallback:
        return None
    other = "brave" if engine == "google" else "google"
    return other if engine_ready(other)[0] else None


async def web_search(
    query: str,
    engine: str | None = None,
    *,
    http: Http | None = None,
    count: int = 10,
    page: int = 0,
    language: str = "",
    region: str = "",
    allow_fallback: bool = True,
) -> SearchResponse:
    """Run one query on one engine. Snippets are leads, not substantiated claims."""
    if http is not None:
        return await _search_once(
            query, engine, http, count, page, language, region, allow_fallback
        )
    async with Http(concurrency=2) as own:
        return await _search_once(
            query, engine, own, count, page, language, region, allow_fallback
        )


async def _search_once(
    query: str,
    engine: str | None,
    http: Http,
    count: int,
    page: int,
    language: str,
    region: str,
    allow_fallback: bool,
) -> SearchResponse:
    engine = resolve_engine(engine)
    count = max(1, min(MAX_COUNT.get(engine, 10), int(count)))
    page = max(0, min(MAX_PAGE.get(engine, 4), int(page)))
    language = language or config.search_language
    region = region or config.search_region

    if engine == "google":
        response = await _serpapi_google(query, http, count, page, language, region)
    elif engine == "brave":
        response = await _brave(query, http, count, page, language, region)
    else:
        response = SearchResponse(
            engine, ENGINE_LABELS.get(engine, engine), query, "unsupported_engine"
        )

    if (
        allow_fallback
        and response.outcome in {"missing_key", "rate_limited", "unavailable"}
        and (other := fallback_engine(engine))
    ):
        retry = await _search_once(
            query, other, http, count, page, language, region, allow_fallback=False
        )
        retry.error = (
            f"{engine} unavailable ({response.outcome}); retried on {other}. " + retry.error
        ).strip()
        return retry
    return response


def _serpapi_url(query: str, count: int, page: int, language: str, region: str) -> str:
    params = {
        "engine": "google",
        "q": query,
        "num": str(count),
        "start": str(page * count),
        "api_key": config.serpapi_key,
    }
    if language:
        params["hl"] = language
    if region:
        params["gl"] = region
    return "https://serpapi.com/search.json?" + urlencode(params)


async def _serpapi_google(
    query: str, http: Http, count: int, page: int, language: str, region: str
) -> SearchResponse:
    provider = ENGINE_LABELS["google"]
    if not config.serpapi_key:
        return SearchResponse(
            "google", provider, query, "missing_key", error=SETUP_HINTS["google"], retrieved_at=utcnow()
        )
    fetch = await http.get(
        _serpapi_url(query, count, page, language, region),
        want_json=True,
        credentials_for="serpapi.com",
    )
    now = fetch.retrieved_at or utcnow()
    if fetch.outcome != "found" or not isinstance(fetch.json, dict):
        return SearchResponse(
            "google", provider, query, fetch.outcome, error=fetch.error, retrieved_at=now
        )
    error = fetch.json.get("error", "")
    if error:
        return SearchResponse(
            "google",
            provider,
            query,
            "auth_failure" if fetch.json.get("status") in {"Invalid key", 401} else "unavailable",
            error=str(error)[:200],
            retrieved_at=now,
        )
    results: list[SearchResult] = []
    for item in fetch.json.get("organic_results") or []:
        if isinstance(item, dict) and item.get("link"):
            supplied_rank = item.get("position")
            results.append(
                SearchResult(
                    rank=(
                        int(supplied_rank)
                        if isinstance(supplied_rank, int) and supplied_rank > 0
                        else page * count + len(results) + 1
                    ),
                    title=str(item.get("title", ""))[:300],
                    url=str(item["link"]),
                    snippet=str(item.get("snippet", ""))[:600],
                    source_date=str(item.get("date", ""))[:40],
                    retrieved_at=now,
                )
            )
    return SearchResponse(
        "google", provider, query, "found" if results else "empty", results=results, retrieved_at=now
    )


async def _brave(
    query: str, http: Http, count: int, page: int, language: str, region: str
) -> SearchResponse:
    provider = ENGINE_LABELS["brave"]
    if not config.brave_search_key:
        return SearchResponse(
            "brave", provider, query, "missing_key", error=SETUP_HINTS["brave"], retrieved_at=utcnow()
        )
    params = {"q": query, "count": str(count), "offset": str(page)}
    if language:
        params["search_lang"] = language
    if region:
        params["country"] = region
    fetch = await http.get(
        "https://api.search.brave.com/res/v1/web/search?" + urlencode(params),
        want_json=True,
        headers={
            "X-Subscription-Token": config.brave_search_key,
            "Accept": "application/json",
        },
        credentials_for="api.search.brave.com",
    )
    now = fetch.retrieved_at or utcnow()
    if fetch.outcome != "found" or not isinstance(fetch.json, dict):
        if fetch.status in {401, 403}:
            return SearchResponse(
                "brave", provider, query, "auth_failure", error=fetch.error, retrieved_at=now
            )
        return SearchResponse(
            "brave", provider, query, fetch.outcome, error=fetch.error, retrieved_at=now
        )
    results: list[SearchResult] = []
    for item in (fetch.json.get("web", {}) or {}).get("results", []) or []:
        if not isinstance(item, dict) or not item.get("url"):
            continue
        results.append(
            SearchResult(
                rank=page * count + len(results) + 1,
                title=str(item.get("title", ""))[:300],
                url=str(item["url"]),
                snippet=str(item.get("description", ""))[:600],
                source_date=str(item.get("age", item.get("date", "")))[:40],
                retrieved_at=now,
            )
        )
    return SearchResponse(
        "brave", provider, query, "found" if results else "empty", results=results, retrieved_at=now
    )


def manual_results(
    query: str,
    result_urls: list[str],
    *,
    titles: dict[str, str] | None = None,
    via: str = "user-import",
    query_link: str = "",
) -> SearchResponse:
    """Build a labelled manual-assistance result set the analyst supplied.

    This is assistance, not a completed automated search; the engine label and
    provenance stay explicit wherever these results are displayed.
    """
    titles = titles or {}
    now = utcnow()
    rows = [
        SearchResult(
            rank=index,
            title=titles.get(url, url.rsplit("/", 1)[-1] or url)[:300],
            url=url,
            snippet="supplied manually by the analyst; snippet not captured",
            source_date="",
            retrieved_at=now,
        )
        for index, url in enumerate(dict.fromkeys(result_urls), 1)
        if url.strip()
    ]
    response = SearchResponse(
        "manual",
        ENGINE_LABELS["manual"],
        query,
        "found" if rows else "empty",
        results=rows,
        retrieved_at=now,
    )
    response.extra_query_link = query_link  # type: ignore[attr-defined]
    response.extra_via = via  # type: ignore[attr-defined]
    return response


def query_record(response: SearchResponse, *, via: str = "", query_link: str = "") -> dict:
    """Persist an executed search with full provenance for the case file."""
    return {
        "id": query_id(response.engine, response.query),
        "engine": response.engine,
        "provider": response.provider,
        "query": response.query,
        "outcome": response.outcome,
        "error": response.error,
        "retrieved_at": response.retrieved_at,
        "via": via or getattr(response, "extra_via", ""),
        "query_link": query_link or getattr(response, "extra_query_link", ""),
        "results": [r.to_dict() for r in response.results],
    }


def search_url_for(engine: str, query: str) -> str:
    """Human-facing query link for manual assistance workflows."""
    engine = engine.casefold()
    if engine == "google":
        return "https://www.google.com/search?q=" + quote(query)
    if engine == "brave":
        return "https://search.brave.com/search?q=" + quote(query)
    return ""
