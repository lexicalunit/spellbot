from __future__ import annotations

import logging
from os import getenv
from typing import Any

from pythonjsonlogger.json import JsonFormatter

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
DD_ENV = getenv("DD_ENV", "dev")  # not pulled from settings.py (to avoid any imports)


class DatadogJsonFormatter(JsonFormatter):
    def add_fields(  # pragma: no cover
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        if "status" not in log_record:
            log_record["status"] = record.levelname

        # ECS configuration puts the environment in an "environment" field, but
        # we want to use "env" for consistency with other logs and metrics.
        # Otherwise, we fallback to the value set for DD_ENV.
        env = DD_ENV
        if environment := log_record.get("environment"):
            env = environment
        log_record["env"] = env


# Note: be sure to call this before importing any application modules!
def configure_logging(level: int | str = "INFO") -> None:  # pragma: no cover
    if DD_ENV == "dev":
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
