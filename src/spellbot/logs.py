from __future__ import annotations

import logging

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


# Note: be sure to call this before importing any application modules!
def configure_logging(level: int | str = "INFO") -> None:  # pragma: no cover
    handler = logging.StreamHandler()
    formatter = JsonFormatter(fmt=FORMAT, datefmt=DATE_FMT)
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
