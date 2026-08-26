from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .client import BilibiliFetchError
from .config import Settings
from .rss import render_rss
from .service import BilibiliService

settings = Settings.from_env()
service = BilibiliService(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await service.close()


app = FastAPI(title="Bilibili RSS Service", version=__version__, lifespan=lifespan)
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).with_name("static")),
    name="static",
)


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Bilibili RSS Service</title>
<style>body{font:16px system-ui,sans-serif;max-width:720px;margin:48px auto;padding:0 20px;color:#172033}code{background:#f1f3f6;padding:2px 5px;border-radius:4px}a{color:#1769e0}</style></head>
<body><h1>Bilibili RSS Service</h1><p>Self-hosted RSS feeds for public Bilibili creator videos.</p>
<p>Subscribe with <code>/rss/&lt;uid&gt;</code> or open that URL in a browser.</p>
<p><a href="/health">Health</a></p></body></html>"""


@app.get("/health")
@app.get("/api/health")
async def health() -> dict[str, object]:
    return {
        "ok": True,
        "service": "bilibili-rss",
        "cacheEntries": len(service._cache),
        "cookieConfigured": bool(settings.cookie),
    }


@app.get("/api/users/{uid}/videos")
async def videos(
    uid: str,
    force: bool = Query(False),
    detail_limit: int = Query(0, ge=0, le=5),
):
    try:
        result = await service.fetch(uid, force=force, detail_limit=detail_limit)
    except BilibiliFetchError as exc:
        raise _http_error(exc) from exc
    return result.model_dump(mode="json")


@app.get("/rss", include_in_schema=False)
async def rss_index() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=307)


@app.get("/rss/{uid}")
async def rss(
    request: Request,
    uid: str,
    force: bool = Query(False),
    detail_limit: int = Query(5, ge=0, le=5),
) -> Response:
    try:
        result = await service.fetch(uid, force=force, detail_limit=detail_limit)
    except BilibiliFetchError as exc:
        raise _http_error(exc) from exc
    return Response(
        render_rss(result, self_url=str(request.url.replace(query=""))),
        media_type="application/rss+xml; charset=utf-8",
    )


def _http_error(exc: BilibiliFetchError) -> HTTPException:
    return HTTPException(
        status_code=400 if exc.error_type == "invalid_input" else 502,
        detail={
            "message": str(exc),
            "errorType": exc.error_type,
            "attempts": exc.attempts,
        },
    )
