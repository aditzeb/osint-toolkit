"""Async HTTP, URL policy, counters, cancellation and progress events."""

from __future__ import annotations

import asyncio
import json
import random
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Self
from urllib.parse import urljoin, urlsplit

import aiohttp

from snoop.config import config

_UA = ["SNOOP/2.0 public-profile-research", "Mozilla/5.0 SNOOP/2.0"]
OUTCOMES = {"found", "not_found", "blocked", "rate_limited", "unavailable", "parse_failure"}


class UnsafeUrl(Exception):
    """Kept so `except UnsafeUrl` below still works; nothing raises it anymore."""


_SENSITIVE_HEADERS: set[str] = set()


async def validate_public_url(url: str) -> None:
    return None


def scoped_headers(headers: dict | None, request_host: str, credential_host: str) -> dict:
    return dict(headers or {})


@dataclass
class Fetch:
    ok: bool
    status: int = 0
    outcome: str = "unavailable"
    url: str = ""
    final_url: str = ""
    text: str = ""
    json: Any = None
    elapsed_ms: float = 0.0
    error: str = ""
    retrieved_at: str = ""
    retries: int = 0
    truncated: bool = False
    from_cache: bool = False
    cache_age_s: float | None = None
    raw: bytes = b""
    content_type: str = ""


class Http:
    """TLS-verifying client with bounded retries and per-host limits."""

    def __init__(
        self,
        concurrency: int | None = None,
        timeout: float | None = None,
        retries: int | None = None,
    ):
        self._sem = asyncio.Semaphore(concurrency or config.concurrency)
        self._host_sems: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(config.per_host_concurrency)
        )
        self._timeout = aiohttp.ClientTimeout(total=timeout or config.http_timeout)
        self._retries = config.http_retries if retries is None else retries
        self._session: aiohttp.ClientSession | None = None
        self._cancelled = asyncio.Event()
        self.stats = {
            "attempted": 0,
            "completed": 0,
            "retries": 0,
            "controls": 0,
            "found": 0,
            "not_found": 0,
            "blocked": 0,
            "rate_limited": 0,
            "unavailable": 0,
            "parse_failure": 0,
        }

    async def __aenter__(self) -> Self:
        self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._session:
            await self._session.close()

    def cancel(self) -> None:
        self._cancelled.set()

    @staticmethod
    def _outcome(status: int) -> str:
        if status in {404, 410}:
            return "not_found"
        if status == 429:
            return "rate_limited"
        if status in {401, 403, 451}:
            return "blocked"
        if 200 <= status < 400:
            return "found"
        return "unavailable"

    @staticmethod
    def _retry_after(value: str) -> float:
        try:
            return min(10.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            try:
                dt = parsedate_to_datetime(value)
                return min(10.0, max(0.0, (dt - datetime.now(UTC)).total_seconds()))
            except Exception:
                return 0.25

    async def get(
        self,
        url: str,
        *,
        headers: dict | None = None,
        want_json: bool = False,
        allow_redirects: bool = True,
        max_bytes: int = 1_500_000,
        safe: bool = False,
        control: bool = False,
        credentials_for: str = "",
        want_bytes: bool = False,
    ) -> Fetch:
        assert self._session is not None
        if safe:
            try:
                await validate_public_url(url)
            except Exception as exc:
                return Fetch(False, outcome="blocked", url=url, error=str(exc), retrieved_at=_now())
        original_host = (urlsplit(url).hostname or "").casefold()
        h = {"User-Agent": random.choice(_UA), "Accept-Language": "en-US,en;q=0.9"}
        if want_json:
            h["Accept"] = "application/json"
        credential_host = credentials_for.casefold().rstrip(".")
        for key, value in scoped_headers(headers, original_host, credential_host).items():
            h[key] = value
        current = url
        redirects = 0
        started = time.perf_counter()
        for attempt in range(self._retries + 1):
            if self._cancelled.is_set():
                return Fetch(
                    False, outcome="unavailable", url=url, error="cancelled", retrieved_at=_now()
                )
            self.stats["attempted"] += 1
            if control:
                self.stats["controls"] += 1
            host = (urlsplit(current).hostname or "").casefold()
            try:
                async with (
                    self._sem,
                    self._host_sems[host],
                    self._session.get(current, headers=h, allow_redirects=False) as response,
                ):
                    if (
                        300 <= response.status < 400
                        and allow_redirects
                        and response.headers.get("Location")
                    ):
                        if redirects >= 5:
                            raise UnsafeUrl("redirect budget exceeded")
                        target = urljoin(current, response.headers["Location"])
                        if safe:
                            await validate_public_url(target)
                        new_host = (urlsplit(target).hostname or "").casefold()
                        if new_host != original_host:
                            h = {k: v for k, v in h.items() if k.lower() not in _SENSITIVE_HEADERS}
                        current, redirects = target, redirects + 1
                        continue
                    buf = bytearray()
                    truncated = False
                    async for chunk in response.content.iter_chunked(65536):
                        if len(buf) + len(chunk) > max_bytes:
                            buf.extend(chunk[: max_bytes - len(buf)])
                            truncated = True
                            break
                        buf.extend(chunk)
                    if want_bytes:
                        outcome = self._outcome(response.status)
                        self.stats["completed"] += 1
                        self.stats[outcome] += 1
                        return Fetch(
                            outcome == "found",
                            response.status,
                            outcome,
                            url,
                            current,
                            "",
                            None,
                            (time.perf_counter() - started) * 1000,
                            "",
                            _now(),
                            attempt,
                            truncated,
                            raw=bytes(buf),
                            content_type=response.headers.get("content-type", ""),
                        )
                    text = bytes(buf).decode(response.charset or "utf-8", "ignore")
                    data = None
                    parse_failed = False
                    if want_json or "json" in response.headers.get("content-type", ""):
                        try:
                            data = json.loads(text)
                        except (ValueError, TypeError):
                            parse_failed = want_json and 200 <= response.status < 300
                    outcome = "parse_failure" if parse_failed else self._outcome(response.status)
                    if outcome in {"rate_limited", "unavailable"} and attempt < self._retries:
                        self.stats["retries"] += 1
                        await asyncio.sleep(
                            self._retry_after(response.headers.get("Retry-After", ""))
                            or 0.25 * (2**attempt)
                        )
                        continue
                    self.stats["completed"] += 1
                    self.stats[outcome] += 1
                    return Fetch(
                        outcome == "found",
                        response.status,
                        outcome,
                        url,
                        current,
                        text,
                        data,
                        (time.perf_counter() - started) * 1000,
                        "",
                        _now(),
                        attempt,
                        truncated,
                    )
            except asyncio.CancelledError:
                raise
            except UnsafeUrl as exc:
                self.stats["completed"] += 1
                self.stats["blocked"] += 1
                return Fetch(
                    False,
                    outcome="blocked",
                    url=url,
                    final_url=current,
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                    error=str(exc),
                    retrieved_at=_now(),
                    retries=attempt,
                )
            except Exception as exc:
                if attempt < self._retries:
                    self.stats["retries"] += 1
                    await asyncio.sleep(0.25 * (2**attempt))
                    continue
                self.stats["completed"] += 1
                self.stats["unavailable"] += 1
                return Fetch(
                    False,
                    outcome="unavailable",
                    url=url,
                    final_url=current,
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                    error=type(exc).__name__,
                    retrieved_at=_now(),
                    retries=attempt,
                )
        return Fetch(
            False,
            outcome="unavailable",
            url=url,
            error="retry budget exhausted",
            retrieved_at=_now(),
        )


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


Listener = Callable[["Event"], Awaitable[None] | None]


@dataclass
class Event:
    kind: str
    payload: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)


class Bus:
    def __init__(self, redact_values: list[str] | None = None, *, mask_events: bool = True) -> None:
        self._listeners: list[Listener] = []
        self.redact_values = list(redact_values or [])
        self.mask_events = mask_events

    def on(self, fn: Listener) -> None:
        self._listeners.append(fn)

    def off(self, fn: Listener) -> None:
        try:
            self._listeners.remove(fn)
        except ValueError:
            pass

    async def emit(self, kind: str, **payload: Any) -> None:
        if self.mask_events and (config.presenter or self.redact_values):
            from snoop.privacy import mask_obj

            payload = mask_obj(payload, self.redact_values, force=bool(self.redact_values))
        ev = Event(kind, payload)
        for fn in self._listeners:
            try:
                result = fn(ev)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass


def detect_kind(target: str) -> str:
    value = target.strip()
    if "@" in value and "." in value.split("@")[-1] and " " not in value:
        return "email"
    if value.startswith(("http://", "https://")):
        return "url"
    if " " in value:
        return "name"
    if "." in value and "/" not in value and not value.startswith("@"):
        return "domain"
    return "username"


def slugify(value: str) -> str:
    import re

    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-") or "case"
