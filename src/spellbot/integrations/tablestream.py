from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

import httpx

from spellbot import __version__
from spellbot.enums import GameFormat
from spellbot.metrics import add_span_error
from spellbot.settings import settings

if TYPE_CHECKING:
    from spellbot.models import GameDict

logger = logging.getLogger(__name__)

RETRY_ATTEMPTS = 2
TIMEOUT_S = 3


class TableSteamGameTypes(Enum):
    MTGCommander = "MTGCommander"
    MTGLegacy = "MTGLegacy"
    MTGModern = "MTGModern"
    MTGStandard = "MTGStandard"
    MTGVintage = "MTGVintage"


def table_stream_game_type(format: GameFormat) -> TableSteamGameTypes:  # pragma: no cover
    match format:
        case (
            GameFormat.COMMANDER
            | GameFormat.OATHBREAKER
            | GameFormat.BRAWL_MULTIPLAYER
            | GameFormat.EDH_MAX
            | GameFormat.EDH_HIGH
            | GameFormat.EDH_MID
            | GameFormat.EDH_LOW
            | GameFormat.EDH_BATTLECRUISER
            | GameFormat.PLANECHASE
            | GameFormat.TWO_HEADED_GIANT
            | GameFormat.PRE_CONS
            | GameFormat.CEDH
            | GameFormat.PAUPER_EDH
            | GameFormat.ARCHENEMY
        ):
            return TableSteamGameTypes.MTGCommander
        case (
            GameFormat.LEGACY
            | GameFormat.PAUPER
            | GameFormat.DUEL_COMMANDER
            | GameFormat.BRAWL_TWO_PLAYER
        ):
            return TableSteamGameTypes.MTGLegacy
        case GameFormat.MODERN | GameFormat.PIONEER:
            return TableSteamGameTypes.MTGModern
        case GameFormat.STANDARD | GameFormat.SEALED:
            return TableSteamGameTypes.MTGStandard
        case GameFormat.VINTAGE:
            return TableSteamGameTypes.MTGVintage


class TableStreamArgs(TypedDict):
    roomName: str
    gameType: str
    maxPlayers: int

    # If true and no password passed in the system
    # will auto generate and return a password
    private: NotRequired[bool]

    # password for the room, leave blank for auto
    # generated password if 'private' is true
    password: NotRequired[bool]

    # amount of time the room is joinable after
    # which it is auto deleted. Default: 1 hour
    initialScheduleTTLInSeconds: NotRequired[int]


def build_ts_args(game: GameDict) -> TableStreamArgs:  # pragma: no cover
    room_name = f"SB{game['id']}"
    sb_game_format = GameFormat(game["format"])
    ts_game_type = table_stream_game_type(sb_game_format).value
    return TableStreamArgs(
        roomName=room_name,
        gameType=ts_game_type,
        maxPlayers=sb_game_format.players,
        private=True,
        initialScheduleTTLInSeconds=60 * 60,  # 1 hour
    )


async def fetch_table_stream_link(  # pragma: no cover
    client: httpx.AsyncClient,
    ts_args: TableStreamArgs,
) -> dict[str, Any] | None:
    """
    Hits the TableStream API to create a new room and returns the response data.

    Example TableStream API response:
    {
      "room": {
        "roomName": "SB12345",
        "roomId": "UUID",
        "roomUrl": "https://table-stream.com/game?id=UUID",
        "gameType": "MTGCommander",
        "maxPlayers": 4,
        "password": "OMIT",
      }
    }
    """
    headers = {
        "user-agent": f"spellbot/{__version__}",
        "Authorization": f"Bearer: {settings.TABLESTREAM_AUTH_KEY}",
    }
    response = await client.post(
        settings.TABLESTREAM_CREATE,
        headers=headers,
        json=ts_args,
    )
    response.raise_for_status()
    return response.json()


async def generate_link(game: GameDict) -> tuple[str | None, str | None]:  # pragma: no cover
    if not settings.TABLESTREAM_AUTH_KEY:
        return None, None

    ts_args = build_ts_args(game)
    timeout = httpx.Timeout(TIMEOUT_S, connect=TIMEOUT_S, read=TIMEOUT_S, write=TIMEOUT_S)

    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(RETRY_ATTEMPTS):
            try:
                data = await fetch_table_stream_link(client, ts_args)
            except Exception as ex:
                add_span_error(ex)
                if attempt == RETRY_ATTEMPTS - 1:
                    logger.exception("TableStream API failure (final attempt)")
                    return None, None
                logger.warning(
                    "TableStream API issue (attempt %s)",
                    attempt + 1,
                    exc_info=True,
                )

            if not data:
                return None, None
            room = data.get("room", {})
            return room.get("roomUrl"), room.get("password")

    return None, None
