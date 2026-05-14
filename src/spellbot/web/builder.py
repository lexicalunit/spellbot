from __future__ import annotations

import logging
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import aiohttp_jinja2
import jinja2
from aiohttp import web
from babel.dates import format_datetime

from spellbot import services
from spellbot.database import db_session_manager
from spellbot.models import import_models
from spellbot.redis_client import close_redis
from spellbot.settings import settings
from spellbot.web.api import analytics, ping, record, rest, status
from spellbot.web.tools import rate_limited

if TYPE_CHECKING:
    from aiohttp.typedefs import Handler

logger = logging.getLogger(__name__)

TEMPLATES_ROOT = Path(__file__).resolve().parent / "templates"

ALL_ROUTES = [
    ping.routes,
    status.routes,
    analytics.routes,
    record.routes,
    rest.routes,
]


def humanize(ts: int, offset: int, zone: str) -> str:
    d = datetime.fromtimestamp(ts / 1e3, tz=UTC) - timedelta(minutes=offset)
    with suppress(ZoneInfoNotFoundError):
        d = d.replace(tzinfo=ZoneInfo(zone))
    return format_datetime(d, format="long", locale=settings.LOCALE)


@web.middleware
async def auth_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
    # only rest endpoints require authorization
    if not request.path.startswith("/api"):
        return await handler(request)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return web.json_response({"error": "Missing or invalid Authorization header"}, status=401)

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return web.json_response({"error": "Missing or invalid Authorization header"}, status=401)
    async with db_session_manager():
        if not await services.apps.verify_token(token, request.rel_url.path):
            if await rate_limited(request):
                return web.json_response({"error": "Too many requests"}, status=429)
            return web.json_response({"error": "Unauthorized"}, status=403)

    return await handler(request)


async def serve_analytics_js(_: web.Request) -> web.FileResponse:
    """Serve the analytics JavaScript file with caching headers."""
    return web.FileResponse(
        TEMPLATES_ROOT / "analytics.js",
        headers={"Cache-Control": "public, max-age=3600"},  # 1 hour cache
    )


def build_web_app() -> web.Application:
    import_models()
    app = web.Application(middlewares=[auth_middleware])
    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader(TEMPLATES_ROOT),
        filters={"humanize": humanize},
    )
    for routes in ALL_ROUTES:
        app.router.add_routes(routes)
    app.router.add_get("/analytics.js", serve_analytics_js)
    app.on_cleanup.append(close_shared_clients)
    return app


async def close_shared_clients(_app: web.Application) -> None:
    await rest.close_http_session()
    await close_redis()
