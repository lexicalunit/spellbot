from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import aiohttp_jinja2
from aiohttp import web
from babel import Locale, UnknownLocaleError
from ddtrace.trace import tracer

from spellbot import services
from spellbot.database import db_session_manager
from spellbot.enums import GAME_BRACKET_ORDER, GAME_FORMAT_ORDER
from spellbot.i18n import normalize_locale
from spellbot.metrics import add_span_request_id, generate_request_id
from spellbot.settings import settings
from spellbot.web.api.viewer_auth import get_viewer

if TYPE_CHECKING:
    from collections.abc import Iterable

SPELLBOT_DEFAULT_LOGO = "https://spellbot.io/assets/img/avatar-icon.png"
ICON_FETCH_TTL = timedelta(hours=6)
STARTED_GAMES_WINDOW = timedelta(hours=2)
PLAYED_GUILDS_WINDOW = timedelta(days=365)

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
        raw_games = await services.queues.public_active_games(
            STARTED_GAMES_WINDOW,
            only_member_of=member_of,
        )
        raw_played_guilds = (
            await services.queues.viewer_played_guilds(
                viewer_xid,
                played_within=PLAYED_GUILDS_WINDOW,
            )
            if viewer_xid is not None
            else []
        )
        alert_guild_xids = (
            await services.alerts.get_guild_xids_for_user(viewer_xid)
            if viewer_xid is not None
            else set()
        )
        backfilled = await _resolve_icons(raw_rows + raw_games + raw_played_guilds)
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
    games = [
        {
            **game,
            "logo": game.get("guild_icon")
            or backfilled.get(game["guild_xid"])
            or SPELLBOT_DEFAULT_LOGO,
            "language": language_name(game["guild_locale"]),
        }
        for game in raw_games
    ]
    played_guilds = [
        {
            **pg,
            "logo": pg.get("guild_icon")
            or backfilled.get(pg["guild_xid"])
            or SPELLBOT_DEFAULT_LOGO,
            "notifications_on": pg["guild_xid"] in alert_guild_xids,
        }
        for pg in raw_played_guilds
    ]
    formats = sorted({r["format"] for r in rows} | {g["format"] for g in games})
    brackets = sorted({r["bracket"] for r in rows} | {g["bracket"] for g in games})
    languages = sorted({r["language"] for r in rows} | {g["language"] for g in games})
    stats = {"active_games": len(raw_rows) + len(raw_games)}
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
        "games": games,
        "played_guilds": played_guilds,
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
    """Return the public list of pending queues and recently-started games as JSON."""
    add_span_request_id(generate_request_id())
    only_mythic_track = request.query.get("mythic_track") == "1"
    async with db_session_manager():
        raw_rows = await services.queues.public_active_queues(
            only_mythic_track=only_mythic_track,
        )
        raw_games = await services.queues.public_active_games(
            STARTED_GAMES_WINDOW,
            only_mythic_track=only_mythic_track,
        )
        backfilled = await _resolve_icons(raw_rows + raw_games)
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
    games = [
        {
            "guild_xid": game["guild_xid"],
            "guild_name": game["guild_name"],
            "guild_locale": game["guild_locale"],
            "logo": game.get("guild_icon")
            or backfilled.get(game["guild_xid"])
            or SPELLBOT_DEFAULT_LOGO,
            "format": game["format"],
            "bracket": game["bracket"],
            "service": game["service"],
            "seats": game["seats"],
            "started_seconds_ago": game["started_seconds_ago"],
            "jump_url": game["jump_url"],
        }
        for game in raw_games
    ]
    return web.json_response(
        {
            "stats": {"active_games": len(raw_rows) + len(raw_games)},
            "queues": queues,
            "games": games,
        },
    )


def notify_format_choices() -> list[dict[str, Any]]:
    return [{"value": f.value, "label": str(f)} for f in GAME_FORMAT_ORDER]


def notify_bracket_choices() -> list[dict[str, Any]]:
    return [{"value": b.value, "label": str(b)} for b in GAME_BRACKET_ORDER]


VALID_FORMAT_VALUES = {f.value for f in GAME_FORMAT_ORDER}
VALID_BRACKET_VALUES = {b.value for b in GAME_BRACKET_ORDER}


def wants_json(request: web.Request) -> bool:
    """Return True if the request's `Accept` header prefers JSON."""
    accept = request.headers.get("Accept", "")
    return "application/json" in accept


@routes.get(r"/queues/g/{guild}")
@tracer.wrap(name="web", resource="queue_guild_notify")
async def guild_notify_endpoint(request: web.Request) -> web.Response:
    """Render the per-guild notification preferences page for the current viewer."""
    add_span_request_id(generate_request_id())
    try:
        guild_xid = int(request.match_info["guild"])
    except KeyError, ValueError:
        return web.Response(status=404)
    viewer_xid, viewer_name = await get_viewer(request)
    if viewer_xid is None:
        return web.HTTPFound(f"/queues/login?next=/queues/g/{guild_xid}")
    async with db_session_manager():
        guild = await services.queues.guild_summary(guild_xid)
        if guild is None:
            return web.Response(status=404)
        backfilled = await _resolve_icons([guild])
        # Fetch soft-deleted alerts too so the viewer's prior preferences can be
        # re-displayed (and restored on save) after they previously turned
        # notifications off for this guild.
        existing = await services.alerts.get_for_user_guild(
            guild_xid,
            viewer_xid,
            include_deleted=True,
        )
        played_channels = await services.queues.viewer_played_channels(
            viewer_xid,
            guild_xid,
            played_within=PLAYED_GUILDS_WINDOW,
        )
    guild_view = {
        **guild,
        "logo": guild.get("guild_icon")
        or backfilled.get(guild["guild_xid"])
        or SPELLBOT_DEFAULT_LOGO,
        "language": language_name(guild["guild_locale"]),
    }
    channel_choices = [
        {"value": c["channel_xid"], "label": c["channel_name"] or str(c["channel_xid"])}
        for c in played_channels
    ]
    valid_channel_values = {c["value"] for c in channel_choices}
    selected_formats = set(existing.formats) if existing else set()
    selected_brackets = set(existing.brackets) if existing else set()
    selected_channels = (
        {c for c in existing.channels if c in valid_channel_values} if existing else set()
    )
    active_hours = existing.active_hours if existing else None
    notifications_off = existing is None or existing.deleted_at is not None
    context = {
        "guild": guild_view,
        "default_logo": SPELLBOT_DEFAULT_LOGO,
        "format_choices": notify_format_choices(),
        "bracket_choices": notify_bracket_choices(),
        "channel_choices": channel_choices,
        "selected_formats": selected_formats,
        "selected_brackets": selected_brackets,
        "selected_channels": selected_channels,
        "notifications_off": notifications_off,
        "active_hours": active_hours,
        "active_hours_max_length": services.alerts.ACTIVE_HOURS_MAX_LENGTH,
        "viewer": {"xid": viewer_xid, "name": viewer_name, "logged_in": True},
    }
    return aiohttp_jinja2.render_template("guild_notify.html.j2", request, context)


def parse_notify_values(raw: Iterable[Any], valid: set[int]) -> list[int] | None:
    """Parse and validate posted enum-int values; return None if any value is invalid."""
    parsed: list[int] = []
    for value in raw:
        try:
            parsed.append(int(value))
        except TypeError, ValueError:
            return None
    if any(v not in valid for v in parsed):
        return None
    return parsed


def parse_active_hours_form(form: Any) -> dict[str, Any] | None:
    """Extract a raw active_hours payload from posted form data, or None when off."""
    if not form.get("active_hours_enabled"):
        return None
    return {
        "start": form.get("active_hours_start"),
        "end": form.get("active_hours_end"),
        "tz": form.get("active_hours_tz"),
    }


@routes.post(r"/queues/g/{guild}/notify")
@tracer.wrap(name="web", resource="queue_guild_notify_save")
async def guild_notify_save_endpoint(request: web.Request) -> web.StreamResponse:
    """Save the viewer's notification preferences for a guild."""
    add_span_request_id(generate_request_id())
    try:
        guild_xid = int(request.match_info["guild"])
    except KeyError, ValueError:
        return web.Response(status=404)
    viewer_xid, _ = await get_viewer(request)
    if viewer_xid is None:
        return web.HTTPFound(f"/queues/login?next=/queues/g/{guild_xid}")
    form = await request.post()
    if form.get("off"):
        async with db_session_manager():
            await services.alerts.delete(guild_xid, viewer_xid)
        if wants_json(request):
            return web.json_response({"ok": True, "off": True})
        return web.HTTPFound(f"/queues/g/{guild_xid}")
    formats = parse_notify_values(form.getall("formats", []), VALID_FORMAT_VALUES)
    brackets = parse_notify_values(form.getall("brackets", []), VALID_BRACKET_VALUES)
    active_hours_raw = parse_active_hours_form(form)
    try:
        active_hours = services.alerts.parse_active_hours(active_hours_raw)
    except ValueError as ex:
        if wants_json(request):
            return web.json_response(
                {"ok": False, "error": "invalid_active_hours", "detail": str(ex)},
                status=400,
            )
        return web.Response(status=400)
    async with db_session_manager():
        played_channels = await services.queues.viewer_played_channels(
            viewer_xid,
            guild_xid,
            played_within=PLAYED_GUILDS_WINDOW,
        )
        valid_channel_values = {int(c["channel_xid"]) for c in played_channels}
        channels = parse_notify_values(form.getall("channels", []), valid_channel_values)
        if formats is None or brackets is None or channels is None:
            if wants_json(request):
                return web.json_response({"ok": False, "error": "invalid_input"}, status=400)
            return web.Response(status=400)
        saved = await services.alerts.upsert(
            guild_xid,
            viewer_xid,
            formats=formats,
            brackets=brackets,
            channels=channels,
            active_hours=active_hours,
        )
    if wants_json(request):
        return web.json_response(
            {
                "ok": True,
                "formats": saved.formats,
                "brackets": saved.brackets,
                "channels": saved.channels,
                "active_hours": saved.active_hours,
            },
        )
    return web.HTTPFound(f"/queues/g/{guild_xid}")
