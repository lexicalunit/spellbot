from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp_jinja2
from aiohttp import web
from babel import Locale, UnknownLocaleError
from ddtrace.trace import tracer

from spellbot import services
from spellbot.database import db_session_manager
from spellbot.i18n import normalize_locale
from spellbot.metrics import add_span_request_id, generate_request_id
from spellbot.settings import settings
from spellbot.web.api.viewer_auth import get_viewer

SPELLBOT_DEFAULT_LOGO = "https://spellbot.io/assets/img/avatar-icon.png"
ICON_FETCH_TTL = timedelta(hours=6)
STARTED_GAMES_WINDOW = timedelta(hours=2)

_icon_fetch_attempts: dict[int, datetime] = {}

routes = web.RouteTableDef()


def language_name(locale: str | None) -> str:
    """Return an English display name for `locale` (e.g., `ja` -> `Japanese`)."""
    code = normalize_locale(locale or "en")
    try:
        return Locale.parse(code).get_display_name("en") or code
    except UnknownLocaleError, ValueError:
        return code


def format_wait(seconds: int) -> str:
    """Render a wait duration in compact `Xh Ym` / `Xm` / `<1m` form."""
    if seconds < 60:
        return "<1m"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    if minutes == 0:
        return f"{hours}h"
    return f"{hours}h {minutes}m"


async def _resolve_icons(rows: list[dict[str, Any]]) -> dict[int, str | None]:
    """Return a `{guild_xid: icon_url}` map, backfilling missing entries from Discord."""
    now = datetime.now(UTC)
    candidates = {row["guild_xid"] for row in rows if not row.get("guild_icon")}
    missing = [
        xid
        for xid in candidates
        if (last := _icon_fetch_attempts.get(xid)) is None or now - last >= ICON_FETCH_TTL
    ]
    if not missing:
        return {}
    fetched = await asyncio.gather(
        *(services.guilds.fetch_icon_url(xid) for xid in missing),
    )
    results: dict[int, str | None] = {}
    for xid, icon in zip(missing, fetched, strict=True):
        _icon_fetch_attempts[xid] = now
        if icon is not None:
            await services.guilds.set_icon(xid, icon)
        results[xid] = icon
    return results


@routes.get("/queues")
@tracer.wrap(name="web", resource="queues")
async def queues_endpoint(request: web.Request) -> web.Response:
    """Render the public list of pending games that currently have queued players."""
    add_span_request_id(generate_request_id())
    viewer_xid, viewer_name = await get_viewer(request)
    my_filter_on = request.query.get("my") == "1" and viewer_xid is not None
    member_of = viewer_xid if my_filter_on else None
    async with db_session_manager():
        raw_rows = await services.queues.public_active_queues(only_member_of=member_of)
        started_recent = await services.queues.public_recent_started_count(
            STARTED_GAMES_WINDOW,
            only_member_of=member_of,
        )
        backfilled = await _resolve_icons(raw_rows)
    rows = [
        {
            **row,
            "logo": row.get("guild_icon")
            or backfilled.get(row["guild_xid"])
            or SPELLBOT_DEFAULT_LOGO,
            "language": language_name(row["guild_locale"]),
        }
        for row in raw_rows
    ]
    formats = sorted({row["format"] for row in rows})
    brackets = sorted({row["bracket"] for row in rows})
    languages = sorted({row["language"] for row in rows})
    stats = {"started_recent": started_recent}
    login_enabled = bool(settings.BOT_APPLICATION_ID and settings.BOT_CLIENT_SECRET)
    viewer = {
        "xid": viewer_xid,
        "name": viewer_name,
        "logged_in": viewer_xid is not None,
        "login_enabled": login_enabled,
        "my_filter_on": my_filter_on,
    }
    context = {
        "rows": rows,
        "default_logo": SPELLBOT_DEFAULT_LOGO,
        "formats": formats,
        "brackets": brackets,
        "languages": languages,
        "stats": stats,
        "viewer": viewer,
    }
    return aiohttp_jinja2.render_template("queues.html.j2", request, context)


@routes.get("/queues.json")
@tracer.wrap(name="web", resource="queues_json")
async def queues_json_endpoint(request: web.Request) -> web.Response:
    """Return the public list of pending queues as JSON."""
    add_span_request_id(generate_request_id())
    only_mythic_track = request.query.get("mythic_track") == "1"
    async with db_session_manager():
        raw_rows = await services.queues.public_active_queues(
            only_mythic_track=only_mythic_track,
        )
        started_recent = await services.queues.public_recent_started_count(
            STARTED_GAMES_WINDOW,
            only_mythic_track=only_mythic_track,
        )
        backfilled = await _resolve_icons(raw_rows)
    queues = [
        {
            "guild_xid": row["guild_xid"],
            "guild_name": row["guild_name"],
            "guild_locale": row["guild_locale"],
            "logo": row.get("guild_icon")
            or backfilled.get(row["guild_xid"])
            or SPELLBOT_DEFAULT_LOGO,
            "format": row["format"],
            "bracket": row["bracket"],
            "service": row["service"],
            "players": row["players"],
            "seats": row["seats"],
            "wait_seconds": row["wait_seconds"],
            "jump_url": row["jump_url"],
        }
        for row in raw_rows
    ]
    return web.json_response(
        {
            "stats": {"active_games": started_recent},
            "queues": queues,
        },
    )
