# Copyright (c) 2026 spellbot@lexicalunit.com

"""
Shared helpers for talking to the third party game link APIs.

Every integration wraps its HTTP calls in a retry loop. Two rules belong to all of them
rather than to any one integration, so they live here:

- A 4xx means the request itself was wrong, so replaying it unchanged only burns attempts
  and latency. Only `408` and `429` are worth another try, since those describe a moment
  rather than the request.
- `httpx.Response.raise_for_status()` reports the status and nothing else, so the body that
  says *which* field the API rejected is lost exactly when it is needed. `describe_http_error`
  puts it back into the log line.
"""

from __future__ import annotations

import asyncio
import logging
from enum import StrEnum
from typing import TYPE_CHECKING

import httpx

from spellbot import __version__
from spellbot.metrics import add_span_error

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class Integration(StrEnum):
    """
    An outside service SpellBot depends on, named as it appears in logs and monitors.

    Each one has its own outage monitor in `infrastructure/o11y/main.tf`, which finds its
    failures by the `integration` attribute that `about()` adds to their logs.
    """

    CASTLOG = "Castlog"
    CONVOKE = "Convoke"
    EDHLAB = "EDHLab"
    GIRUDO = "Girudo"
    PATREON = "Patreon"
    PLAYGROUP_LIVE = "Playgroup Live"

    def about(self) -> dict[str, str]:
        """Return the `extra` that marks a log as being about this integration."""
        return {"integration": self.value}


# Sent with every request so the services can tell SpellBot traffic and versions apart.
USER_AGENT = f"spellbot/{__version__}"

# 4xx codes that describe a transient moment rather than a malformed request, so a replay of
# the very same request can still succeed.
RETRYABLE_CLIENT_STATUSES = frozenset({408, 429})

# Enough of the body to name the offending field without flooding the logs.
MAX_BODY_CHARS = 2000


def is_terminal_client_error(ex: BaseException) -> bool:
    """Whether `ex` is a 4xx that will fail again if the same request is replayed."""
    if not isinstance(ex, httpx.HTTPStatusError):
        return False
    status = ex.response.status_code
    return 400 <= status < 500 and status not in RETRYABLE_CLIENT_STATUSES


def describe_http_error(ex: BaseException) -> str:
    """
    Describe `ex` for a log line, including the response body when there is one.

    Returns an empty string for non-HTTP errors so callers can append it unconditionally.
    """
    if not isinstance(ex, httpx.HTTPStatusError):
        return ""
    try:
        body = ex.response.text
    except Exception:  # httpx raises if the body was never read
        body = "<unavailable>"
    body = body.strip()
    if len(body) > MAX_BODY_CHARS:
        body = f"{body[:MAX_BODY_CHARS]}… (truncated)"
    return f"HTTP {ex.response.status_code} from {ex.request.url}: {body or '<empty body>'}"


async def request_with_retries[T](
    integration: Integration,
    request: Callable[[httpx.AsyncClient], Awaitable[T]],
    *,
    attempts: int,
    timeout_s: float,
    backoff_s: float = 0.0,
) -> T | None:
    """
    Run a request against `integration`, retrying failures. Returns `None` if it never succeeds.

    A terminal client error ends the retries early. When `backoff_s` is set, the wait between
    attempts doubles each time, starting from `backoff_s`.
    """
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_s)) as client:
        for attempt in range(attempts):
            try:
                return await request(client)
            except Exception as ex:
                details = describe_http_error(ex)
                if attempt == attempts - 1 or is_terminal_client_error(ex):
                    add_span_error(ex)
                    logger.exception(
                        "%s API failure. %s",
                        integration,
                        details,
                        extra=integration.about(),
                    )
                    return None
                logger.warning(
                    "%s API issue (attempt %s). %s",
                    integration,
                    attempt + 1,
                    details,
                    exc_info=True,
                    extra=integration.about(),
                )
                if backoff_s:
                    await asyncio.sleep(backoff_s * (2**attempt))
    return None  # only reached when `attempts` is zero
