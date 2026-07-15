from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING, Any

import httpx

from spellbot import __version__, services
from spellbot.enums import GameBracket, GameFormat
from spellbot.metrics import add_span_error
from spellbot.settings import settings

if TYPE_CHECKING:
    from spellbot.data import GameData

logger = logging.getLogger(__name__)

SUPPORTED_LOCALES = ["de", "en", "es", "fr", "it", "ja", "pt"]
RETRY_ATTEMPTS = 3
TIMEOUT_S = 3


class ConvokeGameTypes(Enum):
    Commander = "commander"
    Standard = "standard"
    Modern = "modern"
    Planechase = "planechase-commander"
    Horde = "horde-commander"
    Other = "other"


def convoke_game_format(format: GameFormat) -> ConvokeGameTypes:
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
        ):
            return ConvokeGameTypes.Commander
        case GameFormat.MODERN:
            return ConvokeGameTypes.Modern
        case GameFormat.STANDARD:
            return ConvokeGameTypes.Standard
        case GameFormat.HORDE_MAGIC:
            return ConvokeGameTypes.Horde
        case GameFormat.PLANECHASE:
            return ConvokeGameTypes.Planechase
        case _:
            return ConvokeGameTypes.Other


async def fetch_convoke_link(
    client: httpx.AsyncClient,
    game_data: GameData,
    pins: list[str] | None,
) -> dict[str, Any]:
    name = f"SB{game_data.id}"
    sb_game_format = GameFormat(game_data.format)
    format = convoke_game_format(sb_game_format).value
    players = await services.games.player_convoke_data(game_data.id)
    game_language = "en"
    for supported_locale in SUPPORTED_LOCALES:
        if game_data.locale.startswith(supported_locale):
            game_language = supported_locale
            break
    payload = {
        "isPublic": False,
        "name": name,
        "spellbotGameId": str(game_data.id),
        "seatLimit": game_data.seats,
        "format": format,
        "discordGuild": str(game_data.guild_xid),
        "discordChannel": str(game_data.channel_xid),
        "discordPlayers": [{"id": str(p["xid"]), "name": p["name"]} for p in players],
        "language": game_language,
    }
    if pins:
        payload["spellbotGamePins"] = pins
    if game_data.bracket != GameBracket.NONE.value:
        payload["bracketLevel"] = f"B{game_data.bracket - 1}"
    if game_data.format == GameFormat.PRE_CONS.value:
        payload["bracketLevel"] = "PRECON"  # Convoke uses Bracket to indicate "pre-cons"
    headers = {
        "user-agent": f"spellbot/{__version__}",
        "x-api-key": settings.CONVOKE_API_KEY,
    }
    endpoint = f"{settings.CONVOKE_ROOT}/game/create-game"
    resp = await client.post(endpoint, json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def generate_link(
    game_data: GameData,
    pins: list[str] | None,
) -> tuple[str | None, str | None]:
    if not settings.CONVOKE_API_KEY:
        return None, None

    timeout = httpx.Timeout(TIMEOUT_S, connect=TIMEOUT_S, read=TIMEOUT_S, write=TIMEOUT_S)
    data: dict[str, Any] | None = None
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(RETRY_ATTEMPTS):
            try:
                data = await fetch_convoke_link(client, game_data, pins)
            except Exception as ex:
                is_final_attempt = attempt == RETRY_ATTEMPTS - 1
                if is_final_attempt:
                    add_span_error(ex)
                    logger.exception("Convoke API failure (final attempt)")
                    return None, None
                logger.warning(
                    "Convoke API issue (attempt %s)",
                    attempt + 1,
                    exc_info=True,
                )
                continue

            if not data:
                return None, None
            game_link = data["url"]
            game_pass = data.get("password")
            return game_link, game_pass

    return None, None
