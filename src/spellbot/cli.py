from __future__ import annotations

import asyncio
import time
from socket import socket

import click
import hupper
import uvloop

from . import __version__
from .logs import configure_logging
from .metrics import no_metrics
from .settings import settings


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
    "-t",
    "--disable-tasks",
    default=False,
    is_flag=True,
    help="Don't run background tasks",
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
    disable_tasks: bool,
    api: bool,
    port: int | None = None,
) -> None:
    if dev:
        hupper.start_reloader("spellbot.main")

    # Ensure that configure_logging() is called as early as possible
    level = log_level if log_level is not None else settings.LOG_LEVEL
    configure_logging(level)

    import logging  # allow_inline

    # ddtrace logging is awful and spammy
    ddtrace_logger = logging.getLogger("ddtrace")
    ddtrace_logger.propagate = False
    ddtrace_logger.setLevel(logging.CRITICAL)

    # When metrics are enabled, let's ensure that datadog-agent is running first...
    if not no_metrics():  # pragma: no cover
        logger = logging.root
        connected = False

        logger.info("metrics enabled, checking for connection to statsd server...")
        while not connected:
            conn = socket()
            try:
                conn.connect(("127.0.0.1", 8126))
            except Exception as e:
                logger.info("statsd connection error: %s, retrying...", str(e))
                time.sleep(1)
            else:
                logger.info("statsd server connection established")
                connected = True
                logger.info("waiting for statsd server to finish initialization...")
                time.sleep(5)
            finally:
                conn.close()

    if api:
        from .web import launch_dev_server  # allow_inline

        launch_dev_server(debug, port or settings.PORT)
    else:
        from .client import build_bot  # allow_inline

        bot_token = settings.BOT_TOKEN
        if bot_token is None:
            raise SystemExit(1)

        bot = build_bot(mock_games=mock_games, disable_tasks=disable_tasks)

        async def run_bot() -> None:  # pragma: no cover
            async with bot:
                await bot.start(bot_token)

        if settings.DISABLE_UVLOOP:  # pragma: no cover
            asyncio.run(run_bot())
        else:
            uvloop.run(run_bot())
