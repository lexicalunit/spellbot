from __future__ import annotations

import logging
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


# Note: be sure to call this before importing any application modules!
def configure_logging(level: int | str = "INFO") -> None:  # pragma: no cover
    handler = logging.StreamHandler()
    formatter = DatadogJsonFormatter(fmt=FORMAT, datefmt=DATE_FMT)
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
