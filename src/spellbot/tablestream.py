from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from aiohttp.client_exceptions import ClientError
from aiohttp_retry import ExponentialRetry, RetryClient

from spellbot import __version__
from spellbot.metrics import add_span_error
from spellbot.settings import settings

if TYPE_CHECKING:
    from spellbot.models import GameDict

logger = logging.getLogger(__name__)


async def generate_tablestream_link(game: GameDict) -> str | None:
    assert settings.TABLESTREAM_AUTH_KEY

    headers = {
        "user-agent": f"spellbot/{__version__}",
        "Authorization": f"Bearer: {settings.SPELLTABLE_AUTH_KEY}",
    }

    data: dict[str, Any] | None = None
    raw_data: bytes | None = None

    # Game Types:
    # "MTGCommander"
    # "MTGStandard"
    # "MTGModern"
    # "MTGVintage"
    # "MTGLegacy"

    request_data = {
        "roomName": "amy-testing",
        "gameType": "MTGCommander",
        "maxPlayers": 4,
        "private": True,
        # private?:boolean; optional: If true and no password passed in the system
        #                             will auto generate and return a password
        # password?:string; optional: password for the room, leave blank for auto
        #                             generated password if 'private' is true
        # initialScheduleTTLInSeconds?:number; optional: amount of time the room is joinable after
        #                                                which it is auto deleted. Default: 1 hour
    }

    try:
        async with (
            RetryClient(
                raise_for_status=False,
                retry_options=ExponentialRetry(attempts=5),
            ) as client,
            client.post(
                settings.TABLESTREAM_CREATE,
                headers=headers,
                json=request_data,
            ) as resp,
        ):
            # Rather than use `resp.json()`, which respects mimetype, let's just
            # grab the data and try to decode it ourselves.
            # https://github.com/inyutin/aiohttp_retry/issues/55
            raw_data = await resp.read()
            data = json.loads(raw_data)

            # data = {
            #     "room": {
            #         "roomName": "amy-testing",
            #         "roomId": "cc56f322-3338-4643-8cd3-251055aa515d",
            #         "roomUrl": "https://table-stream.com/game?id=cc56f322-3338-4643-8cd3-251055aa515d",
            #         "gameType": "MTGCommander",
            #         "maxPlayers": 4,
            #         "password": "J^vT!wL1kQ",
            #     }
            # }

            return None
    except ClientError as ex:
        add_span_error(ex)
        logger.warning(
            "warning: TableStream API failure: %s, data: %s, raw: %s",
            ex,
            data,
            raw_data,
            exc_info=True,
        )
        return None
    except Exception as ex:
        if raw_data == b"upstream request timeout":
            return None

        add_span_error(ex)
        logger.exception("error: unexpected exception: data: %s, raw: %s", data, raw_data)
        return None
