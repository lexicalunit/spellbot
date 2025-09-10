from __future__ import annotations

import inspect
import logging
import os
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import MutableMapping


# Datadog integration processor
def add_datadog_trace_info(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Add Datadog trace information to log events."""
    try:
        # Get DD trace info from ddtrace
        from ddtrace.trace import tracer

        span = tracer.current_span()
        if span:
            event_dict["dd.trace_id"] = str(span.trace_id)
            event_dict["dd.span_id"] = str(span.span_id)
        else:
            event_dict["dd.trace_id"] = "0"
            event_dict["dd.span_id"] = "0"
    except (ImportError, AttributeError):
        event_dict["dd.trace_id"] = "0"
        event_dict["dd.span_id"] = "0"

    # Add service info from environment or defaults
    event_dict["dd.service"] = os.getenv("DD_SERVICE", "spellbot")
    event_dict["dd.env"] = os.getenv("DD_ENV", "production")
    event_dict["dd.version"] = os.getenv("DD_VERSION", "unknown")

    return event_dict


def add_caller_info(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Add caller information for better debugging."""
    # Get the frame info for the actual call site (skip structlog frames)
    frame = inspect.currentframe()
    # Go up the stack to find the actual caller (skip structlog internal frames)
    for _ in range(6):  # Typical depth to skip structlog internals
        if frame and frame.f_back:
            frame = frame.f_back
        else:
            break

    if frame:
        event_dict["filename"] = frame.f_code.co_filename.split("/")[-1]
        event_dict["lineno"] = frame.f_lineno
        event_dict["function"] = frame.f_code.co_name

    return event_dict


def is_development() -> bool:
    """Check if we're running in development mode."""
    # Check various indicators for development environment
    return any(
        [
            os.getenv("DD_ENV") == "development",
            os.getenv("ENVIRONMENT") == "development",
            os.getenv("NODE_ENV") == "development",
            os.getenv("FLASK_ENV") == "development",
            os.getenv("DEBUG") == "true",
            # Also check if we're running tests
            "pytest" in os.getenv("_", ""),
            "test" in os.getenv("PYTEST_CURRENT_TEST", ""),
        ]
    )


def configure_structlog() -> None:
    """Configure structlog with Datadog integration."""
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    # Configure processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        add_caller_info,
        add_datadog_trace_info,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Choose renderer based on environment
    if is_development():
        # Use colorful console logging for development
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # Use JSON logging for production
        renderer = structlog.processors.JSONRenderer()

    # Configure structlog
    structlog.configure(
        processors=[
            *shared_processors,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )


# Legacy format for compatibility (if needed)
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
    """Configure logging with structlog and Datadog integration."""
    # Set up standard library logging to work with structlog
    logging.basicConfig(
        format="%(message)s",
        stream=None,  # Use default (stdout)
        level=level,
    )

    # Choose renderer based on environment
    if is_development():
        # Use colorful console logging for development
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # Use JSON logging for production
        renderer = structlog.processors.JSONRenderer()

    # Configure structlog to handle standard library logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            add_caller_info,
            add_datadog_trace_info,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            renderer,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Get a structlog logger instance."""
    return structlog.get_logger(name)
