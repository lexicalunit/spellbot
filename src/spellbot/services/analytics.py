# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, distinct, func, select

from spellbot.database import DatabaseSession, any_of
from spellbot.enums import GameBracket
from spellbot.models import Block, Channel, Game, GuildMember, Play, User
from spellbot.services import dashboard
from spellbot.services.dashboard import count_rows, started_game_filters
from spellbot.services.filters import GuildFilter, PeriodSpec, parse_period
from spellbot.services.labels import SERVICE_LABEL

if TYPE_CHECKING:
    from sqlalchemy.sql import ColumnElement

# How many rows the page's top-N tables show.
TOP_N = 10
# How many rule phrases the page's word cloud shows.
TOP_PHRASES = 50
# How far back the retention chart looks unless all time is selected.
RETENTION_WINDOW = timedelta(weeks=12)
DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
ALL_TIME = PeriodSpec(period="all", start_dt=None, bucket="day")


def analytics_scope(guild_xid: int, *, all_time: bool) -> tuple[PeriodSpec, GuildFilter]:
    """Return the page's period (last 30 days or all time, by day) and a filter for the guild."""
    period = parse_period("all" if all_time else "30d")
    return replace(period, bucket="day"), GuildFilter(mode="include", xid=guild_xid)


def day(date: str) -> str:
    """Trim an ISO timestamp from a day bucket down to its date."""
    return date[:10]


async def analytics_summary(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return summary stats for the analytics dashboard."""
    period, opts = analytics_scope(guild_xid, all_time=all_time)
    summary = await dashboard.dashboard_summary(period, opts)
    players = summary["players"]

    # Repeat player rate: the share of players who played more than one game.
    per_player = (
        select(Play.user_xid, func.count(distinct(Game.id)).label("game_count"))
        .select_from(Play)
        .join(Game, Play.game_id == Game.id)
        .where(*started_game_filters(period, opts))
        .group_by(Play.user_xid)
        .subquery()
    )
    repeat_players = await count_rows(
        select(func.count()).select_from(per_player).where(per_player.c.game_count > 1),
    )
    return {
        "fill_rate": summary["fill_rate"],
        "total_games": summary["games"],
        "active_players": players,
        "repeat_player_rate": round(100 * repeat_players / players, 1) if players else 0.0,
    }


async def analytics_activity(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return daily started games, expired games, and new players."""
    period, opts = analytics_scope(guild_xid, all_time=all_time)
    games = await dashboard.dashboard_games(period, opts)
    new_users = await dashboard.new_user_bucket_series(period, opts)

    def per_day(series: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"day": day(point["date"]), "count": point["count"]} for point in series]

    return {
        "games_per_day": per_day(games["started"]),
        "expired_per_day": per_day(games["expired"]),
        "daily_new_users": per_day(new_users),
    }


async def analytics_wait_time(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return average wait time per day."""
    period, opts = analytics_scope(guild_xid, all_time=all_time)
    series = (await dashboard.dashboard_avg_wait_time(period, opts))["series"]
    return {
        "avg_wait_per_day": [
            {"day": day(point["date"]), "minutes": point["minutes"]} for point in series
        ],
    }


async def analytics_growth(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return cumulative player growth data."""
    period, opts = analytics_scope(guild_xid, all_time=all_time)
    series = (await dashboard.dashboard_player_growth(period, opts))["cumulative_players"]
    return {
        "cumulative_players": [
            {"day": day(point["date"]), "total": point["count"]} for point in series
        ],
    }


async def analytics_histogram(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return games per player histogram data."""
    period, opts = analytics_scope(guild_xid, all_time=all_time)
    result = await dashboard.dashboard_games_per_player(period, opts)
    return {"median_games": result["median"], "games_histogram": result["histogram"]}


async def analytics_formats(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return popular formats data."""
    period, opts = analytics_scope(guild_xid, all_time=all_time)
    rows = (await dashboard.dashboard_popular_formats(period, opts))["rows"]
    return {"popular_formats": rows[:TOP_N]}


async def analytics_languages(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return game languages data."""
    period, opts = analytics_scope(guild_xid, all_time=all_time)
    rows = (await dashboard.dashboard_game_languages(period, opts))["rows"]
    return {"top_languages": rows[:TOP_N]}


async def analytics_hour_of_day(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return games per UTC hour of the day."""
    period, opts = analytics_scope(guild_xid, all_time=all_time)
    return {"games_by_hour": (await dashboard.dashboard_hour_of_day(period, opts))["hours"]}


async def analytics_day_of_week(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return games per UTC day of the week, Sunday first."""
    period, opts = analytics_scope(guild_xid, all_time=all_time)
    days = (await dashboard.dashboard_day_of_week(period, opts))["days"]
    return {
        "games_by_day": [
            {"day": DAY_NAMES[d["dow"]], "day_num": d["dow"], "count": d["count"]} for d in days
        ],
    }


async def analytics_rules(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return top rules and n-gram frequencies for the word cloud."""
    period, opts = analytics_scope(guild_xid, all_time=all_time)
    result = await dashboard.dashboard_rules(period, opts)
    return {
        "top_rules": result["top_rules"][:TOP_N],
        "rule_ngrams": result["rule_ngrams"][:TOP_PHRASES],
    }


async def analytics_brackets(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return games by bracket per day."""
    period, opts = analytics_scope(guild_xid, all_time=all_time)
    day_col = func.date(Game.started_at).label("day")
    rows = (
        await DatabaseSession.execute(
            select(day_col, Game.bracket, func.count(Game.id))
            .where(*started_game_filters(period, opts))
            .group_by(day_col, Game.bracket)
            .order_by(day_col),
        )
    ).all()
    return {
        "games_by_bracket_per_day": [
            {"day": str(row[0]), "bracket": str(GameBracket(row[1])), "count": row[2]}
            for row in rows
        ],
    }


async def analytics_retention(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return how many of each week's players were new to the guild versus returning."""
    _, opts = analytics_scope(guild_xid, all_time=True)
    window = PeriodSpec(
        period="all" if all_time else "90d",
        start_dt=None if all_time else datetime.now(tz=UTC) - RETENTION_WINDOW,
        bucket="week",
    )
    week_col = func.date_trunc("week", Game.started_at).label("week")
    weekly_rows = (
        await DatabaseSession.execute(
            select(week_col, Play.user_xid)
            .select_from(Play)
            .join(Game, Play.game_id == Game.id)
            .where(*started_game_filters(window, opts))
            .group_by(week_col, Play.user_xid),
        )
    ).all()
    weeks_players: dict[datetime, set[int]] = defaultdict(set)
    for week, user_xid in weekly_rows:
        weeks_players[week].add(user_xid)

    # Each of those players' first game in this guild, ever.
    active_xids = list({user_xid for _, user_xid in weekly_rows})
    first_games = dict(
        (
            await DatabaseSession.execute(
                select(Play.user_xid, func.min(Game.started_at))
                .select_from(Play)
                .join(Game, Play.game_id == Game.id)
                .where(*started_game_filters(ALL_TIME, opts), any_of(Play.user_xid, active_xids))
                .group_by(Play.user_xid),
            )
        ).all(),
    )

    player_retention = []
    for week_start in sorted(weeks_players):
        week_end = week_start + timedelta(days=7)
        players = weeks_players[week_start]
        new = sum(1 for xid in players if week_start <= first_games[xid] < week_end)
        player_retention.append(
            {"week": str(week_start.date()), "new": new, "returning": len(players) - new},
        )
    return {"player_retention": player_retention}


async def analytics_channels(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return the channels with the most started games."""
    period, opts = analytics_scope(guild_xid, all_time=all_time)
    count_col = func.count(Game.id)
    rows = (
        await DatabaseSession.execute(
            select(Channel.xid, Channel.name, count_col)
            .select_from(Channel)
            .join(Game, Game.channel_xid == Channel.xid)
            .where(*started_game_filters(period, opts))
            .group_by(Channel.xid, Channel.name)
            .order_by(count_col.desc())
            .limit(TOP_N),
        )
    ).all()
    return {"busiest_channels": [{"name": row[1] or str(row[0]), "count": row[2]} for row in rows]}


async def analytics_channel_players(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return the channels with the most distinct players."""
    period, opts = analytics_scope(guild_xid, all_time=all_time)
    players_col = func.count(distinct(Play.user_xid))
    rows = (
        await DatabaseSession.execute(
            select(Channel.xid, Channel.name, players_col)
            .select_from(Channel)
            .join(Game, Game.channel_xid == Channel.xid)
            .join(Play, Play.game_id == Game.id)
            .where(*started_game_filters(period, opts))
            .group_by(Channel.xid, Channel.name)
            .order_by(players_col.desc())
            .limit(TOP_N),
        )
    ).all()
    return {"channel_players": [{"name": row[1] or str(row[0]), "players": row[2]} for row in rows]}


async def analytics_services(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return the most used game services."""
    period, opts = analytics_scope(guild_xid, all_time=all_time)
    count_col = func.count(Game.id)
    rows = (
        await DatabaseSession.execute(
            select(SERVICE_LABEL, count_col)
            .where(*started_game_filters(period, opts))
            .group_by(SERVICE_LABEL)
            .order_by(count_col.desc(), SERVICE_LABEL)
            .limit(TOP_N),
        )
    ).all()
    return {"popular_services": [{"service": row[0], "count": row[1]} for row in rows]}


async def analytics_players(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return the guild's most active players (only players with GuildMember records)."""
    period, opts = analytics_scope(guild_xid, all_time=all_time)
    count_col = func.count(Play.game_id)
    rows = (
        await DatabaseSession.execute(
            select(Play.user_xid, User.name, count_col)
            .select_from(Play)
            .join(Game, Play.game_id == Game.id)
            .join(User, User.xid == Play.user_xid)
            .join(
                GuildMember,
                and_(GuildMember.user_xid == Play.user_xid, GuildMember.guild_xid == guild_xid),
            )
            .where(*started_game_filters(period, opts))
            .group_by(Play.user_xid, User.name)
            .order_by(count_col.desc())
            .limit(TOP_N),
        )
    ).all()
    return {
        "top_players": [{"user_xid": str(row[0]), "name": row[1], "count": row[2]} for row in rows],
    }


async def analytics_blocked(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return the guild's most blocked players (only players with GuildMember records)."""
    period, _ = analytics_scope(guild_xid, all_time=all_time)
    members = select(GuildMember.user_xid).where(GuildMember.guild_xid == guild_xid)
    filters: list[ColumnElement[bool]] = [Block.blocked_user_xid.in_(members.scalar_subquery())]
    if period.start_dt is not None:
        filters.append(Block.created_at >= period.start_dt)
    count_col = func.count(Block.user_xid)
    rows = (
        await DatabaseSession.execute(
            select(Block.blocked_user_xid, User.name, count_col)
            .select_from(Block)
            .join(User, User.xid == Block.blocked_user_xid)
            .where(*filters)
            .group_by(Block.blocked_user_xid, User.name)
            .order_by(count_col.desc())
            .limit(TOP_N),
        )
    ).all()
    return {
        "top_blocked": [{"user_xid": str(row[0]), "name": row[1], "count": row[2]} for row in rows],
    }
