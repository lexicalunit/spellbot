# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from spellbot.integrations.http_errors import USER_AGENT, Integration, request_with_retries
from spellbot.settings import settings

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)

RETRY_ATTEMPTS = 2
# Reports are forwarded while Convoke waits on our response, and Convoke gives up on that request
# after 10 seconds. Keep `RETRY_ATTEMPTS * TIMEOUT_S` under that so a slow Castlog never makes
# a report that we did store look like a failure to the reporter.
TIMEOUT_S = 4


async def fetch_castlog_report(
    client: httpx.AsyncClient,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Hit the Castlog webhook with a post-game report and return the response data.

    Example Castlog API response:
    {
      "match_id": "uuid",
      "castlog_url": "https://app.castlog.gg/match/<uuid>",
      "linked_players": ["ravepool", "Ghoulie"],
      "unlinked_players": ["jaythedragonking"]
    }
    """
    headers = {
        "user-agent": USER_AGENT,
        "X-SpellBot-Secret": settings.CASTLOG_SECRET or "",
    }
    response = await client.post(settings.CASTLOG_ENDPOINT, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


async def report_match(payload: dict[str, Any]) -> dict[str, Any] | None:
    """
    Forward a post-game report to Castlog for match tracking.

    Best-effort and non-blocking for the caller's own persistence: any failure is
    logged and swallowed so a Castlog outage never prevents a report from being
    stored locally. Sends the same JSON structure that is stored in the `games`
    table's `metadata` column, unmodified, since Castlog parses it as-is.
    """
    if not settings.CASTLOG_ENDPOINT or not settings.CASTLOG_SECRET:
        return None

    return await request_with_retries(
        Integration.CASTLOG,
        lambda client: fetch_castlog_report(client, payload),
        attempts=RETRY_ATTEMPTS,
        timeout_s=TIMEOUT_S,
    )
