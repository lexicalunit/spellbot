from __future__ import annotations

import logging
from collections import namedtuple
from enum import Enum, auto
from typing import Optional

import aiohttp_jinja2
from aiohttp import web
from aiohttp.web_response import Response as WebResponse

from ...database import db_session_manager
from ...services import PlaysService

logger = logging.getLogger(__name__)


class RecordKind(Enum):
    CHANNEL = auto()
    USER = auto()


Opts = namedtuple("Opts", ["guild_xid", "target_xid", "page", "tz_offset", "tz_name"])


async def parse_opts(request: web.Request, kind: RecordKind) -> Opts:
    """Parse out the request options from web request object."""
    guild_xid = int(request.match_info["guild"])

    if kind is RecordKind.CHANNEL:
        target_xid = int(request.match_info["channel"])
    else:
        target_xid = int(request.match_info["user"])

    page = max(int(request.query.get("page", 0)), 0)

    tz_offset_cookie = request.cookies.get("timezone_offset")
    tz_offset: Optional[int] = None
    if tz_offset_cookie:
        try:
            tz_offset = int(tz_offset_cookie)
        except ValueError:
            pass

    tz_name = request.cookies.get("timezone_name")

    return Opts(
        guild_xid=guild_xid,
        target_xid=target_xid,
        page=page,
        tz_offset=tz_offset,
        tz_name=tz_name,
    )


async def impl(request: web.Request, kind: RecordKind) -> WebResponse:
    try:
        opts = await parse_opts(request, kind)
    except ValueError:
        return WebResponse(status=404)

    plays = PlaysService()
    if kind is RecordKind.CHANNEL:
        records = await plays.channel_records(
            guild_xid=opts.guild_xid,
            channel_xid=opts.target_xid,
            page=opts.page,
        )
    else:
        records = await plays.user_records(
            guild_xid=opts.guild_xid,
            user_xid=opts.target_xid,
            page=opts.page,
        )

    if records is None:
        return WebResponse(status=404)

    path = f"{'channel' if kind is RecordKind.CHANNEL else 'user'}_record.html.j2"
    context = {
        "records": records,
        "tz_offset": opts.tz_offset,
        "tz_name": opts.tz_name,
        "prev_page": f"{request.path}?page={max(opts.page - 1, 0)}",
        "next_page": f"{request.path}?page={opts.page + 1}",
    }
    return aiohttp_jinja2.render_template(path, request, context)


async def channel_endpoint(request: web.Request) -> WebResponse:
    async with db_session_manager():
        return await impl(request, RecordKind.CHANNEL)


async def user_endpoint(request: web.Request) -> WebResponse:
    async with db_session_manager():
        return await impl(request, RecordKind.USER)
