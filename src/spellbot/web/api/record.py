import logging
from enum import Enum, auto

import aiohttp_jinja2
from aiohttp import web
from aiohttp.web_response import Response as WebResponse

from ...database import db_session_manager
from ...services import PlaysService

logger = logging.getLogger(__name__)


class RecordKind(Enum):
    CHANNEL = auto()
    USER = auto()


async def impl(request: web.Request, kind: RecordKind) -> WebResponse:
    try:
        guild_xid = int(request.match_info["guild"])
        if kind is RecordKind.CHANNEL:
            target_id = int(request.match_info["channel"])
        else:
            target_id = int(request.match_info["user"])
        page = max(int(request.query.get("page", 0)), 0)
    except ValueError:
        return WebResponse(status=404)

    plays = PlaysService()
    if kind is RecordKind.CHANNEL:
        records = await plays.channel_records(guild_xid, target_id, page=page)
    else:
        records = await plays.user_records(guild_xid, target_id, page=page)

    context = {"records": records}
    response = aiohttp_jinja2.render_template(
        f"{'channel' if kind is RecordKind.CHANNEL else 'user'}_record.html.j2",
        request,
        context,
    )
    return response


async def channel_endpoint(request: web.Request) -> WebResponse:
    async with db_session_manager():
        return await impl(request, RecordKind.CHANNEL)


async def user_endpoint(request: web.Request) -> WebResponse:
    async with db_session_manager():
        return await impl(request, RecordKind.USER)
