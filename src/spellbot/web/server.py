from __future__ import annotations

import asyncio
import logging
from os import getenv, getpid

from aiohttp import web
from dotenv import load_dotenv

from spellbot.logs import configure_logging

configure_logging(getenv("LOG_LEVEL") or "INFO")

from spellbot.database import initialize_connection  # noqa: E402
from spellbot.environment import running_in_pytest  # noqa: E402
from spellbot.settings import settings  # noqa: E402

from .builder import build_web_app  # noqa: E402

if not running_in_pytest():  # pragma: no cover
    load_dotenv()

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
    loop = asyncio.new_event_loop()
    loop.set_debug(debug)

    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, settings.HOST, port)
    loop.run_until_complete(site.start())
    logger.info("server running: http://%s:%s", settings.HOST, port)

    loop.run_forever()


if not running_in_pytest():  # pragma: no cover
    app.on_startup.append(on_startup)
