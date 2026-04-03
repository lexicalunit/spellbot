from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import aiohttp_jinja2
import httpx
from aiohttp.web_response import Response as WebResponse
from asgiref.sync import sync_to_async
from ddtrace.trace import tracer

from spellbot.database import DatabaseSession, db_session_manager
from spellbot.metrics import add_span_request_id, generate_request_id
from spellbot.models import Guild, GuildMember
from spellbot.services import ServicesRegistry
from spellbot.settings import settings
from spellbot.utils import validate_signature

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from aiohttp import web

    from spellbot.services.plays import PlaysService

logger = logging.getLogger(__name__)


async def _validate_analytics_request(
    request: web.Request,
) -> tuple[int, None] | tuple[None, WebResponse]:
    """
    Validate guild_xid, expires, and signature.

    Returns (guild_xid, None) or (None, error_response).
    """
    try:
        guild_xid = int(request.match_info["guild"])
    except (KeyError, ValueError):
        return None, WebResponse(status=404)

    if not settings.CHECK_SIGNATURE:
        return guild_xid, None

    try:
        expires = int(request.query["expires"])
        sig = request.query["sig"]
    except (KeyError, ValueError):
        return None, WebResponse(status=403, text="Missing or invalid signature parameters.")

    if not validate_signature(guild_xid, expires, sig):
        return None, WebResponse(status=403, text="Invalid or expired link.")

    return guild_xid, None


async def _analytics_json_endpoint(
    request: web.Request,
    fetch_fn: Callable[[PlaysService, int, bool], Awaitable[dict[str, Any]]],
) -> WebResponse:
    """Return analytics JSON data using the provided fetch function."""
    guild_xid, error = await _validate_analytics_request(request)
    if error:
        return error
    assert guild_xid is not None

    # Check for period query parameter (default: 30d)
    period = request.query.get("period", "30d")
    all_time = period == "all"

    async with db_session_manager():
        services = ServicesRegistry()
        if not await services.plays.guild_exists(guild_xid):
            return WebResponse(status=404, text="Guild not found.")
        data = await fetch_fn(services.plays, guild_xid, all_time)

    return WebResponse(
        status=200,
        content_type="application/json",
        text=json.dumps(data),
    )


@tracer.wrap(name="web", resource="analytics")
async def analytics_endpoint(request: web.Request) -> WebResponse:
    """Shell page endpoint - returns HTML immediately with loading spinner."""
    add_span_request_id(generate_request_id())
    try:
        guild_xid = int(request.match_info["guild"])
    except (KeyError, ValueError):
        return WebResponse(status=404)

    try:
        expires = int(request.query["expires"])
        sig = request.query["sig"]
    except (KeyError, ValueError):
        return WebResponse(status=403, text="Missing or invalid signature parameters.")

    if not validate_signature(guild_xid, expires, sig):
        return WebResponse(status=403, text="Invalid or expired link.")

    @sync_to_async()
    def get_guild_name() -> str | None:
        guild = DatabaseSession.query(Guild).filter(Guild.xid == guild_xid).one_or_none()
        return guild.name if guild else None

    async with db_session_manager():
        guild_name = await get_guild_name()

    if guild_name is None:
        return WebResponse(status=404, text="Guild not found.")

    context = {"guild_xid": guild_xid, "guild_name": guild_name, "expires": expires, "sig": sig}
    return aiohttp_jinja2.render_template("analytics.html.j2", request, context)


@tracer.wrap(name="web", resource="analytics_summary")
async def analytics_summary_endpoint(request: web.Request) -> WebResponse:
    """Return summary stats (fill rate, total games, unique players, etc.)."""
    add_span_request_id(generate_request_id())
    return await _analytics_json_endpoint(
        request,
        lambda p, g, a: p.analytics_summary(g, all_time=a),
    )


@tracer.wrap(name="web", resource="analytics_activity")
async def analytics_activity_endpoint(request: web.Request) -> WebResponse:
    """Return daily activity data (games per day, expired, new users)."""
    add_span_request_id(generate_request_id())
    return await _analytics_json_endpoint(
        request,
        lambda p, g, a: p.analytics_activity(g, all_time=a),
    )


@tracer.wrap(name="web", resource="analytics_wait_time")
async def analytics_wait_time_endpoint(request: web.Request) -> WebResponse:
    """Return average wait time per day data."""
    add_span_request_id(generate_request_id())
    return await _analytics_json_endpoint(
        request,
        lambda p, g, a: p.analytics_wait_time(g, all_time=a),
    )


@tracer.wrap(name="web", resource="analytics_brackets")
async def analytics_brackets_endpoint(request: web.Request) -> WebResponse:
    """Return games by bracket per day data."""
    add_span_request_id(generate_request_id())
    return await _analytics_json_endpoint(
        request,
        lambda p, g, a: p.analytics_brackets(g, all_time=a),
    )


@tracer.wrap(name="web", resource="analytics_retention")
async def analytics_retention_endpoint(request: web.Request) -> WebResponse:
    """Return player retention data."""
    add_span_request_id(generate_request_id())
    return await _analytics_json_endpoint(
        request,
        lambda p, g, a: p.analytics_retention(g, all_time=a),
    )


@tracer.wrap(name="web", resource="analytics_growth")
async def analytics_growth_endpoint(request: web.Request) -> WebResponse:
    """Return cumulative player growth data."""
    add_span_request_id(generate_request_id())
    return await _analytics_json_endpoint(
        request,
        lambda p, g, a: p.analytics_growth(g, all_time=a),
    )


@tracer.wrap(name="web", resource="analytics_histogram")
async def analytics_histogram_endpoint(request: web.Request) -> WebResponse:
    """Return games per player histogram data."""
    add_span_request_id(generate_request_id())
    return await _analytics_json_endpoint(
        request,
        lambda p, g, a: p.analytics_histogram(g, all_time=a),
    )


@tracer.wrap(name="web", resource="analytics_formats")
async def analytics_formats_endpoint(request: web.Request) -> WebResponse:
    """Return popular formats data."""
    add_span_request_id(generate_request_id())
    return await _analytics_json_endpoint(
        request,
        lambda p, g, a: p.analytics_formats(g, all_time=a),
    )


@tracer.wrap(name="web", resource="analytics_channels")
async def analytics_channels_endpoint(request: web.Request) -> WebResponse:
    """Return busiest channels data."""
    add_span_request_id(generate_request_id())
    return await _analytics_json_endpoint(
        request,
        lambda p, g, a: p.analytics_channels(g, all_time=a),
    )


@tracer.wrap(name="web", resource="analytics_services")
async def analytics_services_endpoint(request: web.Request) -> WebResponse:
    """Return popular services data."""
    add_span_request_id(generate_request_id())
    return await _analytics_json_endpoint(
        request,
        lambda p, g, a: p.analytics_services(g, all_time=a),
    )


@sync_to_async()
def _delete_guild_member(guild_xid: int, user_xid: int) -> None:
    """Delete a GuildMember record when the user is no longer in the guild."""
    DatabaseSession.query(GuildMember).filter(
        GuildMember.guild_xid == guild_xid,
        GuildMember.user_xid == user_xid,
    ).delete()


async def _check_guild_member(guild_xid: int, user_xid: int) -> bool | None:
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


async def _check_membership_and_update(
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
        is_member = await _check_guild_member(guild_xid, user_xid)
        player_copy = dict(player)
        if is_member is False:
            # Only mark as left when we get a definitive 404
            player_copy["left_server"] = True
            # Delete the stale GuildMember record
            await _delete_guild_member(guild_xid, user_xid)
        else:
            # User is confirmed member (True) or status unknown (None)
            player_copy["left_server"] = False
        results.append(player_copy)
    return results


@tracer.wrap(name="web", resource="analytics_players")
async def analytics_players_endpoint(request: web.Request) -> WebResponse:
    """Return top players data with membership status."""
    add_span_request_id(generate_request_id())

    guild_xid, error = await _validate_analytics_request(request)
    if error:
        return error
    assert guild_xid is not None

    period = request.query.get("period", "30d")
    all_time = period == "all"

    async with db_session_manager():
        services = ServicesRegistry()
        if not await services.plays.guild_exists(guild_xid):
            return WebResponse(status=404, text="Guild not found.")
        data = await services.plays.analytics_players(guild_xid, all_time=all_time)

        # Check membership status for each player
        if data.get("top_players"):
            data["top_players"] = await _check_membership_and_update(
                guild_xid,
                data["top_players"],
            )

    return WebResponse(
        status=200,
        content_type="application/json",
        text=json.dumps(data),
    )


@tracer.wrap(name="web", resource="analytics_blocked")
async def analytics_blocked_endpoint(request: web.Request) -> WebResponse:
    """Return top blocked players data with membership status."""
    add_span_request_id(generate_request_id())

    guild_xid, error = await _validate_analytics_request(request)
    if error:
        return error
    assert guild_xid is not None

    period = request.query.get("period", "30d")
    all_time = period == "all"

    async with db_session_manager():
        services = ServicesRegistry()
        if not await services.plays.guild_exists(guild_xid):
            return WebResponse(status=404, text="Guild not found.")
        data = await services.plays.analytics_blocked(guild_xid, all_time=all_time)

        # Check membership status for each blocked user
        if data.get("top_blocked"):
            data["top_blocked"] = await _check_membership_and_update(
                guild_xid,
                data["top_blocked"],
            )

    return WebResponse(
        status=200,
        content_type="application/json",
        text=json.dumps(data),
    )
