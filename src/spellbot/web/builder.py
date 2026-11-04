# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
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
    stats,
    status,
    viewer_auth,
)
from spellbot.web.api.oauth import oauth_configured, safe_relative_path
from spellbot.web.tools import rate_limited

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from aiohttp.typedefs import Handler

logger = logging.getLogger(__name__)

TEMPLATES_ROOT = Path(__file__).resolve().parent / "templates"

# Endpoints readable cross-origin. Every one is public, unauthenticated and
# read-only, and is already served to anonymous visitors, so `*` exposes nothing
# new while keeping responses cacheable (an origin-specific header would force
# `Vary: Origin`). Matched as exact paths rather than by prefix so an
# authenticated route can never pick up CORS by accident -- in particular nothing
# under `/api` or `/admin` belongs here.
PUBLIC_CORS_PATHS = frozenset({"/stats.json", "/queues.json", "/status.json"})

# Keep crawlers off the whole site. CSV exports, which are expensive to serve,
# additionally reject crawlers that ignore this (see `is_crawler`).
ROBOTS_TXT = """\
User-agent: *
Disallow: /
"""

ALL_ROUTES = [
    ping.routes,
    stats.routes,
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

    return {"lang": locale, "t": translate, "nav": await nav_context(request)}


async def nav_context(request: web.Request) -> dict[str, object]:
    """
    Build the shared site-header identity for the login/logout control.

    Exposing this globally (rather than threading it through each handler) is what
    lets the one shared header render a correct login/logout state on every public
    page. The `here` value carries the current path so both flows return the user to
    the page they were on, all through a single OAuth redirect URI.
    """
    viewer_xid, viewer_name = await viewer_auth.get_viewer(request)
    is_admin = await admin_auth.get_admin_user_xid(request) is not None
    # Return-to path only (no query string): enough to send the viewer back to the
    # page they logged in from, without reflecting arbitrary query params into the page.
    here = safe_relative_path(request.path)
    return {
        "logged_in": viewer_xid is not None,
        "xid": viewer_xid,
        "name": viewer_name,
        "is_admin": is_admin,
        "login_enabled": oauth_configured(),
        "here": here or "/queues",
    }


async def add_security_headers(request: web.Request, response: web.StreamResponse) -> None:
    """
    Add security headers to every response, including errors such as 404s.

    This runs as an `on_response_prepare` hook rather than a middleware: a middleware
    never sees the responses for exceptions raised past it (unknown routes, for one).
    It also runs after aiohttp fills in its default `Server` header, which names the
    exact Python and aiohttp versions, so the override here wins.
    """
    response.headers["Server"] = "SpellBot"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.path in PUBLIC_CORS_PATHS:
        response.headers["Access-Control-Allow-Origin"] = "*"


def forwarded_client_ip(request: web.Request, hops: int) -> str | None:
    """
    Return the client IP that the nearest `hops` trusted proxies recorded.

    Each proxy appends the address it received the request from, so the entry `hops`
    places from the right was written by a trusted proxy. Entries further left came
    from the client and could say anything. Returns None when there's no usable entry.
    """
    entries = [
        entry.strip()
        for header in request.headers.getall("X-Forwarded-For", [])
        for entry in header.split(",")
    ]
    entries = [entry for entry in entries if entry]
    if not entries:
        return None
    candidate = entries[-min(hops, len(entries))]
    try:
        return str(ip_address(candidate))
    except ValueError:
        return None


@web.middleware
async def forwarded_ip_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
    """
    Replace `request.remote` with the real client IP when behind trusted proxies.

    Behind the ALB, `request.remote` is the load balancer's own address, so every client
    would share one rate-limit bucket. `TRUSTED_PROXY_HOPS` says how many proxies to trust.
    """
    if settings.TRUSTED_PROXY_HOPS > 0 and (
        ip := forwarded_client_ip(request, settings.TRUSTED_PROXY_HOPS)
    ):
        request = request.clone(remote=ip)
    return await handler(request)


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


def serve_js(*names: str) -> Callable[[web.Request], Awaitable[web.Response]]:
    """
    Serve the concatenated template-dir JS files `names`, starting with the shared helpers.

    The files contain no secrets, only chart wiring and fetches against endpoints that are
    gated on their own. No-cache headers make viewers pick up new code right after a deploy
    instead of running a stale copy.
    """

    async def serve(_: web.Request) -> web.Response:
        return web.Response(
            body=concat_js("chart_common_pure.js", *names),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Content-Type": "application/javascript; charset=utf-8",
            },
        )

    return serve


serve_analytics_js = serve_js("analytics_pure.js", "analytics.js")
serve_dashboard_js = serve_js("dashboard_pure.js", "dashboard.js")


async def serve_robots_txt(_: web.Request) -> web.Response:
    """Serve the crawler rules for the site."""
    return web.Response(text=ROBOTS_TXT, content_type="text/plain")


def build_web_app() -> web.Application:
    import_models()
    app = web.Application(middlewares=[forwarded_ip_middleware, auth_middleware])
    app.on_response_prepare.append(add_security_headers)
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
    app.router.add_get("/robots.txt", serve_robots_txt)
    app.on_cleanup.append(close_shared_clients)
    return app


async def close_shared_clients(_app: web.Application) -> None:
    await rest.close_http_session()
    await close_redis()
