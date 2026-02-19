from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import aiohttp_jinja2
from aiohttp.web_response import Response as WebResponse
from asgiref.sync import sync_to_async

from spellbot.database import DatabaseSession, db_session_manager
from spellbot.models import Guild
from spellbot.services import ServicesRegistry
from spellbot.utils import validate_signature

if TYPE_CHECKING:
    from aiohttp import web

logger = logging.getLogger(__name__)


async def analytics_endpoint(request: web.Request) -> WebResponse:
    """Shell page endpoint - returns HTML immediately with loading spinner."""
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


async def analytics_data_endpoint(request: web.Request) -> WebResponse:
    """Return JSON with all analytics data."""
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

    async with db_session_manager():
        services = ServicesRegistry()
        data = await services.plays.guild_analytics(guild_xid)

    if data is None:
        return WebResponse(status=404, text="Guild not found.")

    return WebResponse(
        status=200,
        content_type="application/json",
        text=json.dumps(data),
    )
