# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from spellbot.data import GameLinkDetails
from spellbot.enums import GameBracket
from spellbot.integrations.http_errors import USER_AGENT, request_with_retries
from spellbot.settings import settings

if TYPE_CHECKING:
    import httpx

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
        payload["bracket"] = GameBracket(game_data.bracket).level
    headers = {
        "user-agent": USER_AGENT,
        "Authorization": f"Bearer {settings.EDHLAB_API_KEY}",
    }
    resp = await client.post(settings.EDHLAB_CREATE, json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def generate_link(game_data: GameData) -> GameLinkDetails:
    if not settings.EDHLAB_API_KEY:
        return GameLinkDetails()
    data = await request_with_retries(
        "EDHLAB",
        lambda client: fetch_edhlab_link(client, game_data),
        attempts=RETRY_ATTEMPTS,
        timeout_s=TIMEOUT_S,
    )
    return GameLinkDetails(data["gameUrl"]) if data else GameLinkDetails()
