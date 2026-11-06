"""Scan engine - the single pipeline used by BOTH the CLI and the web layer.

parse -> run configured providers concurrently -> aggregate -> footprint -> AI.
No scan logic is duplicated anywhere else.
"""

from __future__ import annotations

import asyncio

import httpx

from .aggregator import aggregate
from .cache import Cache
from .config import Settings, get_settings
from .dorking import build_dorking
from .footprint import build_footprint
from .logging import get_logger
from .lookup import build_sites
from .models import (
    ParsedNumber,
    Profile,
    ProviderReport,
    ProviderResult,
    ProviderStatus,
)
from .parser import parse_number
from .ratelimit import RateLimiter
from .registry import discover

log = get_logger("engine")

_USER_AGENT = "numint/0.1 (+https://github.com/whoamitang/numint)"


class Engine:
    """Reusable scan engine. Construct once, call `scan` many times."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.cache = Cache()
        self.rate_limiter = RateLimiter(self.settings.rate_limit_per_sec)
        self._provider_classes = discover()

    # -- provider introspection (used by `numint providers` and the UI) -----
    def provider_infos(self) -> list[dict]:
        infos = []
        for cls in self._provider_classes:
            inst = cls(self.settings)
            infos.append(
                {
                    "name": inst.name,
                    "requires_key": inst.requires_key,
                    "env_key": inst.env_key,
                    "optional": getattr(inst, "optional", False),
                    "configured": inst.is_configured(),
                    "signup_url": getattr(inst, "signup_url", None),
                }
            )
        return infos

    async def scan(
        self,
        raw_number: str,
        *,
        default_region: str | None = None,
        use_cache: bool = True,
        with_offline: bool = True,
        with_api: bool = True,
        with_footprint: bool = True,
        with_dorking: bool = False,
        with_presence: bool = False,
        with_sites: bool = False,
        sites_top_only: bool = True,
        with_ai: bool = True,
        ask: str | None = None,
    ) -> Profile:
        """Run the pipeline for a single number.

        The layers are opt-in-able: `with_offline` runs the built-in
        libphonenumber provider, `with_api` runs the key'd data providers,
        `with_dorking` builds search-engine dork links, `with_sites` builds the
        reverse-lookup site links (for the `--lookup` tool). `with_presence` is
        authorized-use-only and actively probes third-party sites. Everything
        that only builds URLs makes no network calls.
        """
        number = parse_number(raw_number, default_region)

        results, reports = await self._run_providers(
            number, use_cache, with_offline, with_api
        )

        profile = aggregate(number, results)
        profile.providers = reports

        if with_presence:
            profile.presence = await self._run_presence(number)

        if with_footprint:
            profile.footprint = build_footprint(number)

        if with_dorking:
            profile.dorking = build_dorking(number)

        if with_sites:
            profile.sites = build_sites(number, top_only=sites_top_only)

        if with_ai:
            # Imported lazily so the AI stack is optional at import time.
            from ..ai import answer_question, run_ai_analysis

            if ask:
                profile.ai_analysis = await answer_question(
                    profile, ask, self.settings
                )
            else:
                profile.ai_analysis = await run_ai_analysis(
                    profile, self.settings
                )

        return profile

    async def _run_providers(
        self,
        number: ParsedNumber,
        use_cache: bool,
        with_offline: bool = True,
        with_api: bool = True,
    ) -> tuple[list[ProviderResult], list[ProviderReport]]:
        instances = [cls(self.settings) for cls in self._provider_classes]
        reports: list[ProviderReport] = []
        active = []
        results: list[ProviderResult] = []

        for inst in instances:
            # A provider is "offline" (the built-in one) when it needs no key.
            is_offline = not inst.requires_key
            if is_offline and not with_offline:
                continue
            if not is_offline and not with_api:
                continue
            if not inst.is_configured():
                reports.append(
                    ProviderReport(
                        name=inst.name,
                        status=ProviderStatus.SKIPPED,
                        requires_key=inst.requires_key,
                        reason="no API key configured",
                    )
                )
                continue
            active.append(inst)

        timeout = self.settings.provider_timeout
        headers = {"User-Agent": _USER_AGENT}
        async with httpx.AsyncClient(
            timeout=timeout, headers=headers, follow_redirects=True
        ) as client:

            async def run_one(inst) -> ProviderResult:
                cache_key = f"{inst.name}:{number.e164}"
                if use_cache:
                    cached = self.cache.get(cache_key)
                    if cached is not None:
                        return ProviderResult(**cached)
                await self.rate_limiter.acquire(inst.name)
                try:
                    res = await asyncio.wait_for(
                        inst.lookup(number, client), timeout=timeout + 2
                    )
                except TimeoutError:
                    res = ProviderResult(
                        source=inst.name,
                        ok=False,
                        status=ProviderStatus.ERROR,
                        error=f"timed out after {timeout}s",
                    )
                if use_cache and res.ok:
                    self.cache.set(
                        cache_key,
                        res.model_dump(mode="json"),
                        self.settings.cache_ttl,
                    )
                return res

            gathered = await asyncio.gather(
                *(run_one(inst) for inst in active), return_exceptions=True
            )

        for inst, res in zip(active, gathered, strict=False):
            if isinstance(res, Exception):
                res = ProviderResult(
                    source=inst.name,
                    ok=False,
                    status=ProviderStatus.ERROR,
                    error=f"{res.__class__.__name__}: {res}",
                )
            results.append(res)
            status = (
                ProviderStatus.RAN if res.ok else ProviderStatus.ERROR
            )
            reports.append(
                ProviderReport(
                    name=inst.name,
                    status=status,
                    requires_key=inst.requires_key,
                    reason=res.error,
                    elapsed_ms=res.elapsed_ms,
                )
            )

        return results, reports

    async def _run_presence(self, number: ParsedNumber) -> list:
        """Run every registered presence check concurrently (isolated)."""
        from ..presence.base import discover_presence

        checks = [cls() for cls in discover_presence()]
        if not checks:
            return []

        timeout = self.settings.provider_timeout
        headers = {"User-Agent": _USER_AGENT}
        async with httpx.AsyncClient(
            timeout=timeout, headers=headers, follow_redirects=True
        ) as client:

            async def run_one(chk):
                await self.rate_limiter.acquire(f"presence:{chk.site}")
                try:
                    return await asyncio.wait_for(
                        chk.check(number, client), timeout=timeout + 2
                    )
                except TimeoutError:
                    from .models import PresenceResult

                    return PresenceResult(
                        site=chk.site,
                        registered="error",
                        method=chk.method,
                        error=f"timed out after {timeout}s",
                    )

            gathered = await asyncio.gather(
                *(run_one(c) for c in checks), return_exceptions=True
            )

        from .models import PresenceResult

        out = []
        for chk, res in zip(checks, gathered, strict=False):
            if isinstance(res, Exception):
                res = PresenceResult(
                    site=chk.site,
                    registered="error",
                    method=chk.method,
                    error=f"{res.__class__.__name__}: {res}",
                )
            out.append(res)
        return out


def run_scan(raw_number: str, **kwargs) -> Profile:
    """Sync convenience wrapper around `Engine.scan` for the CLI."""
    engine = Engine()
    return asyncio.run(engine.scan(raw_number, **kwargs))
