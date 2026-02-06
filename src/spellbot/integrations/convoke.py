from __future__ import annotations

import logging
import random
from enum import Enum
from typing import TYPE_CHECKING, Any

import httpx

from spellbot import __version__
from spellbot.enums import GameBracket, GameFormat
from spellbot.metrics import add_span_error
from spellbot.services import ServicesRegistry
from spellbot.settings import settings

if TYPE_CHECKING:
    from spellbot.models import GameDict

logger = logging.getLogger(__name__)
services = ServicesRegistry()

USE_PASSWORD = False  # no password is now supported!
RETRY_ATTEMPTS = 2
TIMEOUT_S = 3
ADJECTIVES = [
    "ancient",
    "angry",
    "arcane",
    "blazing",
    "cursed",
    "dark",
    "eternal",
    "fierce",
    "giant",
    "grim",
    "hidden",
    "lucky",
    "mighty",
    "mystic",
    "ominous",
    "sacred",
    "shiny",
    "swift",
    "twisted",
    "wild",
]
NOUNS = [
    "angel",
    "beast",
    "bolt",
    "counter",
    "dragon",
    "elf",
    "fetch",
    "goblin",
    "land",
    "mana",
    "merfolk",
    "sliver",
    "sorcery",
    "stack",
    "storm",
    "token",
    "wizard",
    "zombie",
]


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


def passphrase() -> str | None:
    if USE_PASSWORD:
        return f"{random.choice(ADJECTIVES)} {random.choice(NOUNS)}"  # noqa: S311
    return None


async def fetch_convoke_link(
    client: httpx.AsyncClient,
    game: GameDict,
    key: str | None,
) -> dict[str, Any]:
    name = f"SB{game['id']}"
    sb_game_format = GameFormat(game["format"])
    format = convoke_game_format(sb_game_format).value
    players = await services.games.player_data(game["id"])
    payload = {
        "apiKey": settings.CONVOKE_API_KEY,
        "isPublic": False,
        "name": name,
        "spellbotGameId": game["id"],
        "seatLimit": game["seats"],
        "format": format,
        "discordGuild": str(game["guild_xid"]),
        "discordChannel": str(game["channel_xid"]),
        "discordPlayers": [
            {"id": str(p["xid"]), "name": p["name"], "pin": p["pin"]} for p in players
        ],
    }
    if game["bracket"] != GameBracket.NONE.value:
        payload["bracketLevel"] = f"B{game['bracket'] - 1}"
    if key:
        payload["password"] = key
    headers = {"user-agent": f"spellbot/{__version__}"}
    endpoint = f"{settings.CONVOKE_ROOT}/game/create-game"
    resp = await client.post(endpoint, json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def generate_link(game: GameDict) -> tuple[str | None, str | None]:
    if not settings.CONVOKE_API_KEY:
        return None, None

    key = passphrase()
    timeout = httpx.Timeout(TIMEOUT_S, connect=TIMEOUT_S, read=TIMEOUT_S, write=TIMEOUT_S)
    data: dict[str, Any] | None = None
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(RETRY_ATTEMPTS):
            try:
                data = await fetch_convoke_link(client, game, key)
            except Exception as ex:
                add_span_error(ex)
                if attempt == RETRY_ATTEMPTS - 1:
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
            game_pass = data.get("password") or key
            return game_link, game_pass

    return None, None
