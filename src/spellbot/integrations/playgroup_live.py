from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import httpx

from spellbot import __version__
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.metrics import add_span_error
from spellbot.settings import settings

if TYPE_CHECKING:
    from spellbot.data import GameData

logger = logging.getLogger(__name__)

RETRY_ATTEMPTS = 2
RETRY_BACKOFF_S = 0.2
TIMEOUT_S = 3
MAX_PLAYERS = GameService.PLAYGROUP_LIVE.max_seats


def _api_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.PLAYGROUP_LIVE_API_KEY}",
        "User-Agent": f"spellbot/{__version__}",
    }


def playgroup_life_amount(format: GameFormat) -> int:
    match format:
        case (
            GameFormat.COMMANDER
            | GameFormat.EDH_MAX
            | GameFormat.EDH_HIGH
            | GameFormat.EDH_MID
            | GameFormat.EDH_LOW
            | GameFormat.EDH_BATTLECRUISER
            | GameFormat.PRE_CONS
            | GameFormat.CEDH
            | GameFormat.PAUPER_EDH
            | GameFormat.PLANECHASE
            | GameFormat.ARCHENEMY
            | GameFormat.HORDE_MAGIC
        ):
            return 40
        case GameFormat.TWO_HEADED_GIANT:
            return 30
        case GameFormat.BRAWL_TWO_PLAYER | GameFormat.BRAWL_MULTIPLAYER:
            return 25
        case _:
            return 20


def playgroup_bracket(bracket: int) -> int | None:
    if bracket == GameBracket.NONE.value:
        return None
    mapped = bracket - GameBracket.NONE.value
    return mapped if 1 <= mapped <= 5 else None


def find_linked_player(game_data: GameData) -> int | None:
    for player in game_data.players:
        if player.playgroup_user_id is not None:
            return player.playgroup_user_id
    return None


async def lookup_playgroup_user(
    client: httpx.AsyncClient,
    discord_id: int,
) -> tuple[int | None, str | None]:
    endpoint = f"{settings.PLAYGROUP_LIVE_API_URL}/api/v2/users/by_discord/{discord_id}"
    try:
        resp = await client.get(endpoint, headers=_api_headers())
        if resp.status_code == 404:
            logger.info("Playgroup user not found for Discord ID %s", discord_id)
            return None, None
        resp.raise_for_status()
        data = resp.json()
        user_id = data["id"]
        username = data["username"]
    except httpx.HTTPStatusError:
        logger.warning("Playgroup user lookup API error for Discord %s", discord_id, exc_info=True)
        return None, None
    except Exception:
        logger.warning("Playgroup user lookup failed for Discord %s", discord_id, exc_info=True)
        return None, None
    else:
        logger.info(
            "Playgroup user lookup: Discord %s -> Playgroup user %s",
            discord_id,
            user_id,
        )
        return user_id, username


async def fetch_playgroup_live_session(
    client: httpx.AsyncClient,
    game_data: GameData,
    playgroup_user_id: int,
    player_amount: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "player_amount": min(player_amount, MAX_PLAYERS),
        "life_amount": playgroup_life_amount(GameFormat(game_data.format)),
        "client_identifier": "spellbot",
        "on_behalf_of_user_id": playgroup_user_id,
    }
    bracket_value = playgroup_bracket(game_data.bracket)
    if bracket_value is not None:
        payload["bracket"] = bracket_value

    endpoint = f"{settings.PLAYGROUP_LIVE_API_URL}/api/public/v1/live_sessions"
    resp = await client.post(endpoint, json=payload, headers=_api_headers())
    resp.raise_for_status()
    return resp.json()


async def generate_link(
    game_data: GameData,
    original_seats: int | None = None,
) -> tuple[str | None, str | None]:
    if not settings.PLAYGROUP_LIVE_API_KEY:
        logger.warning("Playgroup Live API key not configured")
        return None, None

    playgroup_user_id = find_linked_player(game_data)
    if playgroup_user_id is None:
        return None, None

    player_amount = original_seats or game_data.seats

    timeout = httpx.Timeout(TIMEOUT_S, connect=TIMEOUT_S, read=TIMEOUT_S, write=TIMEOUT_S)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(RETRY_ATTEMPTS):
            try:
                data = await fetch_playgroup_live_session(
                    client,
                    game_data,
                    playgroup_user_id,
                    player_amount,
                )
            except Exception as ex:
                add_span_error(ex)
                if attempt == RETRY_ATTEMPTS - 1:
                    logger.exception("Playgroup Live API failure (final attempt)")
                    return None, None
                logger.warning(
                    "Playgroup Live API issue (attempt %s)",
                    attempt + 1,
                    exc_info=True,
                )
                await asyncio.sleep(RETRY_BACKOFF_S * (2**attempt))
                continue

            if not data:
                return None, None
            game_link = data["url"]
            logger.info("Playgroup Live session created for game %s: %s", game_data.id, game_link)
            return game_link, None

    return None, None
