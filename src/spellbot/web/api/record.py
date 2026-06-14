from __future__ import annotations

import csv
import io
import logging
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta
from enum import Enum, auto
from typing import Any, NamedTuple
from urllib.parse import quote, urlencode

import aiohttp_jinja2
from aiohttp import web
from ddtrace.trace import tracer

from spellbot import audit, services
from spellbot.database import db_session_manager
from spellbot.enums import (
    GAME_BRACKET_ORDER,
    GAME_FORMAT_ORDER,
    GAME_SERVICE_ORDER,
    MAX_SEATS,
    MIN_SEATS,
    VALID_BRACKETS,
    VALID_FORMATS,
    VALID_SERVICES,
)
from spellbot.metrics import add_span_request_id, generate_request_id
from spellbot.models import Channel, Guild, GuildAward, web_editable_docs
from spellbot.services.plays import (
    CHANNEL_PAGE_SIZE,
    CHANNEL_RECORDS_SORT_COLUMNS,
    USER_PAGE_SIZE,
    USER_RECORDS_SORT_COLUMNS,
    RecordFilters,
)
from spellbot.web.api.admin_auth import is_owner_request
from spellbot.web.api.moderation import viewer_is_moderator
from spellbot.web.api.oauth import safe_relative_path
from spellbot.web.api.viewer_auth import get_viewer

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


def service_choices() -> list[dict[str, Any]]:
    return [{"value": s.value, "label": str(s)} for s in GAME_SERVICE_ORDER]


# The seat counts offered in the channel settings form and accepted on submit.
SEAT_CHOICES = list(range(MIN_SEATS, MAX_SEATS + 1))
VALID_SEATS = frozenset(SEAT_CHOICES)


def form_bool(form: Any, name: str) -> bool:
    """Interpret a checkbox field: present (checked) is True, absent is False."""
    return form.get(name) is not None


def form_str(form: Any, name: str, max_len: int | None) -> str:
    """Read a trimmed string field, truncated to `max_len` when provided."""
    value = (form.get(name) or "").strip()
    return value[:max_len] if max_len else value


def form_choice(form: Any, name: str, valid: frozenset[int]) -> int | None:
    """Read an integer enum field, returning None when missing or out of range."""
    raw = form.get(name)
    if raw is None:
        return None
    try:
        value = int(raw)
    except TypeError, ValueError:
        return None
    return value if value in valid else None


def parse_channel_settings(form: Any) -> dict[str, Any]:
    """Coerce + validate a channel settings form into a column->value mapping."""
    values: dict[str, Any] = {
        "auto_verify": form_bool(form, "auto_verify"),
        "unverified_only": form_bool(form, "unverified_only"),
        "verified_only": form_bool(form, "verified_only"),
        "voice_invite": form_bool(form, "voice_invite"),
        "delete_expired": form_bool(form, "delete_expired"),
        "blind_games": form_bool(form, "blind_games"),
        "to_mode": form_bool(form, "to_mode"),
        "motd": form_str(form, "motd", Channel.motd.property.columns[0].type.length),
        "extra": form_str(form, "extra", Channel.extra.property.columns[0].type.length),
        "voice_category": form_str(
            form,
            "voice_category",
            Channel.voice_category.property.columns[0].type.length,
        ),
    }
    if (seats := form_choice(form, "default_seats", VALID_SEATS)) is not None:
        values["default_seats"] = seats
    if (fmt := form_choice(form, "default_format", VALID_FORMATS)) is not None:
        values["default_format"] = fmt
    if (bracket := form_choice(form, "default_bracket", VALID_BRACKETS)) is not None:
        values["default_bracket"] = bracket
    if (service := form_choice(form, "default_service", VALID_SERVICES)) is not None:
        values["default_service"] = service
    return values


def parse_guild_settings(form: Any) -> dict[str, Any]:
    """Coerce + validate a guild settings form into a column->value mapping."""
    return {
        "show_links": form_bool(form, "show_links"),
        "voice_create": form_bool(form, "voice_create"),
        "use_max_bitrate": form_bool(form, "use_max_bitrate"),
        "enable_mythic_track": form_bool(form, "enable_mythic_track"),
        "motd": form_str(form, "motd", Guild.motd.property.columns[0].type.length),
        "suggest_voice_category": form_str(
            form,
            "suggest_voice_category",
            Guild.suggest_voice_category.property.columns[0].type.length,
        ),
    }


AWARD_ROLE_MAX = GuildAward.role.property.columns[0].type.length
AWARD_MESSAGE_MAX = GuildAward.message.property.columns[0].type.length


def award_help() -> dict[str, str]:
    """Per-field help text for the award form, taken from the model column docs."""
    return {column.name: column.doc for column in GuildAward.__table__.columns if column.doc}


# Award validation errors are surfaced via an `award_error` query parameter on a redirect back to
# the guild page. As with block errors, the redirect only ever carries one of these fixed *codes*;
# the page maps the code to a server-controlled message and ignores anything not in this allow-list,
# so no user-supplied text is ever reflected into the URL or the page.
AWARD_ERRORS = {
    "no_role": "An award needs a role to give or take.",
    "message_too_long": f"An award message can't be longer than {AWARD_MESSAGE_MAX} characters.",
    "bad_count": "An award needs a whole number of games.",
    "zero_count": "An award can't be given for fewer than 1 game.",
    "verify_conflict": "An award can't be both verified and unverified only.",
}


def parse_award_form(form: Any) -> tuple[dict[str, Any] | None, str | None]:
    """Coerce + validate an award form. Returns `(values, None)` or `(None, error_code)`."""
    role = form_str(form, "role", AWARD_ROLE_MAX).lstrip("@")
    if not role:
        return None, "no_role"
    message = form_str(form, "message", None)
    if len(message) > AWARD_MESSAGE_MAX:
        return None, "message_too_long"
    raw_count = (form.get("count") or "").strip()
    try:
        count = int(raw_count)
    except TypeError, ValueError:
        return None, "bad_count"
    if count < 1:
        return None, "zero_count"
    verified_only = form_bool(form, "verified_only")
    unverified_only = form_bool(form, "unverified_only")
    if verified_only and unverified_only:
        return None, "verify_conflict"
    return {
        "count": count,
        "role": role,
        "message": message,
        "repeating": form_bool(form, "repeating"),
        "remove": form_bool(form, "remove"),
        "verified_only": verified_only,
        "unverified_only": unverified_only,
    }, None


async def request_is_moderator(request: web.Request, guild_xid: int) -> bool:
    """Return True when the request's logged-in viewer moderates `guild_xid`."""
    _, is_moderator = await viewer_access(request, guild_xid)
    return is_moderator


async def viewer_access(request: web.Request, guild_xid: int) -> tuple[bool, bool]:
    """Return `(is_logged_in, is_moderator)` for the request's viewer w.r.t. `guild_xid`."""
    viewer_xid, _ = await get_viewer(request)
    if viewer_xid is None:
        return False, False
    return True, await viewer_is_moderator(viewer_xid, guild_xid)


def login_url(request: web.Request) -> str:
    """Build a viewer login URL that returns to the current page after authenticating."""
    # `next` is validated again where it is consumed (see `viewer_auth`), but sanitize the
    # current path here too so a hostile request target can never seed an open redirect.
    next_path = safe_relative_path(request.path_qs) or "/"
    return f"/queues/login?next={quote(next_path, safe='')}"


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

    viewer_xid, _ = await get_viewer(request)
    channel = None
    is_logged_in = False
    is_moderator = False
    is_own_profile = False
    blocked_users: list[Any] = []
    if kind is RecordKind.CHANNEL:
        assert opts.guild_xid is not None
        guild = await services.guilds.get(opts.guild_xid)
        guild_name = guild.name if guild else None
        channel = await services.channels.select(opts.target_xid)
        target_name = channel.name if channel else None
        page_size = CHANNEL_PAGE_SIZE
        is_logged_in, is_moderator = await viewer_access(request, opts.guild_xid)
    else:
        guild_name = None
        user = await services.users.get(opts.target_xid)
        target_name = user.name if user else None
        page_size = USER_PAGE_SIZE
        is_logged_in = viewer_xid is not None
        is_own_profile = viewer_xid == opts.target_xid
        if is_own_profile:
            blocked_users = await services.users.blocklist(opts.target_xid)

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
        "viewer_xid": viewer_xid,
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
        "service_choices": service_choices(),
        "seat_choices": SEAT_CHOICES,
        "channel": channel,
        "channel_help": web_editable_docs(Channel),
        "is_logged_in": is_logged_in,
        "is_moderator": is_moderator,
        "is_own_profile": is_own_profile,
        "blocked_users": blocked_users,
        "block_error": BLOCK_ERRORS.get(request.query.get("block_error", "")),
        "login_url": login_url(request),
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


async def viewer_owns_profile(request: web.Request, user_xid: int) -> bool:
    """Return True when the request's logged-in viewer is the owner of `user_xid`'s profile."""
    viewer_xid, _ = await get_viewer(request)
    return viewer_xid is not None and viewer_xid == user_xid


# Block-list validation errors are surfaced to the user via a `block_error` query parameter on a
# redirect back to their profile. To avoid reflecting attacker-controlled text into the URL (and
# the page), the redirect only ever carries one of these fixed *codes*; the page maps the code to
# a server-controlled message and ignores anything not in this allow-list.
BLOCK_ERRORS = {
    "invalid": "Enter a Discord user ID or name to block.",
    "not_found": "No SpellBot user with that name was found.",
    "self": "You can't block yourself.",
}


async def resolve_block_target(raw: str) -> tuple[int | None, str | None]:
    """Resolve a block-target form value (a Discord id or name) to `(xid, None)`/`(None, code)`."""
    token = (raw or "").strip().lstrip("@")
    if not token:
        return None, "invalid"
    if token.isdigit():
        return int(token), None
    xid = await services.users.get_xid_by_name(token)
    if xid is None:
        return None, "not_found"
    return xid, None


def block_error_redirect(user_xid: int, code: str) -> web.HTTPFound:
    """
    Redirect back to the profile page flagging a block validation error by code.

    The destination is always this user's own internal page: `user_xid` is coerced to an int so the
    path is fixed and can never point off-site, and only a known `BLOCK_ERRORS` code is placed in
    the URL, never user-supplied text.
    """
    safe_code = code if code in BLOCK_ERRORS else "invalid"
    return web.HTTPFound(f"/u/{int(user_xid)}?{urlencode({'block_error': safe_code})}")


async def user_block_add_impl(request: web.Request) -> web.Response:
    """Owner-only: add a user to the profile owner's block list, then redirect back."""
    try:
        user_xid = int(request.match_info["user"])
    except ValueError:
        return web.Response(status=404)
    if not await viewer_owns_profile(request, user_xid):
        return web.Response(status=403, text="Forbidden")
    form = await request.post()
    target_xid, error = await resolve_block_target(str(form.get("target") or ""))
    if target_xid is None:
        assert error is not None
        return block_error_redirect(user_xid, error)
    if target_xid == user_xid:
        return block_error_redirect(user_xid, "self")
    await services.users.ensure_exists(user_xid)
    await services.users.ensure_exists(target_xid)
    await services.users.block(user_xid, target_xid)
    return web.HTTPFound(f"/u/{user_xid}")


@routes.post(r"/u/{user}/blocks/add")
@tracer.wrap(name="web", resource="user_block_add")
async def user_block_add_endpoint(request: web.Request) -> web.StreamResponse:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await user_block_add_impl(request)


async def user_block_remove_impl(request: web.Request) -> web.Response:
    """Owner-only: remove a user from the profile owner's block list, then redirect back."""
    try:
        user_xid = int(request.match_info["user"])
        target_xid = int(request.match_info["target"])
    except ValueError:
        return web.Response(status=404)
    if not await viewer_owns_profile(request, user_xid):
        return web.Response(status=403, text="Forbidden")
    await services.users.unblock(user_xid, target_xid)
    return web.HTTPFound(f"/u/{user_xid}")


@routes.post(r"/u/{user}/blocks/{target}/remove")
@tracer.wrap(name="web", resource="user_block_remove")
async def user_block_remove_endpoint(request: web.Request) -> web.StreamResponse:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await user_block_remove_impl(request)


async def viewer_can_view_game_links(
    game: dict[str, Any],
    viewer_xid: int | None,
) -> bool:
    """
    Return True when the viewer may see a game's join links on its detail page.

    Links are public when the guild has `show_links` enabled (the bot already posts
    them in the channel for everyone to see). Otherwise the links are restricted to
    the game's own players, the guild's moderators/admins, and the bot owner (the
    last two are both covered by `viewer_is_moderator`).
    """
    if game["guild"].get("show_links"):
        return True
    if viewer_xid is None:
        return False
    if any(play["user_xid"] == viewer_xid for play in game["plays"]):
        return True
    return await viewer_is_moderator(viewer_xid, game["guild"]["xid"])


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

    viewer_xid, _ = await get_viewer(request)
    context = {
        "game": game,
        "tz_offset": tz_offset,
        "tz_name": tz_name,
        "viewer_xid": viewer_xid,
        "can_view_links": await viewer_can_view_game_links(game, viewer_xid),
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

    is_logged_in, is_moderator = await viewer_access(request, guild_xid)
    guild_settings = await services.guilds.get(guild_xid) if is_moderator else None
    awards = await services.guilds.award_list(guild_xid) if is_moderator else []
    viewer_xid, _ = await get_viewer(request)

    context = {
        "guild": guild["guild"],
        "channels": guild["channels"],
        "tz_offset": tz_offset,
        "tz_name": tz_name,
        "viewer_xid": viewer_xid,
        "is_owner": await is_owner_request(request),
        "is_logged_in": is_logged_in,
        "is_moderator": is_moderator,
        "login_url": login_url(request),
        "guild_settings": guild_settings,
        "guild_help": web_editable_docs(Guild),
        "awards": awards,
        "award_help": award_help(),
        "award_role_max": AWARD_ROLE_MAX,
        "award_message_max": AWARD_MESSAGE_MAX,
        "award_error": AWARD_ERRORS.get(request.query.get("award_error", "")),
    }
    return aiohttp_jinja2.render_template("guild.html.j2", request, context)


@routes.get(r"/g/{guild}")
@tracer.wrap(name="web", resource="guild_detail")
async def guild_endpoint(request: web.Request) -> web.Response:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await guild_impl(request)


async def guild_promote_impl(request: web.Request) -> web.Response:
    """Owner-only: set a guild's `promote` flag, then redirect back to its page."""
    if not await is_owner_request(request):
        return web.Response(status=403, text="Forbidden")
    try:
        guild_xid = int(request.match_info["guild"])
    except ValueError:
        return web.Response(status=404)
    form = await request.post()
    promote = form.get("promote") == "true"
    await services.guilds.set_promote(guild_xid, promote)
    return web.HTTPFound(f"/g/{guild_xid}")


@routes.post(r"/g/{guild}/promote")
@tracer.wrap(name="web", resource="guild_promote")
async def guild_promote_endpoint(request: web.Request) -> web.StreamResponse:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await guild_promote_impl(request)


async def guild_settings_impl(request: web.Request) -> web.Response:
    """Moderator-only: update a guild's settings, then redirect back to its page."""
    try:
        guild_xid = int(request.match_info["guild"])
    except ValueError:
        return web.Response(status=404)
    if not await request_is_moderator(request, guild_xid):
        return web.Response(status=403, text="Forbidden")
    form = await request.post()
    viewer_xid, viewer_name = await get_viewer(request)
    with audit.actor(viewer_xid, viewer_name, audit.SOURCE_WEB):
        await services.guilds.update_settings(guild_xid, **parse_guild_settings(form))
    return web.HTTPFound(f"/g/{guild_xid}")


@routes.post(r"/g/{guild}/settings")
@tracer.wrap(name="web", resource="guild_settings")
async def guild_settings_endpoint(request: web.Request) -> web.StreamResponse:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await guild_settings_impl(request)


def award_error_redirect(guild_xid: int, code: str) -> web.HTTPFound:
    """
    Redirect back to the guild page flagging an award validation error by code.

    The destination is always this guild's own internal page: `guild_xid` is coerced to an int so
    the path is fixed and can never point off-site, and `code` must be a key of `AWARD_ERRORS`, so
    no user-supplied text is ever reflected. An unrecognized code is dropped rather than reflected.
    """
    location = f"/g/{int(guild_xid)}"
    if code in AWARD_ERRORS:
        location = f"{location}?{urlencode({'award_error': code})}"
    return web.HTTPFound(location)


async def award_add_impl(request: web.Request) -> web.Response:
    """Moderator-only: create a new award on the guild, then redirect back to its page."""
    try:
        guild_xid = int(request.match_info["guild"])
    except ValueError:
        return web.Response(status=404)
    if not await request_is_moderator(request, guild_xid):
        return web.Response(status=403, text="Forbidden")
    form = await request.post()
    values, error = parse_award_form(form)
    if values is None:
        assert error is not None
        return award_error_redirect(guild_xid, error)
    await services.guilds.award_add(
        guild_xid,
        values["count"],
        values["role"],
        values["message"],
        repeating=values["repeating"],
        remove=values["remove"],
        verified_only=values["verified_only"],
        unverified_only=values["unverified_only"],
    )
    return web.HTTPFound(f"/g/{guild_xid}")


@routes.post(r"/g/{guild}/awards/add")
@tracer.wrap(name="web", resource="award_add")
async def award_add_endpoint(request: web.Request) -> web.StreamResponse:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await award_add_impl(request)


async def award_update_impl(request: web.Request) -> web.Response:
    """Moderator-only: update one of the guild's awards, then redirect back to its page."""
    try:
        guild_xid = int(request.match_info["guild"])
        award_id = int(request.match_info["award"])
    except ValueError:
        return web.Response(status=404)
    if not await request_is_moderator(request, guild_xid):
        return web.Response(status=403, text="Forbidden")
    form = await request.post()
    values, error = parse_award_form(form)
    if values is None:
        assert error is not None
        return award_error_redirect(guild_xid, error)
    updated = await services.guilds.award_update(
        guild_xid,
        award_id,
        values["count"],
        values["role"],
        values["message"],
        repeating=values["repeating"],
        remove=values["remove"],
        verified_only=values["verified_only"],
        unverified_only=values["unverified_only"],
    )
    if updated is None:
        return web.Response(status=404)
    return web.HTTPFound(f"/g/{guild_xid}")


@routes.post(r"/g/{guild}/awards/{award}/update")
@tracer.wrap(name="web", resource="award_update")
async def award_update_endpoint(request: web.Request) -> web.StreamResponse:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await award_update_impl(request)


async def award_delete_impl(request: web.Request) -> web.Response:
    """Moderator-only: delete one of the guild's awards, then redirect back to its page."""
    try:
        guild_xid = int(request.match_info["guild"])
        award_id = int(request.match_info["award"])
    except ValueError:
        return web.Response(status=404)
    if not await request_is_moderator(request, guild_xid):
        return web.Response(status=403, text="Forbidden")
    if not await services.guilds.award_delete(guild_xid, award_id):
        return web.Response(status=404)
    return web.HTTPFound(f"/g/{guild_xid}")


@routes.post(r"/g/{guild}/awards/{award}/delete")
@tracer.wrap(name="web", resource="award_delete")
async def award_delete_endpoint(request: web.Request) -> web.StreamResponse:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await award_delete_impl(request)


async def channel_settings_impl(request: web.Request) -> web.Response:
    """Moderator-only: update a channel's settings, then redirect back to its page."""
    try:
        guild_xid = int(request.match_info["guild"])
        channel_xid = int(request.match_info["channel"])
    except ValueError:
        return web.Response(status=404)
    if not await request_is_moderator(request, guild_xid):
        return web.Response(status=403, text="Forbidden")
    form = await request.post()
    viewer_xid, viewer_name = await get_viewer(request)
    with audit.actor(viewer_xid, viewer_name, audit.SOURCE_WEB):
        await services.channels.update_settings(channel_xid, **parse_channel_settings(form))
    return web.HTTPFound(f"/g/{guild_xid}/c/{channel_xid}")


@routes.post(r"/g/{guild}/c/{channel}/settings")
@tracer.wrap(name="web", resource="channel_settings")
async def channel_settings_endpoint(request: web.Request) -> web.StreamResponse:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await channel_settings_impl(request)


async def channel_forget_impl(request: web.Request) -> web.Response:
    """Moderator-only: forget (delete) a channel's settings, then redirect to its guild page."""
    try:
        guild_xid = int(request.match_info["guild"])
        channel_xid = int(request.match_info["channel"])
    except ValueError:
        return web.Response(status=404)
    if not await request_is_moderator(request, guild_xid):
        return web.Response(status=403, text="Forbidden")
    viewer_xid, viewer_name = await get_viewer(request)
    with audit.actor(viewer_xid, viewer_name, audit.SOURCE_WEB):
        await services.channels.forget(channel_xid)
    return web.HTTPFound(f"/g/{guild_xid}")


@routes.post(r"/g/{guild}/c/{channel}/forget")
@tracer.wrap(name="web", resource="channel_forget")
async def channel_forget_endpoint(request: web.Request) -> web.StreamResponse:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await channel_forget_impl(request)


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
