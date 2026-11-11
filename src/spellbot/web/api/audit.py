# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING, Any

import aiohttp_jinja2
from aiohttp import web

from spellbot import audit, services
from spellbot.web.api.record import (
    bracket_choices,
    format_choices,
    require_moderator_page,
    service_choices,
)
from spellbot.web.tools import parse_page, route_id, web_endpoint

if TYPE_CHECKING:
    from datetime import datetime

routes = web.RouteTableDef()

# Settings fields whose stored integer value maps to a human label.
ENUM_LABELS: dict[str, dict[int, str]] = {
    "default_format": {c["value"]: c["label"] for c in format_choices()},
    "default_bracket": {c["value"]: c["label"] for c in bracket_choices()},
    "default_service": {c["value"]: c["label"] for c in service_choices()},
}

# A few nicer field labels; everything else is derived from the column name.
FIELD_LABELS = {"motd": "MOTD"}


def field_label(field: str) -> str:
    return FIELD_LABELS.get(field, field.replace("_", " ").capitalize())


def format_value(field: str, value: Any) -> str:
    if value is None or value == "":
        return "(empty)"
    if field in ENUM_LABELS:
        return ENUM_LABELS[field].get(value, str(value))
    if isinstance(value, bool):
        return "Enabled" if value else "Disabled"
    return str(value)


def millis(issued_at: datetime) -> int:
    return int(issued_at.replace(tzinfo=UTC).timestamp() * 1000)


def change_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten save events into one display row per changed field, newest first."""
    rows: list[dict[str, Any]] = []
    for event in events:
        who = event["actor_name"] or (
            str(event["actor_id"]) if event["actor_id"] is not None else "—"
        )
        when = millis(event["issued_at"])
        for field, new_value in event["changed_data"].items():
            rows.append(
                {
                    "when": when,
                    "who": who,
                    "source": event["source"] or "—",
                    "setting": field_label(field),
                    "old": format_value(field, event["old_data"].get(field)),
                    "new": format_value(field, new_value),
                },
            )
    return rows


async def impl(request: web.Request, *, is_channel: bool) -> web.StreamResponse:
    try:
        guild_xid = route_id(request, "guild")
        target_xid = route_id(request, "channel") if is_channel else guild_xid
    except ValueError:
        return web.Response(status=404)

    if denied := await require_moderator_page(request, guild_xid):
        return denied
    # Moderating `guild_xid` only grants access to that guild's own channels.
    if is_channel and not await services.channels.in_guild(guild_xid, target_xid):
        return web.Response(status=404)

    page = parse_page(request.query.get("page"))
    page_size = audit.SETTINGS_CHANGE_PAGE_SIZE
    table_name = "channels" if is_channel else "guilds"
    events, total = await audit.setting_changes(table_name, target_xid, page=page)

    back_url = f"/g/{guild_xid}/c/{target_xid}" if is_channel else f"/g/{guild_xid}"
    has_prev = page > 0
    has_next = (page + 1) * page_size < total
    context = {
        "scope": "channel" if is_channel else "server",
        "back_url": back_url,
        "rows": change_rows(events),
        "total": total,
        "has_prev": has_prev,
        "has_next": has_next,
        "prev_page": f"{request.path}?page={page - 1}" if has_prev else None,
        "next_page": f"{request.path}?page={page + 1}" if has_next else None,
    }
    return aiohttp_jinja2.render_template("audit.html.j2", request, context)


@routes.get(r"/g/{guild}/audit")
@web_endpoint("guild_audit")
async def guild_audit_endpoint(request: web.Request) -> web.StreamResponse:
    return await impl(request, is_channel=False)


@routes.get(r"/g/{guild}/c/{channel}/audit")
@web_endpoint("channel_audit")
async def channel_audit_endpoint(request: web.Request) -> web.StreamResponse:
    return await impl(request, is_channel=True)
