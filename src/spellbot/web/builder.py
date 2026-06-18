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
from spellbot.i18n import best_locale, t
from spellbot.models import import_models
from spellbot.redis_client import close_redis
from spellbot.settings import settings
from spellbot.web.api import (
    admin_auth,
    analytics,
    audit,
    dashboard,
    ping,
    queues,
    record,
    rest,
    status,
    viewer_auth,
)
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
    audit.routes,
    rest.routes,
    admin_auth.routes,
    dashboard.routes,
    queues.routes,
    viewer_auth.routes,
]


def humanize(ts: int, offset: int, zone: str) -> str:
    d = datetime.fromtimestamp(ts / 1e3, tz=UTC) - timedelta(minutes=offset)
    with suppress(ZoneInfoNotFoundError):
        d = d.replace(tzinfo=ZoneInfo(zone))
    return format_datetime(d, format="long", locale=settings.LOCALE)


async def i18n_context_processor(request: web.Request) -> dict[str, object]:
    """
    Expose a request-scoped translator and language to every template.

    The viewer's language is negotiated from the browser's `Accept-Language`
    header so server-rendered pages arrive already translated. Templates call
    `{{ t("web.some.key") }}`; anything without a `web` entry falls back to `en`.
    """
    locale = best_locale(request.headers.get("Accept-Language"))

    def translate(key: str, **kwargs: object) -> str:
        return t(key, locale=locale, **kwargs)

    return {"lang": locale, "t": translate}


@web.middleware
async def security_headers_middleware(
    request: web.Request,
    handler: Handler,
) -> web.StreamResponse:
    """Add security headers to all responses."""
    response = await handler(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


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


def concat_js(*names: str) -> str:
    """Concatenate template-dir JS files in order, separated by newlines."""
    return "\n".join((TEMPLATES_ROOT / name).read_text(encoding="utf-8") for name in names)


async def serve_analytics_js(_: web.Request) -> web.Response:
    """
    Serve the analytics JavaScript file.

    No-cache headers (like `dashboard.js`) ensure viewers pick up new analytics code
    immediately after a deploy without a hard refresh, instead of running a stale copy.
    """
    return web.Response(
        body=concat_js("analytics_pure.js", "analytics.js"),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Content-Type": "application/javascript; charset=utf-8",
        },
    )


async def serve_dashboard_js(_: web.Request) -> web.Response:
    """
    Serve the admin dashboard JavaScript file.

    Served publicly (the file contains no secrets — only chart wiring and
    fetch calls against `/admin/dashboard/*`, which are themselves gated by
    `admin_auth_middleware`). No-cache headers ensure admins pick up new
    dashboard code immediately after a deploy without a hard refresh.
    """
    return web.Response(
        body=concat_js("dashboard_pure.js", "dashboard.js"),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Content-Type": "application/javascript; charset=utf-8",
        },
    )


def build_web_app() -> web.Application:
    import_models()
    app = web.Application(
        middlewares=[
            security_headers_middleware,
            auth_middleware,
        ],
    )
    # `setup_admin_sessions` appends the aiohttp_session middleware;
    # so it must come before `admin_auth_middleware`
    admin_auth.setup_admin_sessions(app)
    app.middlewares.append(admin_auth.admin_auth_middleware)
    app.middlewares.append(aiohttp_jinja2.context_processors_middleware)
    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader(TEMPLATES_ROOT),
        filters={"humanize": humanize, "wait": queues.format_wait},
    )
    app[aiohttp_jinja2.APP_CONTEXT_PROCESSORS_KEY] = (i18n_context_processor,)
    for routes in ALL_ROUTES:
        app.router.add_routes(routes)
    app.router.add_get("/analytics.js", serve_analytics_js)
    app.router.add_get("/dashboard.js", serve_dashboard_js)
    app.on_cleanup.append(close_shared_clients)
    return app


async def close_shared_clients(_app: web.Application) -> None:
    await rest.close_http_session()
    await close_redis()
