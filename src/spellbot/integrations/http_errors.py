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

import httpx

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
    except Exception:  # pragma: no cover  # httpx raises if the body was never read
        body = "<unavailable>"
    body = body.strip()
    if len(body) > MAX_BODY_CHARS:
        body = f"{body[:MAX_BODY_CHARS]}… (truncated)"
    return f"HTTP {ex.response.status_code} from {ex.request.url}: {body or '<empty body>'}"
