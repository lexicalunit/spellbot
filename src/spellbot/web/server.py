from __future__ import annotations

import logging
from os import getenv, getpid
from typing import TYPE_CHECKING

from dotenv import load_dotenv

from spellbot.logs import configure_logging

if TYPE_CHECKING:
    from aiohttp import web

configure_logging(getenv("LOG_LEVEL") or "INFO")

from spellbot.database import initialize_connection  # noqa: E402
from spellbot.environment import running_in_pytest  # noqa: E402

from . import build_web_app  # noqa: E402

if not running_in_pytest():  # pragma: no cover
    load_dotenv()

logger = logging.getLogger(__name__)


async def on_startup(_app: web.Application) -> None:
    await initialize_connection(
        f"spellbot-web-{getpid()}",
        run_migrations=False,  # let the bot handle this
    )


app = build_web_app()
app.on_startup.append(on_startup)
