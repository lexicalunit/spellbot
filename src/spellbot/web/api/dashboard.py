from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import aiohttp_jinja2
from aiohttp import web
from aiohttp_session import get_session
from ddtrace.trace import tracer

from spellbot import services
from spellbot.database import db_session_manager
from spellbot.metrics import add_span_request_id, generate_request_id
from spellbot.web.dashboard_filters import GuildFilter, PeriodSpec, parse_guild, parse_period

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
    context = {"admin_name": admin_name}
    return aiohttp_jinja2.render_template("dashboard.html.j2", request, context)


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
        data = await fetch_fn(period, opts)
    return web.Response(
        status=200,
        content_type="application/json",
        text=json.dumps(data),
    )


@routes.get("/admin/dashboard/summary")
@tracer.wrap(name="web", resource="dashboard_summary")
async def dashboard_summary_endpoint(request: web.Request) -> web.Response:
    """Return headline totals for the dashboard (games, players, servers)."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_summary)


@routes.get("/admin/dashboard/totals")
@tracer.wrap(name="web", resource="dashboard_totals")
async def dashboard_totals_endpoint(request: web.Request) -> web.Response:
    """Return all-time totals (games, players, servers) ignoring the date range."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_totals)


@routes.get("/admin/dashboard/users-activity")
@tracer.wrap(name="web", resource="dashboard_users_activity")
async def dashboard_users_activity_endpoint(request: web.Request) -> web.Response:
    """Return user activity series (new users, DAU/WAU/MAU, DAU:MAU)."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_users_activity)


@routes.get("/admin/dashboard/games")
@tracer.wrap(name="web", resource="dashboard_games")
async def dashboard_games_endpoint(request: web.Request) -> web.Response:
    """Return bucketed counts of started and expired games."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_games)


@routes.get("/admin/dashboard/player-growth")
@tracer.wrap(name="web", resource="dashboard_player_growth")
async def dashboard_player_growth_endpoint(request: web.Request) -> web.Response:
    """Return cumulative unique-player counts bucketed at `period.bucket`."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_player_growth)


@routes.get("/admin/dashboard/casual-vs-cedh")
@tracer.wrap(name="web", resource="dashboard_casual_vs_cedh")
async def dashboard_casual_vs_cedh_endpoint(request: web.Request) -> web.Response:
    """Return bucketed counts of started games classified as Casual vs cEDH."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_casual_vs_cedh)


@routes.get("/admin/dashboard/server-popularity")
@tracer.wrap(name="web", resource="dashboard_server_popularity")
async def dashboard_server_popularity_endpoint(request: web.Request) -> web.Response:
    """Return bucketed game counts for the top guilds by total games."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_server_popularity)


@routes.get("/admin/dashboard/service-popularity")
@tracer.wrap(name="web", resource="dashboard_service_popularity")
async def dashboard_service_popularity_endpoint(request: web.Request) -> web.Response:
    """Return bucketed game counts grouped by game service."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_service_popularity)


@routes.get("/admin/dashboard/bracket-adoption")
@tracer.wrap(name="web", resource="dashboard_bracket_adoption")
async def dashboard_bracket_adoption_endpoint(request: web.Request) -> web.Response:
    """Return bucketed bracket adoption rate among bracketable formats."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_bracket_adoption)


@routes.get("/admin/dashboard/user-languages")
@tracer.wrap(name="web", resource="dashboard_user_languages")
async def dashboard_user_languages_endpoint(request: web.Request) -> web.Response:
    """Return distinct active-user counts grouped by user locale."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_user_languages)


@routes.get("/admin/dashboard/game-languages")
@tracer.wrap(name="web", resource="dashboard_game_languages")
async def dashboard_game_languages_endpoint(request: web.Request) -> web.Response:
    """Return counts of started games grouped by game locale."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_game_languages)


@routes.get("/admin/dashboard/top-guild-per-game-language")
@tracer.wrap(name="web", resource="dashboard_top_guild_per_game_language")
async def dashboard_top_guild_per_game_language_endpoint(request: web.Request) -> web.Response:
    """Return the most active guild for each distinct game locale."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(
        request,
        services.dashboard.dashboard_top_guild_per_game_language,
    )


@routes.get("/admin/dashboard/guild-languages")
@tracer.wrap(name="web", resource="dashboard_guild_languages")
async def dashboard_guild_languages_endpoint(request: web.Request) -> web.Response:
    """Return counts of distinct active guilds grouped by guild locale."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_guild_languages)


@routes.get("/admin/dashboard/hour-of-day")
@tracer.wrap(name="web", resource="dashboard_hour_of_day")
async def dashboard_hour_of_day_endpoint(request: web.Request) -> web.Response:
    """Return counts of started games per UTC hour of the day (0-23)."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_hour_of_day)


@routes.get("/admin/dashboard/day-of-week")
@tracer.wrap(name="web", resource="dashboard_day_of_week")
async def dashboard_day_of_week_endpoint(request: web.Request) -> web.Response:
    """Return counts of started games per UTC day of the week (0=Sun..6=Sat)."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_day_of_week)


@routes.get("/admin/dashboard/popular-formats")
@tracer.wrap(name="web", resource="dashboard_popular_formats")
async def dashboard_popular_formats_endpoint(request: web.Request) -> web.Response:
    """Return counts of started games grouped by format."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_popular_formats)


@routes.get("/admin/dashboard/popular-seats")
@tracer.wrap(name="web", resource="dashboard_popular_seats")
async def dashboard_popular_seats_endpoint(request: web.Request) -> web.Response:
    """Return counts of started games grouped by seat count."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_popular_seats)


@routes.get("/admin/dashboard/top-players")
@tracer.wrap(name="web", resource="dashboard_top_players")
async def dashboard_top_players_endpoint(request: web.Request) -> web.Response:
    """Return the top players by number of started games played."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_top_players)


@routes.get("/admin/dashboard/top-blocked")
@tracer.wrap(name="web", resource="dashboard_top_blocked")
async def dashboard_top_blocked_endpoint(request: web.Request) -> web.Response:
    """Return the top blocked users globally."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_top_blocked)


@routes.get("/admin/dashboard/avg-wait-time")
@tracer.wrap(name="web", resource="dashboard_avg_wait_time")
async def dashboard_avg_wait_time_endpoint(request: web.Request) -> web.Response:
    """Return the average wait time (in minutes) between game creation and start."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_avg_wait_time)


@routes.get("/admin/dashboard/games-per-player")
@tracer.wrap(name="web", resource="dashboard_games_per_player")
async def dashboard_games_per_player_endpoint(request: web.Request) -> web.Response:
    """Return the games-per-player histogram with the median."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_games_per_player)


@routes.get("/admin/dashboard/rules")
@tracer.wrap(name="web", resource="dashboard_rules")
async def dashboard_rules_endpoint(request: web.Request) -> web.Response:
    """Return the top game rules and rule n-grams for a word cloud."""
    add_span_request_id(generate_request_id())
    return await dashboard_json_endpoint(request, services.dashboard.dashboard_rules)


@routes.get("/admin/dashboard/guilds")
@tracer.wrap(name="web", resource="dashboard_guilds")
async def dashboard_guilds_endpoint(request: web.Request) -> web.Response:
    """Return all known guilds for the dashboard's filter dropdown."""
    add_span_request_id(generate_request_id())
    del request
    async with db_session_manager():
        data = await services.dashboard.dashboard_guilds()
    return web.Response(
        status=200,
        content_type="application/json",
        text=json.dumps({"guilds": data}),
    )
