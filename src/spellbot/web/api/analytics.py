from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import aiohttp_jinja2
import httpx
from aiohttp import web
from ddtrace.trace import tracer
from sqlalchemy import delete, select

from spellbot import services
from spellbot.database import DatabaseSession, db_session_manager
from spellbot.metrics import add_span_request_id, generate_request_id
from spellbot.models import Guild, GuildMember
from spellbot.settings import settings
from spellbot.utils import validate_signature

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


async def validate_analytics_request(
    request: web.Request,
) -> tuple[int, None] | tuple[None, web.Response]:
    """
    Validate guild_xid, expires, and signature.

    Returns (guild_xid, None) or (None, error_response).
    """
    try:
        guild_xid = int(request.match_info["guild"])
    except (KeyError, ValueError):
        return None, web.Response(status=404)

    if not settings.CHECK_SIGNATURE:
        return guild_xid, None

    try:
        expires = int(request.query["expires"])
        sig = request.query["sig"]
    except (KeyError, ValueError):
        return None, web.Response(status=403, text="Missing or invalid signature parameters.")

    if not validate_signature(guild_xid, expires, sig):
        return None, web.Response(status=403, text="Invalid or expired link.")

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
        data = await fetch_fn(guild_xid, all_time)

    return web.Response(
        status=200,
        content_type="application/json",
        text=json.dumps(data),
    )


@routes.get(r"/g/{guild}/analytics")
@tracer.wrap(name="web", resource="analytics")
async def analytics_endpoint(request: web.Request) -> web.Response:
    """Shell page endpoint - returns HTML immediately with loading spinner."""
    add_span_request_id(generate_request_id())
    try:
        guild_xid = int(request.match_info["guild"])
    except (KeyError, ValueError):
        return web.Response(status=404)

    try:
        expires = int(request.query["expires"])
        sig = request.query["sig"]
    except (KeyError, ValueError):
        return web.Response(status=403, text="Missing or invalid signature parameters.")

    if not validate_signature(guild_xid, expires, sig):
        return web.Response(status=403, text="Invalid or expired link.")

    async def get_guild_name() -> str | None:
        result = await DatabaseSession.execute(select(Guild).where(Guild.xid == guild_xid))  # type: ignore
        guild = result.scalar_one_or_none()
        return guild.name if guild else None

    async with db_session_manager():
        guild_name = await get_guild_name()

    if guild_name is None:
        return web.Response(status=404, text="Guild not found.")

    context = {"guild_xid": guild_xid, "guild_name": guild_name, "expires": expires, "sig": sig}
    return aiohttp_jinja2.render_template("analytics.html.j2", request, context)


@routes.get(r"/g/{guild}/analytics/summary")
@tracer.wrap(name="web", resource="analytics_summary")
async def analytics_summary_endpoint(request: web.Request) -> web.Response:
    """Return summary stats (fill rate, total games, unique players, etc.)."""
    add_span_request_id(generate_request_id())
    return await analytics_json_endpoint(
        request,
        lambda g, a: services.plays.analytics_summary(g, all_time=a),
    )


@routes.get(r"/g/{guild}/analytics/activity")
@tracer.wrap(name="web", resource="analytics_activity")
async def analytics_activity_endpoint(request: web.Request) -> web.Response:
    """Return daily activity data (games per day, expired, new users)."""
    add_span_request_id(generate_request_id())
    return await analytics_json_endpoint(
        request,
        lambda g, a: services.plays.analytics_activity(g, all_time=a),
    )


@routes.get(r"/g/{guild}/analytics/wait-time")
@tracer.wrap(name="web", resource="analytics_wait_time")
async def analytics_wait_time_endpoint(request: web.Request) -> web.Response:
    """Return average wait time per day data."""
    add_span_request_id(generate_request_id())
    return await analytics_json_endpoint(
        request,
        lambda g, a: services.plays.analytics_wait_time(g, all_time=a),
    )


@routes.get(r"/g/{guild}/analytics/brackets")
@tracer.wrap(name="web", resource="analytics_brackets")
async def analytics_brackets_endpoint(request: web.Request) -> web.Response:
    """Return games by bracket per day data."""
    add_span_request_id(generate_request_id())
    return await analytics_json_endpoint(
        request,
        lambda g, a: services.plays.analytics_brackets(g, all_time=a),
    )


@routes.get(r"/g/{guild}/analytics/retention")
@tracer.wrap(name="web", resource="analytics_retention")
async def analytics_retention_endpoint(request: web.Request) -> web.Response:
    """Return player retention data."""
    add_span_request_id(generate_request_id())
    return await analytics_json_endpoint(
        request,
        lambda g, a: services.plays.analytics_retention(g, all_time=a),
    )


@routes.get(r"/g/{guild}/analytics/growth")
@tracer.wrap(name="web", resource="analytics_growth")
async def analytics_growth_endpoint(request: web.Request) -> web.Response:
    """Return cumulative player growth data."""
    add_span_request_id(generate_request_id())
    return await analytics_json_endpoint(
        request,
        lambda g, a: services.plays.analytics_growth(g, all_time=a),
    )


@routes.get(r"/g/{guild}/analytics/histogram")
@tracer.wrap(name="web", resource="analytics_histogram")
async def analytics_histogram_endpoint(request: web.Request) -> web.Response:
    """Return games per player histogram data."""
    add_span_request_id(generate_request_id())
    return await analytics_json_endpoint(
        request,
        lambda g, a: services.plays.analytics_histogram(g, all_time=a),
    )


@routes.get(r"/g/{guild}/analytics/formats")
@tracer.wrap(name="web", resource="analytics_formats")
async def analytics_formats_endpoint(request: web.Request) -> web.Response:
    """Return popular formats data."""
    add_span_request_id(generate_request_id())
    return await analytics_json_endpoint(
        request,
        lambda g, a: services.plays.analytics_formats(g, all_time=a),
    )


@routes.get(r"/g/{guild}/analytics/channels")
@tracer.wrap(name="web", resource="analytics_channels")
async def analytics_channels_endpoint(request: web.Request) -> web.Response:
    """Return busiest channels data."""
    add_span_request_id(generate_request_id())
    return await analytics_json_endpoint(
        request,
        lambda g, a: services.plays.analytics_channels(g, all_time=a),
    )


@routes.get(r"/g/{guild}/analytics/channel-players")
@tracer.wrap(name="web", resource="analytics_channel_players")
async def analytics_channel_players_endpoint(request: web.Request) -> web.Response:
    """Return unique players per channel data."""
    add_span_request_id(generate_request_id())
    return await analytics_json_endpoint(
        request,
        lambda g, a: services.plays.analytics_channel_players(g, all_time=a),
    )


@routes.get(r"/g/{guild}/analytics/services")
@tracer.wrap(name="web", resource="analytics_services")
async def analytics_services_endpoint(request: web.Request) -> web.Response:
    """Return popular services data."""
    add_span_request_id(generate_request_id())
    return await analytics_json_endpoint(
        request,
        lambda g, a: services.plays.analytics_services(g, all_time=a),
    )


@routes.get(r"/g/{guild}/analytics/hour-of-day")
@tracer.wrap(name="web", resource="analytics_hour_of_day")
async def analytics_hour_of_day_endpoint(request: web.Request) -> web.Response:
    """Return games per hour of the day histogram."""
    add_span_request_id(generate_request_id())
    return await analytics_json_endpoint(
        request,
        lambda g, a: services.plays.analytics_hour_of_day(g, all_time=a),
    )


@routes.get(r"/g/{guild}/analytics/day-of-week")
@tracer.wrap(name="web", resource="analytics_day_of_week")
async def analytics_day_of_week_endpoint(request: web.Request) -> web.Response:
    """Return games per day of the week histogram."""
    add_span_request_id(generate_request_id())
    return await analytics_json_endpoint(
        request,
        lambda g, a: services.plays.analytics_day_of_week(g, all_time=a),
    )


@routes.get(r"/g/{guild}/analytics/rules")
@tracer.wrap(name="web", resource="analytics_rules")
async def analytics_rules_endpoint(request: web.Request) -> web.Response:
    """Return top rules and n-gram word cloud data."""
    add_span_request_id(generate_request_id())
    return await analytics_json_endpoint(
        request,
        lambda g, a: services.plays.analytics_rules(g, all_time=a),
    )


async def delete_guild_member(guild_xid: int, user_xid: int) -> None:
    """Delete a GuildMember record when the user is no longer in the guild."""
    await DatabaseSession.execute(
        delete(GuildMember).where(
            GuildMember.guild_xid == guild_xid,
            GuildMember.user_xid == user_xid,
        ),
    )


async def check_guild_member(guild_xid: int, user_xid: int) -> bool | None:
    """
    Check if a user is a member of a guild via the Discord REST API.

    Returns:
        True if the user is confirmed to be a member.
        False if the user is confirmed to NOT be a member (404 response).
        None if we couldn't determine membership status (errors, rate limits, etc).

    """
    headers = {"Authorization": f"Bot {settings.BOT_TOKEN}"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://discord.com/api/v10/guilds/{guild_xid}/members/{user_xid}",
                headers=headers,
            )
            if response.status_code == 200:
                return True
            if response.status_code == 404:
                return False
            # Any other status code (rate limit, server error, etc) - we can't be sure
            logger.warning(
                "check_guild_member unexpected status %s for %s/%s",
                response.status_code,
                guild_xid,
                user_xid,
            )
            return None
    except Exception as ex:
        logger.warning("check_guild_member failure for %s/%s: %s", guild_xid, user_xid, ex)
        return None


async def check_membership_and_update(
    guild_xid: int,
    players: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Check membership for each player and mark those who have left.

    Deletes GuildMember records for users who are confirmed to no longer be in the guild.
    Only marks users as left when we get a definitive 404 from Discord API.
    """
    results = []
    for player in players:
        user_xid = int(player["user_xid"])
        is_member = await check_guild_member(guild_xid, user_xid)
        player_copy = dict(player)
        if is_member is False:
            # Only mark as left when we get a definitive 404
            player_copy["left_server"] = True
            # Delete the stale GuildMember record
            await delete_guild_member(guild_xid, user_xid)
        else:
            # User is confirmed member (True) or status unknown (None)
            player_copy["left_server"] = False
        results.append(player_copy)
    return results


@routes.get(r"/g/{guild}/analytics/players")
@tracer.wrap(name="web", resource="analytics_players")
async def analytics_players_endpoint(request: web.Request) -> web.Response:
    """Return top players data with membership status."""
    add_span_request_id(generate_request_id())

    guild_xid, error = await validate_analytics_request(request)
    if error:
        return error
    assert guild_xid is not None

    period = request.query.get("period", "30d")
    all_time = period == "all"

    async with db_session_manager():
        if not await services.plays.guild_exists(guild_xid):
            return web.Response(status=404, text="Guild not found.")
        data = await services.plays.analytics_players(guild_xid, all_time=all_time)

        # Check membership status for each player
        if data.get("top_players"):
            data["top_players"] = await check_membership_and_update(
                guild_xid,
                data["top_players"],
            )

    return web.Response(
        status=200,
        content_type="application/json",
        text=json.dumps(data),
    )


@routes.get(r"/g/{guild}/analytics/blocked")
@tracer.wrap(name="web", resource="analytics_blocked")
async def analytics_blocked_endpoint(request: web.Request) -> web.Response:
    """Return top blocked players data with membership status."""
    add_span_request_id(generate_request_id())

    guild_xid, error = await validate_analytics_request(request)
    if error:
        return error
    assert guild_xid is not None

    period = request.query.get("period", "30d")
    all_time = period == "all"

    async with db_session_manager():
        if not await services.plays.guild_exists(guild_xid):
            return web.Response(status=404, text="Guild not found.")
        data = await services.plays.analytics_blocked(guild_xid, all_time=all_time)

        # Check membership status for each blocked user
        if data.get("top_blocked"):
            data["top_blocked"] = await check_membership_and_update(
                guild_xid,
                data["top_blocked"],
            )

    return web.Response(
        status=200,
        content_type="application/json",
        text=json.dumps(data),
    )
