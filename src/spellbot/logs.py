# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from aiohttp.http_exceptions import HttpProcessingError
from gunicorn.glogging import Logger as GunicornLogger
from pythonjsonlogger.json import JsonFormatter

from spellbot.settings import settings

if TYPE_CHECKING:
    from gunicorn.config import Config

FORMAT = (
    "%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] "
    "[dd.service=%(dd.service)s "
    "dd.env=%(dd.env)s "
    "dd.version=%(dd.version)s "
    "dd.trace_id=%(dd.trace_id)s "
    "dd.span_id=%(dd.span_id)s] "
    "- %(message)s"
)
DATE_FMT = "%Y-%m-%d %H:%M:%S"


class DatadogJsonFormatter(JsonFormatter):
    def add_fields(  # pragma: no cover
        self,
        log_data: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_data, record, message_dict)
        if "status" not in log_data:
            log_data["status"] = record.levelname

        # ECS configuration puts the environment in an "environment" field, but
        # we want to use "env" for consistency with other logs and metrics.
        # Otherwise, we fallback to the value set for DD_ENV.
        env = settings.DD_ENV
        if environment := log_data.get("environment"):
            env = environment
        log_data["env"] = env


def configure_logging(level: int | str = "INFO") -> None:  # pragma: no cover
    if settings.DD_ENV == "dev":
        print("using basic logging for development mode")  # noqa: T201
        logging.basicConfig(level=level)
        return
    handler = logging.StreamHandler()
    formatter = DatadogJsonFormatter(fmt=FORMAT, datefmt=DATE_FMT)
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


def demote_bad_requests(record: logging.LogRecord) -> bool:
    """
    Log malformed HTTP from clients (scanners sending garbage) as a warning, not an error.

    aiohttp logs these with a traceback at error level, but they're the client's mistake,
    not ours, so they shouldn't page anyone.
    """
    exc = record.exc_info[1] if record.exc_info else None
    if isinstance(exc, HttpProcessingError) and record.levelno > logging.WARNING:
        record.levelno = logging.WARNING
        record.levelname = logging.getLevelName(logging.WARNING)
    return True


class JsonGunicornLogger(GunicornLogger):
    """
    A gunicorn logger whose error log is JSON, like the rest of SpellBot's logs.

    gunicorn's own format writes a traceback as many plain-text lines, which reach Datadog
    as separate logs at `info`. As JSON, each record is one log with its real `status` and
    its traceback in `exc_info`. Use with `gunicorn --logger-class`.
    """

    def setup(self, cfg: Config) -> None:
        super().setup(cfg)
        for handler in self.error_log.handlers:
            handler.setFormatter(DatadogJsonFormatter(fmt=FORMAT, datefmt=DATE_FMT))
            handler.addFilter(demote_bad_requests)
