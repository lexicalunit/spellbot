# pylint: disable=too-many-arguments
from __future__ import annotations

import asyncio
import threading
import time
from os import _exit, getenv
from socket import socket
from typing import Optional

import click
import hupper
import uvloop
from dotenv import load_dotenv

from . import __version__
from .environment import running_in_pytest
from .logs import configure_logging
from .metrics import no_metrics

# load .env environment variables as early as possible
if not running_in_pytest():  # pragma: no cover
    load_dotenv()

uvloop.install()


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
    log_level: Optional[str],
    dev: bool,
    debug: bool,
    mock_games: bool,
    api: bool,
    port: Optional[int] = None,
) -> None:
    if dev:
        hupper.start_reloader("spellbot.main")

    from .settings import Settings

    # Ensure that configure_logging() is called as early as possible
    settings = Settings()
    level = log_level if log_level is not None else (getenv("LOG_LEVEL") or "INFO")
    configure_logging(level)

    import logging

    # ddtrace logging is awful and spammy
    ddtrace_logger = logging.getLogger("ddtrace")
    ddtrace_logger.propagate = False
    ddtrace_logger.setLevel(logging.CRITICAL)

    # When metrics are enabled, let's ensure that datadog-agent is running first...
    if not no_metrics():  # pragma: no cover
        import logging

        logger = logging.root
        conn: Optional[socket] = None
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
                logger.info(f"statsd connection error: {e}, retrying...")
                time.sleep(1)
            finally:
                assert conn is not None
                conn.close()

    loop = asyncio.new_event_loop()
    if debug:
        loop.set_debug(True)
    if api:
        from .web import launch_web_server

        launch_web_server(settings, loop, port or settings.PORT)
        loop.run_forever()
    else:
        from . import SpellBot
        from .client import build_bot

        assert settings.BOT_TOKEN is not None
        bot = build_bot(loop=loop, mock_games=mock_games)

        if not debug and not running_in_pytest:
            # Sometimes the bot gets into a weird state where it doesn't properly
            # start up entirely; this causes tasks (see tasks_cog.py) to never begin
            # since those only start after the ready signal has been processed.
            # As such, let's check every 30 minutes if the bot is ready, because if
            # it isn't we can just kill it and have supervisord restart it for us.
            def killer(bot: SpellBot):
                while True:
                    time.sleep(30 * 60)  # 30 minute wait
                    if not bot.is_ready():
                        print("exiting due to readiness check failure")  # noqa: T201
                        _exit(1)
                    else:
                        print("readiness check passed")  # noqa: T201

            x = threading.Thread(target=killer, args=(bot,))
            x.start()

        bot.run(settings.BOT_TOKEN)
