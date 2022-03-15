from __future__ import annotations

import asyncio
import logging
from os import getenv, getpid

from dotenv import load_dotenv

from ..logs import configure_logging

configure_logging(getenv("LOG_LEVEL") or "INFO")

from ..database import initialize_connection
from ..environment import running_in_pytest
from . import build_web_app

if not running_in_pytest():  # pragma: no cover
    load_dotenv()

logger = logging.getLogger(__name__)
app = build_web_app()
loop = asyncio.new_event_loop()
loop.run_until_complete(
    initialize_connection(
        f"spellbot-web-{getpid()}",
        run_migrations=False,  # let the bot handle this
    ),
)
