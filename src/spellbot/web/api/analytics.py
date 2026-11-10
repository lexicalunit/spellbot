# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import aiohttp_jinja2
import httpx
from aiohttp import web
from ddtrace.trace import tracer
from sqlalchemy import delete, select, update

from spellbot import services
from spellbot.database import DatabaseSession, db_session_manager
from spellbot.models import Guild, GuildMember
from spellbot.settings import settings
from spellbot.web.api.record import moderated_route, request_is_moderator, require_moderator_page
from spellbot.web.signing import generate_signed_url, validate_signature
from spellbot.web.tools import route_id, tag_web_request

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

# How long a "Share this page" pre-signed link stays valid.
SHARE_LINK_EXPIRE_MINUTES = 15

# How long a membership Discord confirmed is trusted before asking again. Long on purpose:
# this only decides a "left the server" badge on an analytics page, so an answer a few days
# stale costs nothing, while asking Discord per player per page load costs rate limiting.
MEMBERSHIP_TTL = timedelta(days=7)

# These calls use the bot token, so a slow one holds a request open while spending the same
# Discord budget the bot needs. Give up quickly rather than queue behind Discord.
MEMBERSHIP_TIMEOUT_S = 5.0

# Discord's "you are asking too often" status.
RATE_LIMITED_STATUS = 429


def has_valid_signature(request: web.Request, guild_xid: int) -> bool:
    """Return True when the request carries a valid, unexpired HMAC signature."""
    try:
        expires = int(request.query["expires"])
        sig = request.query["sig"]
    except KeyError, ValueError:
        return False
    return validate_signature(guild_xid, expires, sig)


async def analytics_access_granted(request: web.Request, guild_xid: int) -> bool:
    """
    Return True when the request may view analytics for `guild_xid`.

    Access is granted to a valid signed (shared) link or to a logged-in moderator of
    the guild, mirroring how guild settings access is gated.
    """
    if not settings.CHECK_SIGNATURE:
        return True
    if has_valid_signature(request, guild_xid):
        return True
    return await request_is_moderator(request, guild_xid)


async def validate_analytics_request(
    request: web.Request,
) -> tuple[int, None] | tuple[None, web.Response]:
    """
    Validate access to analytics data for a guild.

    Returns (guild_xid, None) or (None, error_response).
    """
    try:
        guild_xid = route_id(request, "guild")
    except KeyError, ValueError:
        return None, web.Response(status=404)

    if not await analytics_access_granted(request, guild_xid):
        return None, web.Response(status=403, text="Forbidden")

    return guild_xid, None


async def analytics_json_endpoint(
    request: web.Request,
    fetch_fn: Callable[[int, bool], Awaitable[dict[str, Any]]],
) -> web.Response:
    """Return analytics JSON data using the provided fetch function."""
    guild_xid, error = await validate_analytics_request(request)
    if error:
        return error
    assert guild_xid is not None

    # Check for period query parameter (default: 30d)
    period = request.query.get("period", "30d")
    all_time = period == "all"

    async with db_session_manager():
        if not await services.plays.guild_exists(guild_xid):
            return web.Response(status=404, text="Guild not found.")
        return web.json_response(await fetch_fn(guild_xid, all_time))


@routes.get(r"/g/{guild}/analytics")
@tracer.wrap(name="web", resource="analytics")
async def analytics_endpoint(request: web.Request) -> web.StreamResponse:
    """Shell page endpoint - returns HTML immediately with loading spinner."""
    tag_web_request(request)
    try:
        guild_xid = route_id(request, "guild")
    except KeyError, ValueError:
        return web.Response(status=404)

    # A valid signed link grants a "shared" view (e.g. a logged-out recipient); otherwise
    # require a logged-in moderator session, the same gate used for guild settings.
    is_shared = settings.CHECK_SIGNATURE and has_valid_signature(request, guild_xid)
    if (
        not is_shared
        and settings.CHECK_SIGNATURE
        and (denied := await require_moderator_page(request, guild_xid))
    ):
        return denied

    async def get_guild_name() -> str | None:
        result = await DatabaseSession.execute(select(Guild).where(Guild.xid == guild_xid))
        guild = result.scalar_one_or_none()
        return guild.name if guild else None

    async with db_session_manager():
        guild_name = await get_guild_name()

    if guild_name is None:
        return web.Response(status=404, text="Guild not found.")

    context = {
        "guild_xid": guild_xid,
        "guild_name": guild_name,
        "is_shared": is_shared,
        "expires": request.query.get("expires") if is_shared else None,
        "sig": request.query.get("sig") if is_shared else None,
    }
    return aiohttp_jinja2.render_template("analytics.html.j2", request, context)


@routes.get(r"/g/{guild}/analytics/share")
@tracer.wrap(name="web", resource="analytics_share")
async def analytics_share_endpoint(request: web.Request) -> web.Response:
    """Moderator-only: mint a fresh pre-signed shareable analytics link."""
    tag_web_request(request)
    ids = await moderated_route(request)
    if isinstance(ids, web.Response):
        return ids
    (guild_xid,) = ids

    async with db_session_manager():
        if not await services.plays.guild_exists(guild_xid):
            return web.Response(status=404, text="Guild not found.")

    url = generate_signed_url(guild_xid, expires_in_minutes=SHARE_LINK_EXPIRE_MINUTES)
    return web.json_response({"url": url})


# Panels served as JSON straight from a `services.analytics` function. The slug `x-y` is served
# at `/g/{guild}/analytics/x-y` by `analytics_x_y`, and traced as the `analytics_x_y` resource.
JSON_PANELS = (
    "summary",
    "activity",
    "wait-time",
    "brackets",
    "retention",
    "growth",
    "histogram",
    "formats",
    "languages",
    "channels",
    "channel-players",
    "services",
    "hour-of-day",
    "day-of-week",
    "rules",
)


def add_json_panel(slug: str) -> None:
    """Serve the JSON panel `slug`, looking its service function up on each request."""
    name = f"analytics_{slug.replace('-', '_')}"

    async def endpoint(request: web.Request) -> web.Response:
        tag_web_request(request)
        return await analytics_json_endpoint(
            request,
            lambda guild_xid, all_time: getattr(services.analytics, name)(
                guild_xid,
                all_time=all_time,
            ),
        )

    endpoint.__name__ = f"{name}_endpoint"
    routes.get(rf"/g/{{guild}}/analytics/{slug}")(tracer.wrap(name="web", resource=name)(endpoint))


for json_panel in JSON_PANELS:
    add_json_panel(json_panel)


async def delete_guild_member(guild_xid: int, user_xid: int) -> None:
    """Delete a GuildMember record when the user is no longer in the guild."""
    await DatabaseSession.execute(
        delete(GuildMember).where(
            GuildMember.guild_xid == guild_xid,
            GuildMember.user_xid == user_xid,
        ),
    )


class Membership(StrEnum):
    """What one Discord membership check concluded."""

    MEMBER = "member"
    LEFT = "left"
    UNKNOWN = "unknown"
    RATE_LIMITED = "rate_limited"


async def recently_checked_members(guild_xid: int, user_xids: list[int]) -> set[int]:
    """Return the xids among `user_xids` whose membership Discord confirmed recently."""
    cutoff = datetime.now(UTC).replace(tzinfo=None) - MEMBERSHIP_TTL
    rows = await DatabaseSession.execute(
        select(GuildMember.user_xid).where(
            GuildMember.guild_xid == guild_xid,
            GuildMember.user_xid.in_(user_xids),
            GuildMember.membership_checked_at.is_not(None),
            GuildMember.membership_checked_at >= cutoff,
        ),
    )
    return {row[0] for row in rows}


async def mark_membership_checked(guild_xid: int, user_xid: int) -> None:
    """Record that Discord confirmed this membership just now, starting a fresh TTL."""
    await DatabaseSession.execute(
        update(GuildMember)
        .where(
            GuildMember.guild_xid == guild_xid,
            GuildMember.user_xid == user_xid,
        )
        .values(membership_checked_at=datetime.now(UTC).replace(tzinfo=None)),
    )


async def check_guild_member(
    client: httpx.AsyncClient,
    guild_xid: int,
    user_xid: int,
) -> Membership:
    """Ask Discord whether a user is still a member of a guild."""
    headers = {"Authorization": f"Bot {settings.BOT_TOKEN}"}
    try:
        response = await client.get(
            f"https://discord.com/api/v10/guilds/{guild_xid}/members/{user_xid}",
            headers=headers,
        )
    except Exception as ex:
        logger.warning("check_guild_member failure for %s/%s: %s", guild_xid, user_xid, ex)
        return Membership.UNKNOWN
    if response.status_code == 200:
        return Membership.MEMBER
    if response.status_code == 404:
        return Membership.LEFT
    if response.status_code == RATE_LIMITED_STATUS:
        logger.warning("check_guild_member rate limited for %s/%s", guild_xid, user_xid)
        return Membership.RATE_LIMITED
    logger.warning(
        "check_guild_member unexpected status %s for %s/%s",
        response.status_code,
        guild_xid,
        user_xid,
    )
    return Membership.UNKNOWN


async def check_membership_and_update(
    guild_xid: int,
    players: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Mark the players who have left the guild, asking Discord only about the stale ones.

    A membership Discord confirmed within `MEMBERSHIP_TTL` is reused instead of asked about
    again, so repeatedly loading an analytics page costs no Discord calls at all. That
    staleness is harmless here - it only decides a "left the server" badge - and asking per
    player per page load is what made this page a source of rate limiting.

    Deletes `GuildMember` records for users Discord definitively reports a 404 for. Anything
    less than a 404 leaves the record alone, since an error is not evidence of leaving.
    """
    user_xids = [int(player["user_xid"]) for player in players]
    fresh = await recently_checked_members(guild_xid, user_xids)

    results: list[dict[str, Any]] = []
    # Once Discord starts refusing, stop asking for the rest of this request. 429s count
    # toward an invalid request budget for the whole bot token, so continuing to ask after
    # the first refusal is how a slow page turns into a banned token.
    rate_limited = False
    async with httpx.AsyncClient(timeout=MEMBERSHIP_TIMEOUT_S) as client:
        for player in players:
            user_xid = int(player["user_xid"])
            player_copy = dict(player)
            player_copy["left_server"] = False
            if user_xid in fresh or rate_limited:
                results.append(player_copy)
                continue
            membership = await check_guild_member(client, guild_xid, user_xid)
            if membership is Membership.LEFT:
                player_copy["left_server"] = True
                await delete_guild_member(guild_xid, user_xid)
            elif membership is Membership.MEMBER:
                await mark_membership_checked(guild_xid, user_xid)
            elif membership is Membership.RATE_LIMITED:
                rate_limited = True
            results.append(player_copy)
    return results


def with_membership(name: str, key: str) -> Callable[[int, bool], Awaitable[dict[str, Any]]]:
    """Fetch `services.analytics.<name>`, then mark which of its `key` players left the guild."""

    async def fetch(guild_xid: int, all_time: bool) -> dict[str, Any]:
        data = await getattr(services.analytics, name)(guild_xid, all_time=all_time)
        if data.get(key):
            data[key] = await check_membership_and_update(guild_xid, data[key])
        return data

    return fetch


@routes.get(r"/g/{guild}/analytics/players")
@tracer.wrap(name="web", resource="analytics_players")
async def analytics_players_endpoint(request: web.Request) -> web.Response:
    """Return top players data with membership status."""
    tag_web_request(request)
    return await analytics_json_endpoint(
        request,
        with_membership("analytics_players", "top_players"),
    )


@routes.get(r"/g/{guild}/analytics/blocked")
@tracer.wrap(name="web", resource="analytics_blocked")
async def analytics_blocked_endpoint(request: web.Request) -> web.Response:
    """Return top blocked players data with membership status."""
    tag_web_request(request)
    return await analytics_json_endpoint(
        request,
        with_membership("analytics_blocked", "top_blocked"),
    )
