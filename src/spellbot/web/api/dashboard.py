# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import aiohttp_jinja2
from aiohttp import web
from aiohttp_session import get_session
from ddtrace.trace import tracer

from spellbot import services
from spellbot.database import db_session_manager
from spellbot.metrics import add_span_request_id, generate_request_id
from spellbot.services.filters import GuildFilter, PeriodSpec, parse_guild, parse_period
from spellbot.web.api.admin_auth import is_owner_session

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

routes = web.RouteTableDef()


@routes.get("/admin/dashboard")
@tracer.wrap(name="web", resource="dashboard")
async def dashboard_endpoint(request: web.Request) -> web.Response:
    """Render the dashboard shell page. Panels are populated by dashboard.js."""
    add_span_request_id(generate_request_id())
    session = await get_session(request)
    admin_name = session.get("name") or "admin"
    context = {"admin_name": admin_name, "is_owner": is_owner_session(session)}
    return aiohttp_jinja2.render_template("dashboard.html.j2", request, context)


@routes.post("/admin/dashboard/sql")
@tracer.wrap(name="web", resource="dashboard_sql")
async def dashboard_sql_endpoint(request: web.Request) -> web.Response:
    """Run an owner-only, read-only ad-hoc SQL query and return the rows as JSON."""
    add_span_request_id(generate_request_id())
    session = await get_session(request)
    if not is_owner_session(session):
        return web.json_response({"error": "Forbidden"}, status=403)
    try:
        payload = await request.json()
    except ValueError:  # includes json.JSONDecodeError
        return web.json_response({"error": "Invalid JSON body."}, status=400)
    query = payload.get("query") if isinstance(payload, dict) else None
    if not isinstance(query, str):
        return web.json_response({"error": "Missing 'query' string."}, status=400)
    # `dashboard_run_sql` opens its own dedicated read-only connection, so no
    # surrounding `db_session_manager()` is needed here.
    data = await services.dashboard.dashboard_run_sql(query)
    return web.json_response(data, status=400 if "error" in data else 200)


def dashboard_query(request: web.Request) -> tuple[PeriodSpec, GuildFilter]:
    """Parse the shared `period` and `guild` query parameters."""
    return parse_period(request.query.get("period")), parse_guild(request.query.get("guild"))


async def dashboard_json_endpoint(
    request: web.Request,
    fetch_fn: Callable[[PeriodSpec, GuildFilter], Awaitable[dict[str, Any]]],
) -> web.Response:
    """Run `fetch_fn` inside a DB session and return its result as JSON."""
    period, opts = dashboard_query(request)
    async with db_session_manager():
        return web.json_response(await fetch_fn(period, opts))


# Panels served as JSON straight from a `services.dashboard` function. The slug `x-y` is served
# at `/admin/dashboard/x-y` by `dashboard_x_y`, and traced as the `dashboard_x_y` resource.
JSON_PANELS = (
    "summary",
    "totals",
    "users-activity",
    "games",
    "player-growth",
    "casual-vs-cedh",
    "server-popularity",
    "service-popularity",
    "bracket-adoption",
    "user-languages",
    "game-languages",
    "top-guild-per-service",
    "top-guild-per-game-language",
    "guild-languages",
    "hour-of-day",
    "day-of-week",
    "popular-formats",
    "popular-seats",
    "top-players",
    "top-blocked",
    "avg-wait-time",
    "games-per-player",
    "rules",
    "cohort-retention",
    "activity-heatmap",
    "wait-time-distribution",
    "voice-adoption",
    "blind-adoption",
    "to-mode-adoption",
    "competitive-adoption",
    "playgroup-adoption",
    "castlog-adoption",
    "war-usage",
    "mythic-verification",
    "queue-depth",
    "active-queues",
)


def add_json_panel(slug: str) -> None:
    """Serve the JSON panel `slug`, looking its service function up on each request."""
    name = f"dashboard_{slug.replace('-', '_')}"

    async def endpoint(request: web.Request) -> web.Response:
        add_span_request_id(generate_request_id())
        return await dashboard_json_endpoint(request, getattr(services.dashboard, name))

    endpoint.__name__ = f"{name}_endpoint"
    routes.get(f"/admin/dashboard/{slug}")(tracer.wrap(name="web", resource=name)(endpoint))


for json_panel in JSON_PANELS:
    add_json_panel(json_panel)


@routes.get("/admin/dashboard/guilds")
@tracer.wrap(name="web", resource="dashboard_guilds")
async def dashboard_guilds_endpoint(request: web.Request) -> web.Response:
    """Return all known guilds for the dashboard's filter dropdown."""
    add_span_request_id(generate_request_id())
    del request
    async with db_session_manager():
        return web.json_response({"guilds": await services.dashboard.dashboard_guilds()})
