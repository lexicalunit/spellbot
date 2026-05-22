from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ddtrace._trace.span import Span

logger = logging.getLogger(__name__)


def is_empty_resource(span: Span) -> bool:
    """Return `True` when a span's resource normalizes to nothing meaningful."""
    resource = getattr(span, "resource", None) or ""
    return not resource.strip().strip(";").strip()


def configure_tracing() -> None:
    """
    Install ddtrace span filters to suppress agent obfuscator noise.

    The trace agent logs `Error obfuscating stats group resource ";": result
    is empty` whenever it receives a span whose resource normalizes to an
    empty string after the obfuscator strips trailing semicolons. The spans
    themselves carry no useful information, so drop them before they reach
    the agent.

    Safe no-op when `ddtrace` is not installed.
    """
    try:
        from ddtrace.trace import TraceFilter, tracer  # allow_inline
    except ImportError:  # pragma: no cover
        return

    class DropEmptyResource(TraceFilter):
        def process_trace(self, trace: Iterable[Span]) -> list[Span] | None:
            kept = [span for span in trace if not is_empty_resource(span)]
            return kept or None

    tracer.configure(trace_processors=[DropEmptyResource()])
