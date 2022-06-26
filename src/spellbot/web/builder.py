from __future__ import annotations

import logging
from asyncio.events import AbstractEventLoop as Loop
from datetime import datetime, timedelta
from pathlib import Path

import aiohttp_jinja2
import jinja2
import pytz
from aiohttp import web
from babel.dates import format_datetime

from ..database import initialize_connection
from ..models import import_models
from ..settings import Settings
from ..web.api import ping, record

logger = logging.getLogger(__name__)

TEMPLATES_ROOT = Path(__file__).resolve().parent / "templates"


def humanize(ts: int, offset: int, zone: str) -> str:
    d = datetime.fromtimestamp(ts / 1e3, tz=pytz.UTC) - timedelta(minutes=offset)
    try:
        d = d.replace(tzinfo=pytz.timezone(zone))
    except pytz.UnknownTimeZoneError:
        pass
    return format_datetime(d, format="long")


def build_web_app() -> web.Application:
    import_models()
    app = web.Application()
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
        ],
    )
    return app


def launch_web_server(
    settings: Settings,
    loop: Loop,
    port: int,
) -> None:  # pragma: no cover
    app = build_web_app()
    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    loop.run_until_complete(initialize_connection("spellbot-web"))
    site = web.TCPSite(runner, settings.HOST, port)
    loop.run_until_complete(site.start())
    logger.info("server running: http://%s:%s", settings.HOST, port)
