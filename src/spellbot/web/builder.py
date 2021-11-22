import logging
from asyncio.events import AbstractEventLoop as Loop
from pathlib import Path

import aiohttp_jinja2
import jinja2
from aiohttp import web

from ..database import initialize_connection
from ..models import import_models
from ..settings import Settings
from ..web.api import ping, record

logger = logging.getLogger(__name__)

TEMPLATES_ROOT = Path(__file__).resolve().parent / "templates"


def build_web_app() -> web.Application:
    import_models()
    app = web.Application()
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(TEMPLATES_ROOT))
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
