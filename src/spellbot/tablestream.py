from __future__ import annotations

import json
import logging
from enum import Enum
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

from aiohttp.client_exceptions import ClientError
from aiohttp_retry import ExponentialRetry, RetryClient

from spellbot import __version__
from spellbot.enums import GameFormat
from spellbot.metrics import add_span_error
from spellbot.settings import settings

if TYPE_CHECKING:
    from spellbot.models import GameDict

logger = logging.getLogger(__name__)


class TableSteamGameTypes(Enum):
    MTGCommander = "MTGCommander"
    MTGLegacy = "MTGLegacy"
    MTGModern = "MTGModern"
    MTGStandard = "MTGStandard"
    MTGVintage = "MTGVintage"


def table_stream_game_type(format: GameFormat) -> TableSteamGameTypes:
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


async def generate_tablestream_link(game: GameDict) -> tuple[str | None, str | None]:
    assert settings.TABLESTREAM_AUTH_KEY

    headers = {
        "user-agent": f"spellbot/{__version__}",
        "Authorization": f"Bearer: {settings.SPELLTABLE_AUTH_KEY}",
    }

    data: dict[str, Any] | None = None
    raw_data: bytes | None = None

    room_name = f"SB{game['id']}"
    sb_game_format = GameFormat(game["format"])
    ts_game_type = table_stream_game_type(sb_game_format).value
    ts_args = TableStreamArgs(
        roomName=room_name,
        gameType=ts_game_type,
        maxPlayers=sb_game_format.players,
        private=True,
        initialScheduleTTLInSeconds=1 * 60 * 60,  # 1 hour
    )

    try:
        async with (
            RetryClient(
                raise_for_status=False,
                retry_options=ExponentialRetry(attempts=5),
            ) as client,
            client.post(
                settings.TABLESTREAM_CREATE,
                headers=headers,
                json={**ts_args},
            ) as resp,
        ):
            # Rather than use `resp.json()`, which respects mimetype, let's just
            # grab the data and try to decode it ourselves.
            # https://github.com/inyutin/aiohttp_retry/issues/55
            raw_data = await resp.read()

            if not (data := json.loads(raw_data)):
                return None, None

            # Example response:
            # {
            #   "room": {
            #     "roomName": "SB12345",
            #     "roomId": "UUID",
            #     "roomUrl": "https://table-stream.com/game?id=UUID",
            #     "gameType": "MTGCommander",
            #     "maxPlayers": 4,
            #     "password": "OMIT",
            #   }
            # }
            room = data.get("room", {})
            return room.get("roomUrl"), room.get("password")
    except ClientError as ex:
        add_span_error(ex)
        logger.warning(
            "warning: TableStream API failure: %s, data: %s, raw: %s",
            ex,
            data,
            raw_data,
            exc_info=True,
        )
        return None, None
    except Exception as ex:
        if raw_data == b"upstream request timeout":
            return None, None

        add_span_error(ex)
        logger.exception("error: unexpected exception: data: %s, raw: %s", data, raw_data)
        return None, None
