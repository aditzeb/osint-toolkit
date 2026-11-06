"""FastAPI application: JSON API + static single-page UI on one port.

Reuses the shared `Engine` - no scan logic lives here. Errors are sanitized so
no stack traces leak to the browser.
"""

from __future__ import annotations

from importlib import resources

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from .. import __version__
from ..core.engine import Engine
from ..core.logging import get_logger
from ..core.parser import ParseError
from ..core.report import to_markdown

log = get_logger("web")


class ScanRequest(BaseModel):
    number: str
    country: str | None = None
    no_cache: bool = False
    no_footprint: bool = False
    no_ai: bool = False
    presence: bool = False  # active probing - authorized use only
    discord: bool = False  # push result to server-configured webhook
    ask: str | None = None


def create_app() -> FastAPI:
    app = FastAPI(title="Numint", version=__version__)
    engine = Engine()

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return _index_html()

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/api/providers")
    async def providers() -> dict:
        from ..ai.base import get_llm_classes

        settings = engine.settings
        llm = []
        for name, cls in get_llm_classes().items():
            inst = cls(settings)
            llm.append(
                {
                    "name": name,
                    "env_key": cls.env_key,
                    "configured": inst.is_configured(),
                }
            )
        return {"data": engine.provider_infos(), "llm": llm}

    @app.post("/api/scan")
    async def scan(req: ScanRequest) -> JSONResponse:
        try:
            profile = await engine.scan(
                req.number,
                default_region=req.country.upper() if req.country else None,
                use_cache=not req.no_cache,
                with_footprint=not req.no_footprint,
                with_presence=req.presence,
                with_dorking=True,  # dork links, opened by the "open sites" button
                with_sites=True,  # all lookup sites; the UI offers "open all"
                sites_top_only=False,
                with_ai=not req.no_ai,
                ask=req.ask,
            )
        except ParseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # sanitize - never leak internals
            log.exception("scan failed")
            raise HTTPException(
                status_code=500, detail=f"Scan failed: {exc.__class__.__name__}"
            ) from exc

        # Optional Discord push. URL is server-side config only - never taken
        # from the request - and a failure here must not fail the scan.
        if req.discord:
            url = engine.settings.discord_webhook_url
            if url:
                from ..integrations import send_discord_async

                try:
                    await send_discord_async(profile, url)
                except Exception:  # noqa: BLE001
                    log.warning("discord push failed")

        return JSONResponse(profile.model_dump(mode="json"))

    @app.post("/api/scan/markdown")
    async def scan_markdown(req: ScanRequest) -> dict:
        try:
            profile = await engine.scan(
                req.number,
                default_region=req.country.upper() if req.country else None,
                use_cache=not req.no_cache,
                with_footprint=not req.no_footprint,
                with_ai=not req.no_ai,
            )
        except ParseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"markdown": to_markdown(profile)}

    return app


def _index_html() -> str:
    return (
        resources.files("numint.web.static")
        .joinpath("index.html")
        .read_text(encoding="utf-8")
    )
