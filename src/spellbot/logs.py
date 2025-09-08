from __future__ import annotations

import logging

from pythonjsonlogger.json import JsonFormatter


# Note: be sure to call this before importing any application modules!
def configure_logging(level: int | str = "INFO") -> None:  # pragma: no cover
    handler = logging.StreamHandler()

    formatter = JsonFormatter(
        fmt=("%(asctime)s %(name)s %(levelname)s %(message)s %(filename)s %(lineno)d %(funcName)s"),
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
