# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging
from typing import Any

import httpx

from spellbot import __version__
from spellbot.metrics import add_span_error
from spellbot.settings import settings

logger = logging.getLogger(__name__)

RETRY_ATTEMPTS = 2
TIMEOUT_S = 3


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
        "user-agent": f"spellbot/{__version__}",
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

    timeout = httpx.Timeout(TIMEOUT_S, connect=TIMEOUT_S, read=TIMEOUT_S, write=TIMEOUT_S)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(RETRY_ATTEMPTS):
            try:
                return await fetch_castlog_report(client, payload)
            except Exception as ex:
                is_final_attempt = attempt == RETRY_ATTEMPTS - 1
                if is_final_attempt:
                    add_span_error(ex)
                    logger.exception("Castlog API failure (final attempt)")
                    return None
                logger.warning(
                    "Castlog API issue (attempt %s)",
                    attempt + 1,
                    exc_info=True,
                )
                continue

    return None
