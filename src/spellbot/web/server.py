from __future__ import annotations

import asyncio
import logging
from os import getpid

import uvloop
from aiohttp import web

from spellbot.database import initialize_connection
from spellbot.environment import running_in_pytest
from spellbot.logs import configure_logging
from spellbot.settings import settings
from spellbot.tracing import configure_tracing

from .builder import build_web_app

configure_logging(settings.LOG_LEVEL)
configure_tracing()

logger = logging.getLogger(__name__)


# gunicorn entrypoint, it needs an "app" object. See start.sh for details.
app = build_web_app()


async def on_startup(_app: web.Application) -> None:
    await initialize_connection(
        f"spellbot-web-{getpid()}",
        run_migrations=False,  # let the bot handle this
    )


def launch_dev_server(debug: bool, port: int) -> None:  # pragma: no cover
    """Run development server. For production, use gunicorn (see start.sh)."""

    async def run_server() -> None:
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, settings.HOST, port)
        await site.start()
        logger.info("server running: http://%s:%s", settings.HOST, port)
        # Run forever by waiting on an event that never gets set
        await asyncio.Event().wait()

    if settings.DISABLE_UVLOOP:
        asyncio.run(run_server(), debug=debug)
    else:
        uvloop.run(run_server(), debug=debug)


if not running_in_pytest():  # pragma: no cover
    app.on_startup.append(on_startup)
