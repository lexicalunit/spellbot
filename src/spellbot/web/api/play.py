from __future__ import annotations

import logging
from typing import Any

import aiohttp_jinja2
from aiohttp import web
from ddtrace.trace import tracer

from spellbot import services
from spellbot.database import db_session_manager
from spellbot.enums import (
    GAME_BRACKET_ORDER,
    GAME_FORMAT_ORDER,
    GAME_SERVICE_ORDER,
    MAX_SEATS,
    MIN_SEATS,
    GameFormat,
    GameService,
)
from spellbot.i18n import best_locale, t
from spellbot.metrics import add_span_request_id, generate_request_id
from spellbot.models import (
    MAX_RULES_LENGTH,
    WebActionError,
    WebActionKind,
    WebActionStatus,
)
from spellbot.settings import settings
from spellbot.web.api import discord_api
from spellbot.web.api.moderation import viewer_is_moderator
from spellbot.web.api.queues import (
    PLAYED_GUILDS_WINDOW,
    SPELLBOT_DEFAULT_LOGO,
    language_name,
    resolve_icons,
)
from spellbot.web.api.viewer_auth import get_viewer
from spellbot.web.tools import rate_limited

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

VALID_FORMAT_VALUES = {f.value for f in GAME_FORMAT_ORDER}
VALID_BRACKET_VALUES = {b.value for b in GAME_BRACKET_ORDER}
VALID_SERVICE_VALUES = {s.value for s in GAME_SERVICE_ORDER}

# Why a channel can not be used, in the order we report it. These are stable codes the
# template turns into translated text (`web.play.blocked.*`).
BLOCKED_NOT_A_MEMBER = "not_a_member"
BLOCKED_NO_ACCESS = "no_access"
BLOCKED_NO_SEND = "no_send"
BLOCKED_NO_COMMANDS = "no_commands"
BLOCKED_VERIFIED_ONLY = "verified_only"
BLOCKED_UNVERIFIED_ONLY = "unverified_only"

BLOCKED_CODES = (
    BLOCKED_NOT_A_MEMBER,
    BLOCKED_NO_ACCESS,
    BLOCKED_NO_SEND,
    BLOCKED_NO_COMMANDS,
    BLOCKED_VERIFIED_ONLY,
    BLOCKED_UNVERIFIED_ONLY,
)

# Codes the POST endpoints can return, on top of the blocked-channel codes above and
# everything in `WebActionError` that the bot-side worker can record.
REQUEST_ERROR_CODES = (
    "bot_missing_permissions",
    "channel_not_played",
    "game_started",
    "game_unavailable",
    "guild_unavailable",
    "invalid_bracket",
    "invalid_format",
    "invalid_seats",
    "invalid_service",
    "not_logged_in",
    "too_many_requests",
    "user_banned",
    "web_games_disabled",
)


def blocked_messages(locale: str) -> dict[str, str]:
    """Build the `{code: label}` map used to explain an unusable channel in the picker."""
    return {code: t(f"web.play.blocked.{code}", locale=locale) for code in BLOCKED_CODES}


def error_messages(locale: str) -> dict[str, str]:
    """
    Build the `{code: message}` map the page's JavaScript renders failures from.

    Codes travel over the wire, never prose: the bot process records a code without
    knowing the viewer's language, and this is where it becomes text in theirs.
    """
    codes = {*BLOCKED_CODES, *REQUEST_ERROR_CODES, *(e.value for e in WebActionError)}
    return {code: t(f"web.play.error.{code}", locale=locale) for code in sorted(codes)}


def parse_int(raw: Any) -> int | None:
    try:
        return int(raw)
    except TypeError, ValueError:
        return None


def bot_user_xid() -> int | None:
    """Return the bot's own Discord user id, used to check whether it can post."""
    return parse_int(settings.BOT_APPLICATION_ID)


async def channel_block_reason(
    guild_xid: int,
    channel_xid: int,
    viewer_xid: int,
    channel_data: Any,
    *,
    is_moderator: bool,
) -> str | None:
    """
    Return why this viewer may not start a game in this channel, or `None` if they may.

    Two independent gates apply. Discord's own: the viewer must still be a member, must
    be able to see the channel, post in it, and use application commands there — exactly
    what running `/lfg` would require of them. And SpellBot's: the channel's
    verified-only / unverified-only rules, which moderators bypass just as they do in
    the bot.

    A `None` from `member_channel_permissions` means we could not establish access, and
    is treated as a denial.
    """
    perms = await discord_api.member_channel_permissions(guild_xid, channel_xid, viewer_xid)
    if perms is None:
        return BLOCKED_NOT_A_MEMBER
    if not perms.view_channel:
        return BLOCKED_NO_ACCESS
    if not perms.send_messages:
        return BLOCKED_NO_SEND
    if not perms.use_application_commands:
        return BLOCKED_NO_COMMANDS

    if not is_moderator and channel_data is not None:
        verified = await services.users.is_verified(viewer_xid, guild_xid)
        if channel_data.verified_only and not verified:
            return BLOCKED_VERIFIED_ONLY
        if channel_data.unverified_only and verified:
            return BLOCKED_UNVERIFIED_ONLY
    return None


async def bot_can_post(guild_xid: int, channel_xid: int) -> bool:
    """Return True when the bot itself can post in this channel."""
    if (bot_xid := bot_user_xid()) is None:
        # Without a configured application id we can not check; let the bot-side
        # check (which runs against live gateway state) be the gate.
        return True
    perms = await discord_api.member_channel_permissions(guild_xid, channel_xid, bot_xid)
    return perms is not None and perms.view_channel and perms.send_messages


def format_choices() -> list[dict[str, Any]]:
    return [{"value": f.value, "label": str(f), "players": f.players} for f in GAME_FORMAT_ORDER]


def bracket_choices() -> list[dict[str, Any]]:
    return [{"value": b.value, "label": str(b)} for b in GAME_BRACKET_ORDER]


def service_choices() -> list[dict[str, Any]]:
    return [
        {"value": s.value, "label": s.title, "max_seats": s.max_seats} for s in GAME_SERVICE_ORDER
    ]


@routes.get("/play")
@tracer.wrap(name="web", resource="play")
async def play_endpoint(request: web.Request) -> web.StreamResponse:
    """List the servers this viewer can start a SpellBot game in from the website."""
    add_span_request_id(generate_request_id())
    viewer_xid, viewer_name = await get_viewer(request)
    if viewer_xid is None:
        return web.HTTPFound("/login?next=/play")
    async with db_session_manager():
        raw_guilds = await services.queues.viewer_played_guilds(
            viewer_xid,
            played_within=PLAYED_GUILDS_WINDOW,
            require_promote=False,
        )
        guild_data_by_xid = {
            row["guild_xid"]: await services.guilds.get(row["guild_xid"]) for row in raw_guilds
        }
        backfilled = await resolve_icons(raw_guilds)
    guilds = [
        {
            **row,
            "logo": row.get("guild_icon")
            or backfilled.get(row["guild_xid"])
            or SPELLBOT_DEFAULT_LOGO,
            "language": language_name(row["guild_locale"]),
            "web_games": bool(
                (data := guild_data_by_xid.get(row["guild_xid"])) is None or data.web_games,
            ),
        }
        for row in raw_guilds
    ]
    context = {
        "guilds": guilds,
        "default_logo": SPELLBOT_DEFAULT_LOGO,
        "viewer": {"xid": viewer_xid, "name": viewer_name, "logged_in": True},
    }
    return aiohttp_jinja2.render_template("play.html.j2", request, context)


@routes.get(r"/play/g/{guild}")
@tracer.wrap(name="web", resource="play_guild")
async def play_guild_endpoint(request: web.Request) -> web.StreamResponse:
    """Show the channels this viewer may start a game in, and the games they may join."""
    add_span_request_id(generate_request_id())
    guild_xid = parse_int(request.match_info.get("guild"))
    if guild_xid is None:
        return web.Response(status=404)
    viewer_xid, viewer_name = await get_viewer(request)
    if viewer_xid is None:
        return web.HTTPFound(f"/login?next=/play/g/{guild_xid}")

    async with db_session_manager():
        guild_data = await services.guilds.get(guild_xid)
        if guild_data is None or guild_data.banned:
            return web.Response(status=404)
        played_channels = await services.queues.viewer_played_channels(
            viewer_xid,
            guild_xid,
            played_within=PLAYED_GUILDS_WINDOW,
        )
        channel_data_by_xid = {
            row["channel_xid"]: await services.channels.select(row["channel_xid"])
            for row in played_channels
        }
        is_moderator = await viewer_is_moderator(viewer_xid, guild_xid)
        locale = best_locale(request.headers.get("Accept-Language"))
        blocked_labels = blocked_messages(locale)
        channels = []
        for row in played_channels:
            channel_xid = row["channel_xid"]
            channel_data = channel_data_by_xid.get(channel_xid)
            blocked = await channel_block_reason(
                guild_xid,
                channel_xid,
                viewer_xid,
                channel_data,
                is_moderator=is_moderator,
            )
            if blocked is None and not await bot_can_post(guild_xid, channel_xid):
                blocked = BLOCKED_NO_SEND
            channels.append(
                {
                    **row,
                    "blocked": blocked,
                    "blocked_label": blocked_labels.get(blocked) if blocked else None,
                    "default_format": (
                        channel_data.default_format.value
                        if channel_data and channel_data.default_format
                        else GameFormat.COMMANDER.value
                    ),
                    "default_bracket": (
                        channel_data.default_bracket.value
                        if channel_data and channel_data.default_bracket
                        else None
                    ),
                    "default_service": (
                        channel_data.default_service.value
                        if channel_data and channel_data.default_service
                        else GameService.CONVOKE.value
                    ),
                    "default_seats": channel_data.default_seats if channel_data else 4,
                },
            )
        open_channel_xids = [c["channel_xid"] for c in channels if c["blocked"] is None]
        games = await services.queues.pending_games_in_channels(
            guild_xid,
            open_channel_xids,
            viewer_xid=viewer_xid,
        )
        summary = await services.queues.guild_summary(guild_xid)
        backfilled = await resolve_icons([summary] if summary else [])

    context = {
        "guild": {
            "guild_xid": guild_xid,
            "guild_name": guild_data.name or "",
            "web_games": guild_data.web_games,
            "logo": guild_data.icon or backfilled.get(guild_xid) or SPELLBOT_DEFAULT_LOGO,
            "language": language_name(guild_data.locale),
        },
        "channels": channels,
        "games": games,
        "format_choices": format_choices(),
        "bracket_choices": bracket_choices(),
        "service_choices": service_choices(),
        "min_seats": MIN_SEATS,
        "max_seats": MAX_SEATS,
        "max_rules_length": MAX_RULES_LENGTH,
        "errors": error_messages(locale),
        "default_logo": SPELLBOT_DEFAULT_LOGO,
        "viewer": {"xid": viewer_xid, "name": viewer_name, "logged_in": True},
    }
    return aiohttp_jinja2.render_template("play_guild.html.j2", request, context)


def json_error(code: str, *, status: int = 400) -> web.Response:
    return web.json_response({"ok": False, "error": code}, status=status)


async def authorize_channel(
    guild_xid: int,
    channel_xid: int,
    viewer_xid: int,
) -> str | None:
    """Return an error code when this viewer may not act in this channel, else `None`."""
    guild_data = await services.guilds.get(guild_xid)
    if guild_data is None or guild_data.banned:
        return "guild_unavailable"
    if not guild_data.web_games:
        return "web_games_disabled"
    user_data = await services.users.get(viewer_xid)
    if user_data is not None and user_data.banned:
        return "user_banned"
    # The viewer may only act in channels they have actually played in. This is what
    # keeps the website from becoming a way to post into arbitrary channels of any
    # server the bot happens to be in.
    played = await services.queues.viewer_played_channels(
        viewer_xid,
        guild_xid,
        played_within=PLAYED_GUILDS_WINDOW,
    )
    if channel_xid not in {row["channel_xid"] for row in played}:
        return "channel_not_played"
    channel_data = await services.channels.select(channel_xid)
    is_moderator = await viewer_is_moderator(viewer_xid, guild_xid)
    if blocked := await channel_block_reason(
        guild_xid,
        channel_xid,
        viewer_xid,
        channel_data,
        is_moderator=is_moderator,
    ):
        return blocked
    if not await bot_can_post(guild_xid, channel_xid):
        return "bot_missing_permissions"
    return None


def parse_create_form(form: Any) -> dict[str, Any] | str:
    """Validate a posted create-game form, returning params or an error code."""
    params: dict[str, Any] = {}

    if (raw := form.get("format")) not in (None, ""):
        value = parse_int(raw)
        if value not in VALID_FORMAT_VALUES:
            return "invalid_format"
        params["format"] = value
    if (raw := form.get("bracket")) not in (None, ""):
        value = parse_int(raw)
        if value not in VALID_BRACKET_VALUES:
            return "invalid_bracket"
        params["bracket"] = value
    if (raw := form.get("service")) not in (None, ""):
        value = parse_int(raw)
        if value not in VALID_SERVICE_VALUES:
            return "invalid_service"
        params["service"] = value
    if (raw := form.get("seats")) not in (None, ""):
        value = parse_int(raw)
        if value is None or not MIN_SEATS <= value <= MAX_SEATS:
            return "invalid_seats"
        params["seats"] = value
    if rules := (form.get("rules") or "").strip():
        params["rules"] = rules[:MAX_RULES_LENGTH]

    # `friends` is deliberately not accepted from the website. On Discord it is a
    # mention string the client builds from a real member picker; accepting arbitrary
    # user ids here would be a way to drag people into games they never chose. Anything
    # left unset falls through to the channel's configured defaults, exactly as `/lfg`
    # with no arguments does.
    return params


@routes.post(r"/play/g/{guild}/c/{channel}/create")
@tracer.wrap(name="web", resource="play_create")
async def play_create_endpoint(request: web.Request) -> web.StreamResponse:
    """Ask the bot to create a game in a channel on this viewer's behalf."""
    add_span_request_id(generate_request_id())
    guild_xid = parse_int(request.match_info.get("guild"))
    channel_xid = parse_int(request.match_info.get("channel"))
    if guild_xid is None or channel_xid is None:
        return web.Response(status=404)
    viewer_xid, _ = await get_viewer(request)
    if viewer_xid is None:
        return json_error("not_logged_in", status=401)
    if await rate_limited(request, key=f"play_create:{viewer_xid}"):
        return json_error("too_many_requests", status=429)

    form = await request.post()
    async with db_session_manager():
        if error := await authorize_channel(guild_xid, channel_xid, viewer_xid):
            return json_error(error, status=403)
        parsed = parse_create_form(form)
        if isinstance(parsed, str):
            return json_error(parsed)
        await services.users.ensure_exists(viewer_xid)
        action = await services.web_actions.enqueue(
            user_xid=viewer_xid,
            guild_xid=guild_xid,
            channel_xid=channel_xid,
            kind=WebActionKind.CREATE.value,
            locale=best_locale(request.headers.get("Accept-Language")),
            params=parsed,
        )
    return web.json_response({"ok": True, "action_id": action.id, "status": action.status})


async def enqueue_for_game(
    request: web.Request,
    kind: str,
) -> web.StreamResponse:
    """Shared body for the join and leave endpoints, which differ only in `kind`."""
    add_span_request_id(generate_request_id())
    game_id = parse_int(request.match_info.get("game"))
    if game_id is None:
        return web.Response(status=404)
    viewer_xid, _ = await get_viewer(request)
    if viewer_xid is None:
        return json_error("not_logged_in", status=401)
    if await rate_limited(request, key=f"play_{kind}:{viewer_xid}"):
        return json_error("too_many_requests", status=429)

    async with db_session_manager():
        game_data = await services.games.get(game_id)
        if game_data is None or game_data.deleted_at is not None:
            return json_error("game_unavailable", status=404)
        if game_data.started_at is not None:
            return json_error("game_started", status=409)
        if error := await authorize_channel(
            game_data.guild_xid,
            game_data.channel_xid,
            viewer_xid,
        ):
            return json_error(error, status=403)
        await services.users.ensure_exists(viewer_xid)
        action = await services.web_actions.enqueue(
            user_xid=viewer_xid,
            guild_xid=game_data.guild_xid,
            channel_xid=game_data.channel_xid,
            kind=kind,
            locale=best_locale(request.headers.get("Accept-Language")),
            game_id=game_id,
        )
    return web.json_response({"ok": True, "action_id": action.id, "status": action.status})


@routes.post(r"/play/game/{game}/join")
@tracer.wrap(name="web", resource="play_join")
async def play_join_endpoint(request: web.Request) -> web.StreamResponse:
    """Ask the bot to join this viewer to a pending game."""
    return await enqueue_for_game(request, WebActionKind.JOIN.value)


@routes.post(r"/play/game/{game}/leave")
@tracer.wrap(name="web", resource="play_leave")
async def play_leave_endpoint(request: web.Request) -> web.StreamResponse:
    """Ask the bot to remove this viewer from a pending game."""
    return await enqueue_for_game(request, WebActionKind.LEAVE.value)


@routes.get(r"/play/action/{action}.json")
@tracer.wrap(name="web", resource="play_action_status")
async def play_action_status_endpoint(request: web.Request) -> web.StreamResponse:
    """Report the outcome of a request, for the page that is waiting on it."""
    add_span_request_id(generate_request_id())
    action_id = parse_int(request.match_info.get("action"))
    if action_id is None:
        return web.Response(status=404)
    viewer_xid, _ = await get_viewer(request)
    if viewer_xid is None:
        return json_error("not_logged_in", status=401)
    async with db_session_manager():
        action = await services.web_actions.get(action_id, user_xid=viewer_xid)
    if action is None:
        return web.Response(status=404)
    payload: dict[str, Any] = {
        "ok": action.status != WebActionStatus.ERROR.value,
        "action_id": action.id,
        "status": action.status,
        "kind": action.kind,
        "error": action.error_code,
        "notices": action.notices,
        "game_id": action.game_id,
    }
    if action.game_id is not None and action.status == WebActionStatus.DONE.value:
        payload["game_url"] = f"/game/{action.game_id}"
    return web.json_response(payload)
