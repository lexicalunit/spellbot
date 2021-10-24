import asyncio
import logging
import sys
from os import getenv, getpid

from dotenv import load_dotenv

from spellbot import configure_logging
from spellbot.database import initialize_connection
from spellbot.web import build_web_app

if not getenv("PYTEST_CURRENT_TEST") and "pytest" not in sys.modules:
    load_dotenv()

logger = logging.getLogger(__name__)
configure_logging(getenv("LOG_LEVEL") or "INFO")
app = build_web_app()
loop = asyncio.get_event_loop()
loop.run_until_complete(
    initialize_connection(
        f"spellbot-web-{getpid()}",
        run_migrations=False,  # let the bot handle this
    )
)
