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

from spellbot.database import db_session_manager, initialize_connection
from spellbot.models import import_models
from spellbot.services import ServicesRegistry
from spellbot.settings import settings
from spellbot.web.api import ping, record, rest
from spellbot.web.tools import rate_limited

if TYPE_CHECKING:
    from asyncio.events import AbstractEventLoop as Loop

    from aiohttp.typedefs import Handler

logger = logging.getLogger(__name__)

TEMPLATES_ROOT = Path(__file__).resolve().parent / "templates"


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

    token = auth_header.split("Bearer ")[1]
    async with db_session_manager():
        services = ServicesRegistry()
        if not await services.apps.verify_token(token):
            if await rate_limited(request):
                return web.json_response({"error": "Too many requests"}, status=429)
            return web.json_response({"error": "Unauthorized"}, status=403)

    return await handler(request)


def build_web_app() -> web.Application:
    import_models()
    app = web.Application(middlewares=[auth_middleware])
    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader(TEMPLATES_ROOT),
        filters={"humanize": humanize},
    )
    app.add_routes(
        [
            web.get(r"/", ping.endpoint),
            web.get(r"/g/{guild}/c/{channel}", record.channel_endpoint),
            web.get(r"/g/{guild}/u/{user}", record.user_endpoint),
            web.post(r"/api/game/{game}/verify", rest.game_verify_endpoint),
            web.post(r"/api/game/{game}/record", rest.game_record_endpoint),
        ],
    )
    return app


def launch_web_server(loop: Loop, port: int) -> None:  # pragma: no cover
    app = build_web_app()
    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    loop.run_until_complete(initialize_connection("spellbot-web"))
    site = web.TCPSite(runner, settings.HOST, port)
    loop.run_until_complete(site.start())
    logger.info("server running: http://%s:%s", settings.HOST, port)
