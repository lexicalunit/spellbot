from __future__ import annotations

import csv
import io
import logging
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta
from enum import Enum, auto
from typing import Any, NamedTuple
from urllib.parse import urlencode

import aiohttp_jinja2
from aiohttp import web
from ddtrace.trace import tracer

from spellbot import services
from spellbot.database import db_session_manager
from spellbot.enums import GAME_BRACKET_ORDER, GAME_FORMAT_ORDER
from spellbot.metrics import add_span_request_id, generate_request_id
from spellbot.services.plays import (
    CHANNEL_PAGE_SIZE,
    CHANNEL_RECORDS_SORT_COLUMNS,
    USER_PAGE_SIZE,
    USER_RECORDS_SORT_COLUMNS,
    RecordFilters,
)

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

VALID_SORT_DIRS = frozenset({"asc", "desc"})
DEFAULT_SORT_BY = "updated_at"
DEFAULT_SORT_DIR = "desc"

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
    guild_xid: int | None
    target_xid: int
    page: int
    tz_offset: int | None
    tz_name: str | None
    filters: RecordFilters
    raw_filters: dict[str, Any]


def parse_int_list(values: list[str]) -> list[int]:
    """Parse a list of repeated query-string values into a list of ints, skipping junk."""
    out: list[int] = []
    for raw in values:
        for part in raw.split(","):
            token = part.strip()
            if not token:
                continue
            with suppress(ValueError):
                out.append(int(token))
    return out


def parse_local_date(value: str | None) -> date | None:
    """Parse a `YYYY-MM-DD` date string; return None for missing/invalid input."""
    if not value:
        return None
    with suppress(ValueError):
        return date.fromisoformat(value)
    return None


def local_day_to_utc(d: date, tz_offset: int | None, *, end_of_day: bool) -> datetime:
    """
    Convert a viewer's local-calendar date into a UTC datetime boundary.

    `tz_offset` is the JavaScript convention (minutes west of UTC); a positive value
    such as `480` means the viewer is at UTC-8. When `end_of_day` is True, the
    boundary is the exclusive end-of-day (start of the next day) so date filters can
    be expressed as half-open ranges.
    """
    base = datetime(d.year, d.month, d.day, tzinfo=UTC)
    if end_of_day:
        base += timedelta(days=1)
    if tz_offset is not None:
        base += timedelta(minutes=tz_offset)
    return base


def parse_filters(
    request: web.Request,
    kind: RecordKind,
    tz_offset: int | None,
) -> tuple[RecordFilters, dict[str, Any]]:
    """Parse filter / sort query parameters into a `RecordFilters` plus raw form values."""
    q = request.query
    raw: dict[str, Any] = {
        "with_player": q.get("with_player", "").strip(),
        "guild": q.get("guild", "").strip(),
        "formats": parse_int_list(q.getall("formats", [])),
        "brackets": parse_int_list(q.getall("brackets", [])),
        "from": q.get("from", "").strip(),
        "to": q.get("to", "").strip(),
    }

    valid_sort = (
        USER_RECORDS_SORT_COLUMNS if kind is RecordKind.USER else CHANNEL_RECORDS_SORT_COLUMNS
    )
    sort_by = q.get("sort", DEFAULT_SORT_BY)
    if sort_by not in valid_sort:
        sort_by = DEFAULT_SORT_BY
    sort_dir = q.get("dir", DEFAULT_SORT_DIR).lower()
    if sort_dir not in VALID_SORT_DIRS:
        sort_dir = DEFAULT_SORT_DIR
    raw["sort"] = sort_by
    raw["dir"] = sort_dir

    with_player_xid: int | None = None
    with_player_name: str | None = None
    if raw["with_player"]:
        with suppress(ValueError):
            with_player_xid = int(raw["with_player"])
        if with_player_xid is None:
            with_player_name = raw["with_player"]

    guild_xid_filter: int | None = None
    guild_name_filter: str | None = None
    if kind is RecordKind.USER and raw["guild"]:
        with suppress(ValueError):
            guild_xid_filter = int(raw["guild"])
        if guild_xid_filter is None:
            guild_name_filter = raw["guild"]

    from_date = parse_local_date(raw["from"])
    to_date = parse_local_date(raw["to"])
    from_utc = local_day_to_utc(from_date, tz_offset, end_of_day=False) if from_date else None
    to_utc = local_day_to_utc(to_date, tz_offset, end_of_day=True) if to_date else None

    return RecordFilters(
        with_player_xid=with_player_xid,
        with_player_name=with_player_name,
        guild_xid=guild_xid_filter,
        guild_name=guild_name_filter,
        formats=raw["formats"],
        brackets=raw["brackets"],
        from_utc=from_utc,
        to_utc=to_utc,
        sort_by=sort_by,
        sort_dir=sort_dir,
    ), raw


async def parse_opts(request: web.Request, kind: RecordKind) -> Opts:
    """Parse out the request options from web request object."""
    if kind is RecordKind.CHANNEL:
        guild_xid: int | None = int(request.match_info["guild"])
        target_xid = int(request.match_info["channel"])
    else:
        guild_xid = None
        target_xid = int(request.match_info["user"])

    page = max(int(request.query.get("page", 0)), 0)

    tz_offset_cookie = request.cookies.get("timezone_offset")
    tz_offset: int | None = None
    if tz_offset_cookie:
        with suppress(ValueError):
            tz_offset = int(tz_offset_cookie)

    tz_name = request.cookies.get("timezone_name")
    filters, raw_filters = parse_filters(request, kind, tz_offset)

    return Opts(
        guild_xid=guild_xid,
        target_xid=target_xid,
        page=page,
        tz_offset=tz_offset,
        tz_name=tz_name,
        filters=filters,
        raw_filters=raw_filters,
    )


def build_query_string(raw_filters: dict[str, Any], *, page: int | None) -> str:
    """Build a query string preserving filters, optionally setting `page`."""
    parts: list[tuple[str, str]] = []
    for key in ("with_player", "guild", "from", "to"):
        value = raw_filters.get(key)
        if value:
            parts.append((key, value))
    parts.extend(("formats", str(value)) for value in raw_filters.get("formats") or [])
    parts.extend(("brackets", str(value)) for value in raw_filters.get("brackets") or [])
    if raw_filters.get("sort") and raw_filters["sort"] != DEFAULT_SORT_BY:
        parts.append(("sort", raw_filters["sort"]))
    if raw_filters.get("dir") and raw_filters["dir"] != DEFAULT_SORT_DIR:
        parts.append(("dir", raw_filters["dir"]))
    if page is not None and page > 0:
        parts.append(("page", str(page)))
    return f"?{urlencode(parts)}" if parts else ""


def sort_choices(kind: RecordKind) -> list[dict[str, str]]:
    """Build the list of sortable column labels for the templates."""
    if kind is RecordKind.USER:
        keys = list(USER_RECORDS_SORT_COLUMNS.keys())
    else:
        keys = list(CHANNEL_RECORDS_SORT_COLUMNS.keys())
    labels = {
        "id": "Game",
        "updated_at": "Time",
        "guild_name": "Guild",
        "format": "Format",
        "seats": "Seats",
        "bracket": "Bracket",
    }
    return [{"key": k, "label": labels.get(k, k)} for k in keys]


def format_choices() -> list[dict[str, Any]]:
    return [{"value": f.value, "label": str(f)} for f in GAME_FORMAT_ORDER]


def bracket_choices() -> list[dict[str, Any]]:
    return [{"value": b.value, "label": str(b)} for b in GAME_BRACKET_ORDER]


async def impl(request: web.Request, kind: RecordKind) -> web.Response:
    try:
        opts = await parse_opts(request, kind)
    except ValueError:
        return web.Response(status=404)

    if kind is RecordKind.CHANNEL:
        assert opts.guild_xid is not None
        result = await services.plays.channel_records(
            guild_xid=opts.guild_xid,
            channel_xid=opts.target_xid,
            page=opts.page,
            opts=opts.filters,
        )
    else:
        result = await services.plays.user_records(
            user_xid=opts.target_xid,
            page=opts.page,
            opts=opts.filters,
        )

    if result is None:
        return web.Response(status=404)
    records, total = result

    if kind is RecordKind.CHANNEL:
        assert opts.guild_xid is not None
        guild = await services.guilds.get(opts.guild_xid)
        guild_name = guild.name if guild else None
        channel = await services.channels.select(opts.target_xid)
        target_name = channel.name if channel else None
        page_size = CHANNEL_PAGE_SIZE
    else:
        guild_name = None
        user = await services.users.get(opts.target_xid)
        target_name = user.name if user else None
        page_size = USER_PAGE_SIZE

    has_next = (opts.page + 1) * page_size < total
    prev_qs = build_query_string(opts.raw_filters, page=max(opts.page - 1, 0))
    next_qs = build_query_string(opts.raw_filters, page=opts.page + 1)
    export_qs = build_query_string(opts.raw_filters, page=None)

    path = f"{'channel' if kind is RecordKind.CHANNEL else 'user'}_record.html.j2"
    context = {
        "records": records,
        "total": total,
        "tz_offset": opts.tz_offset,
        "tz_name": opts.tz_name,
        "guild_xid": opts.guild_xid,
        "guild_name": guild_name,
        "target_xid": opts.target_xid,
        "target_name": target_name,
        "page": opts.page,
        "page_size": page_size,
        "has_prev": opts.page > 0,
        "has_next": has_next,
        "prev_page": f"{request.path}{prev_qs}",
        "next_page": f"{request.path}{next_qs}",
        "export_url": f"{request.path}/export.csv{export_qs}",
        "filters": opts.raw_filters,
        "sort_by": opts.filters.sort_by,
        "sort_dir": opts.filters.sort_dir,
        "sort_choices": sort_choices(kind),
        "format_choices": format_choices(),
        "bracket_choices": bracket_choices(),
    }
    return aiohttp_jinja2.render_template(path, request, context)


@routes.get(r"/g/{guild}/c/{channel}")
@tracer.wrap(name="web", resource="channel_record")
async def channel_endpoint(request: web.Request) -> web.Response:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await impl(request, RecordKind.CHANNEL)


@routes.get(r"/u/{user}")
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


async def guild_impl(request: web.Request) -> web.Response:
    try:
        guild_xid = int(request.match_info["guild"])
    except ValueError:
        return web.Response(status=404)
    guild = await services.games.guild_detail_view(guild_xid)
    if guild is None:
        return web.Response(status=404)

    tz_offset_cookie = request.cookies.get("timezone_offset")
    tz_offset: int | None = None
    if tz_offset_cookie:
        with suppress(ValueError):
            tz_offset = int(tz_offset_cookie)
    tz_name = request.cookies.get("timezone_name")

    context = {
        "guild": guild["guild"],
        "channels": guild["channels"],
        "tz_offset": tz_offset,
        "tz_name": tz_name,
    }
    return aiohttp_jinja2.render_template("guild.html.j2", request, context)


@routes.get(r"/g/{guild}")
@tracer.wrap(name="web", resource="guild_detail")
async def guild_endpoint(request: web.Request) -> web.Response:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await guild_impl(request)


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
        if kind is RecordKind.CHANNEL:
            guild_xid = int(request.match_info["guild"])
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
        if not await services.plays.user_export_target_exists(target_xid):
            return web.Response(status=404)
        header = USER_EXPORT_HEADER
        stream = services.plays.stream_user_records(target_xid)
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


@routes.get(r"/u/{user}/export.csv")
@tracer.wrap(name="web", resource="user_record_export")
async def user_export_endpoint(request: web.Request) -> web.StreamResponse:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await export_impl(request, RecordKind.USER)
