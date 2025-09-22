from __future__ import annotations

import asyncio
import time
from os import getenv
from socket import socket

import click
import hupper
import uvloop
from dotenv import load_dotenv

from . import __version__
from .environment import running_in_pytest
from .logs import configure_logging
from .metrics import no_metrics
from .settings import settings

# load .env environment variables as early as possible
if not running_in_pytest():  # pragma: no cover
    load_dotenv()

if not getenv("DISABLE_UVLOOP", ""):  # pragma: no cover
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


@click.command()
@click.option(
    "-l",
    "--log-level",
    type=click.Choice(["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]),
    default=None,
    help="INFO is not set, can also be set by the LOG_LEVEL environment variable.",
)
@click.option(
    "-d",
    "--dev",
    default=False,
    is_flag=True,
    help="Development mode, automatically reload bot when source changes",
)
@click.option(
    "-g",
    "--debug",
    default=False,
    is_flag=True,
    help="Enable detailed asyncio debugging",
)
@click.option(
    "-m",
    "--mock-games",
    default=False,
    is_flag=True,
    help="Produce mock game urls instead of real ones",
)
@click.option(
    "-a",
    "--api",
    default=False,
    is_flag=True,
    help="Start the API web server instead of the bot",
)
@click.option(
    "-p",
    "--port",
    type=click.INT,
    required=False,
    help="Use the given port number to serve the API",
)
@click.version_option(version=__version__)
def main(
    log_level: str | None,
    dev: bool,
    debug: bool,
    mock_games: bool,
    api: bool,
    port: int | None = None,
) -> None:
    if dev:
        hupper.start_reloader("spellbot.main")

    # Ensure that configure_logging() is called as early as possible
    level = log_level if log_level is not None else (getenv("LOG_LEVEL") or "INFO")
    configure_logging(level)

    import logging

    # ddtrace logging is awful and spammy
    ddtrace_logger = logging.getLogger("ddtrace")
    ddtrace_logger.propagate = False
    ddtrace_logger.setLevel(logging.CRITICAL)

    # When metrics are enabled, let's ensure that datadog-agent is running first...
    if not no_metrics():  # pragma: no cover
        logger = logging.root
        conn: socket | None = None
        connected = False

        logger.info("metrics enabled, checking for connection to statsd server...")
        while not connected:
            try:
                conn = socket()
                conn.connect(("127.0.0.1", 8126))
                logger.info("statsd server connection established")
                connected = True
                logger.info("waiting for statsd server to finish initialization...")
                time.sleep(5)
            except Exception as e:
                logger.info("statsd connection error: %s, retrying...", str(e))
                time.sleep(1)
            finally:
                assert conn is not None
                conn.close()

    if api:
        from .web import launch_web_server

        loop = asyncio.new_event_loop()
        loop.set_debug(debug)
        launch_web_server(loop, port or settings.PORT)
        loop.run_forever()
    else:
        from .client import build_bot

        assert settings.BOT_TOKEN is not None
        bot = build_bot(mock_games=mock_games)
        bot.run(settings.BOT_TOKEN, log_handler=None)
