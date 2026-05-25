from __future__ import annotations

import csv
import io
import logging
from contextlib import suppress
from datetime import UTC, datetime
from enum import Enum, auto
from typing import Any, NamedTuple

import aiohttp_jinja2
from aiohttp import web
from ddtrace.trace import tracer

from spellbot import services
from spellbot.database import db_session_manager
from spellbot.metrics import add_span_request_id, generate_request_id

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

USER_EXPORT_HEADER = [
    "Game",
    "Time",
    "Guild",
    "Channel",
    "Format",
    "Seats",
    "Bracket",
    "Locale",
    "Link",
    "Players",
]

CHANNEL_EXPORT_HEADER = [
    "Game",
    "Time",
    "Guild",
    "Channel",
    "Format",
    "Seats",
    "Bracket",
    "Locale",
    "Link",
    "User Name",
    "User ID",
]


class RecordKind(Enum):
    CHANNEL = auto()
    USER = auto()


class Opts(NamedTuple):
    guild_xid: int
    target_xid: int
    page: int
    tz_offset: int | None
    tz_name: str | None


async def parse_opts(request: web.Request, kind: RecordKind) -> Opts:
    """Parse out the request options from web request object."""
    guild_xid = int(request.match_info["guild"])

    if kind is RecordKind.CHANNEL:
        target_xid = int(request.match_info["channel"])
    else:
        target_xid = int(request.match_info["user"])

    page = max(int(request.query.get("page", 0)), 0)

    tz_offset_cookie = request.cookies.get("timezone_offset")
    tz_offset: int | None = None
    if tz_offset_cookie:
        with suppress(ValueError):
            tz_offset = int(tz_offset_cookie)

    tz_name = request.cookies.get("timezone_name")

    return Opts(
        guild_xid=guild_xid,
        target_xid=target_xid,
        page=page,
        tz_offset=tz_offset,
        tz_name=tz_name,
    )


async def impl(request: web.Request, kind: RecordKind) -> web.Response:
    try:
        opts = await parse_opts(request, kind)
    except ValueError:
        return web.Response(status=404)

    if kind is RecordKind.CHANNEL:
        records = await services.plays.channel_records(
            guild_xid=opts.guild_xid,
            channel_xid=opts.target_xid,
            page=opts.page,
        )
    else:
        records = await services.plays.user_records(
            guild_xid=opts.guild_xid,
            user_xid=opts.target_xid,
            page=opts.page,
        )

    if records is None:
        return web.Response(status=404)

    path = f"{'channel' if kind is RecordKind.CHANNEL else 'user'}_record.html.j2"
    context = {
        "records": records,
        "tz_offset": opts.tz_offset,
        "tz_name": opts.tz_name,
        "prev_page": f"{request.path}?page={max(opts.page - 1, 0)}",
        "next_page": f"{request.path}?page={opts.page + 1}",
        "export_url": f"{request.path}/export.csv",
    }
    return aiohttp_jinja2.render_template(path, request, context)


@routes.get(r"/g/{guild}/c/{channel}")
@tracer.wrap(name="web", resource="channel_record")
async def channel_endpoint(request: web.Request) -> web.Response:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await impl(request, RecordKind.CHANNEL)


@routes.get(r"/g/{guild}/u/{user}")
@tracer.wrap(name="web", resource="user_record")
async def user_endpoint(request: web.Request) -> web.Response:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await impl(request, RecordKind.USER)


async def game_impl(request: web.Request) -> web.Response:
    try:
        game_id = int(request.match_info["game_id"])
    except ValueError:
        return web.Response(status=404)
    game = await services.games.game_detail_view(game_id)
    if game is None:
        return web.Response(status=404)

    tz_offset_cookie = request.cookies.get("timezone_offset")
    tz_offset: int | None = None
    if tz_offset_cookie:
        with suppress(ValueError):
            tz_offset = int(tz_offset_cookie)
    tz_name = request.cookies.get("timezone_name")

    context = {
        "game": game,
        "tz_offset": tz_offset,
        "tz_name": tz_name,
    }
    return aiohttp_jinja2.render_template("game.html.j2", request, context)


@routes.get(r"/game/{game_id}")
@tracer.wrap(name="web", resource="game_detail")
async def game_endpoint(request: web.Request) -> web.Response:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await game_impl(request)


def csv_line(values: list[Any]) -> bytes:
    """Serialize a single CSV row to UTF-8 bytes."""
    buf = io.StringIO()
    csv.writer(buf).writerow(values)
    return buf.getvalue().encode("utf-8")


def iso_utc(updated_at_ms: float) -> str:
    """Format a millis-since-epoch float as an ISO-8601 UTC timestamp."""
    return datetime.fromtimestamp(updated_at_ms / 1000, tz=UTC).isoformat()


def format_user_export_row(record: dict[str, Any]) -> list[Any]:
    """Build the per-game CSV row for a user export."""
    players = "; ".join(f"{name} ({data[0]})" for name, data in record["scores"].items())
    return [
        record["id"],
        iso_utc(record["updated_at"]),
        record["guild_name"],
        record["channel_name"],
        record["format"],
        record["seats"],
        record["bracket"],
        record["locale"],
        record["link"] or "",
        players,
    ]


def format_channel_export_row(record: dict[str, Any]) -> list[Any]:
    """Build the per-player CSV row for a channel export."""
    return [
        record["id"],
        iso_utc(record["updated_at"]),
        record["guild_name"],
        record["channel_name"],
        record["format"],
        record["seats"],
        record["bracket"],
        record["locale"],
        record["link"] or "",
        record["user_name"] or "",
        record["user_xid"],
    ]


async def export_impl(request: web.Request, kind: RecordKind) -> web.StreamResponse:
    try:
        guild_xid = int(request.match_info["guild"])
        if kind is RecordKind.CHANNEL:
            target_xid = int(request.match_info["channel"])
        else:
            target_xid = int(request.match_info["user"])
    except ValueError:
        return web.Response(status=404)

    if kind is RecordKind.CHANNEL:
        if not await services.plays.channel_export_target_exists(guild_xid, target_xid):
            return web.Response(status=404)
        header = CHANNEL_EXPORT_HEADER
        stream = services.plays.stream_channel_records(guild_xid, target_xid)
        format_row = format_channel_export_row
        filename_part = f"channel-{target_xid}"
    else:
        if not await services.plays.user_export_target_exists(guild_xid):
            return web.Response(status=404)
        header = USER_EXPORT_HEADER
        stream = services.plays.stream_user_records(guild_xid, target_xid)
        format_row = format_user_export_row
        filename_part = f"user-{target_xid}"

    today = datetime.now(tz=UTC).strftime("%Y%m%d")
    filename = f"spellbot-{filename_part}-{today}.csv"
    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
    response.enable_compression(force=web.ContentCoding.gzip)
    response.enable_chunked_encoding()
    await response.prepare(request)

    await response.write(csv_line(header))
    async for record in stream:
        await response.write(csv_line(format_row(record)))

    await response.write_eof()
    return response


@routes.get(r"/g/{guild}/c/{channel}/export.csv")
@tracer.wrap(name="web", resource="channel_record_export")
async def channel_export_endpoint(request: web.Request) -> web.StreamResponse:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await export_impl(request, RecordKind.CHANNEL)


@routes.get(r"/g/{guild}/u/{user}/export.csv")
@tracer.wrap(name="web", resource="user_record_export")
async def user_export_endpoint(request: web.Request) -> web.StreamResponse:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await export_impl(request, RecordKind.USER)
