from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp import web

from spellbot.database import db_session_manager
from spellbot.services.plays import PlaysService
from spellbot.web.tools import rate_limited

if TYPE_CHECKING:
    from aiohttp.web_response import Response as WebResponse

logger = logging.getLogger(__name__)


async def game_verify_endpoint(request: web.Request) -> WebResponse:
    try:
        async with db_session_manager():
            game_id = int(request.match_info["game"])
            payload = await request.json()
            user_xid = int(payload["user_xid"])
            guild_xid = int(payload["guild_xid"])
            pin = payload["pin"]
            plays = PlaysService()
            verified = await plays.verify_game_pin(
                game_id=game_id,
                user_xid=user_xid,
                guild_xid=guild_xid,
                pin=pin,
            )
            if not verified and await rate_limited(request, key=f"game_verify:{game_id}"):
                return web.json_response({"error": "Rate limited"}, status=429)
            return web.json_response({"result": {"verified": verified}})
    except ValueError as e:
        if await rate_limited(request):
            return web.json_response({"error": "Rate limited"}, status=429)
        return web.json_response({"error": str(e)}, status=400)
    except KeyError as e:
        if await rate_limited(request):
            return web.json_response({"error": "Rate limited"}, status=429)
        return web.json_response({"error": f"missing key: {e}"}, status=400)
    except Exception as e:
        if await rate_limited(request):
            return web.json_response({"error": "Rate limited"}, status=429)
        return web.json_response({"error": str(e)}, status=500)
