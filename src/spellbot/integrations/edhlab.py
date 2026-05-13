from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx

from spellbot import __version__
from spellbot.enums import GameBracket
from spellbot.metrics import add_span_error
from spellbot.settings import settings

if TYPE_CHECKING:
    from spellbot.data import GameData

logger = logging.getLogger(__name__)

RETRY_ATTEMPTS = 2
TIMEOUT_S = 3


async def fetch_edhlab_link(
    client: httpx.AsyncClient,
    game_data: GameData,
) -> dict[str, Any]:
    payload = {}
    if game_data.bracket != GameBracket.NONE.value:
        payload["bracket"] = game_data.bracket - 1
    headers = {
        "user-agent": f"spellbot/{__version__}",
        "Authorization": f"Bearer {settings.EDHLAB_API_KEY}",
    }
    resp = await client.post(settings.EDHLAB_CREATE, json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def generate_link(game_data: GameData) -> tuple[str | None, str | None]:
    if not settings.EDHLAB_API_KEY:
        return None, None

    timeout = httpx.Timeout(TIMEOUT_S, connect=TIMEOUT_S, read=TIMEOUT_S, write=TIMEOUT_S)
    data: dict[str, Any] | None = None
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(RETRY_ATTEMPTS):
            try:
                data = await fetch_edhlab_link(client, game_data)
            except Exception as ex:
                is_final_attempt = attempt == RETRY_ATTEMPTS - 1
                if is_final_attempt:
                    add_span_error(ex)
                    logger.exception("EDHLAB API failure (final attempt)")
                    return None, None
                logger.warning(
                    "EDHLAB API issue (attempt %s)",
                    attempt + 1,
                    exc_info=True,
                )
                continue

            if not data:
                return None, None
            return data["gameUrl"], None

    return None, None
