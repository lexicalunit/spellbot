from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING, Any

import aiohttp_jinja2
from aiohttp import web

from spellbot import audit
from spellbot.database import db_session_manager
from spellbot.metrics import add_span_request_id, generate_request_id
from spellbot.web.api.record import (
    bracket_choices,
    format_choices,
    login_url,
    service_choices,
    viewer_access,
)

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


def _change_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def parse_page(request: web.Request) -> int:
    try:
        return max(int(request.query.get("page", "0")), 0)
    except ValueError:
        return 0


async def impl(request: web.Request, *, is_channel: bool) -> web.StreamResponse:
    try:
        guild_xid = int(request.match_info["guild"])
        target_xid = int(request.match_info["channel"]) if is_channel else guild_xid
    except ValueError:
        return web.Response(status=404)

    is_logged_in, is_moderator = await viewer_access(request, guild_xid)
    if not is_logged_in:
        return web.HTTPFound(login_url(request))
    if not is_moderator:
        return web.Response(status=403, text="Forbidden")

    page = parse_page(request)
    page_size = audit.SETTINGS_CHANGE_PAGE_SIZE
    table_name = "channels" if is_channel else "guilds"
    events, total = await audit.setting_changes(table_name, target_xid, page=page)

    back_url = f"/g/{guild_xid}/c/{target_xid}" if is_channel else f"/g/{guild_xid}"
    has_prev = page > 0
    has_next = (page + 1) * page_size < total
    context = {
        "scope": "channel" if is_channel else "server",
        "back_url": back_url,
        "rows": _change_rows(events),
        "total": total,
        "has_prev": has_prev,
        "has_next": has_next,
        "prev_page": f"{request.path}?page={page - 1}" if has_prev else None,
        "next_page": f"{request.path}?page={page + 1}" if has_next else None,
    }
    return aiohttp_jinja2.render_template("audit.html.j2", request, context)


@routes.get(r"/g/{guild}/audit")
async def guild_audit_endpoint(request: web.Request) -> web.StreamResponse:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await impl(request, is_channel=False)


@routes.get(r"/g/{guild}/c/{channel}/audit")
async def channel_audit_endpoint(request: web.Request) -> web.StreamResponse:
    add_span_request_id(generate_request_id())
    async with db_session_manager():
        return await impl(request, is_channel=True)
