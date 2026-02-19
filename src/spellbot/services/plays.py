from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from asgiref.sync import sync_to_async
from dateutil import tz
from dateutil.relativedelta import relativedelta
from sqlalchemy.sql.expression import and_, extract, func, text

from spellbot.database import DatabaseSession
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.models import Channel, Game, Guild, Play, User

USER_PAGE_SIZE = 25
CHANNEL_PAGE_SIZE = 10

USER_RECORDS_SQL = r"""
    WITH game_plays AS (
        SELECT
            games.id AS game_id,
            games.updated_at,
            games.channel_xid,
            posts.message_xid,
            games.game_link,
            games.format,
            games.service
        FROM games
        JOIN plays ON plays.game_id = games.id
        JOIN posts ON posts.game_id = games.id
            AND posts.guild_xid = games.guild_xid
            AND posts.channel_xid = games.channel_xid
        WHERE
            games.guild_xid = :guild_xid AND
            plays.user_xid = :user_xid
        ORDER BY games.updated_at DESC
        OFFSET :offset
        LIMIT :page_size
    )
    SELECT
        game_plays.game_id,
        game_plays.updated_at,
        game_plays.channel_xid,
        game_plays.message_xid,
        game_plays.game_link,
        game_plays.format,
        game_plays.service,
        channels.name,
        STRING_AGG(
            CONCAT(
                REPLACE(REPLACE(users.name, ':', ''), '@', ''),
                ':',
                users.xid
            ),
            '@'
            ORDER BY users.xid
        )
    FROM game_plays
    JOIN plays ON plays.game_id = game_plays.game_id
    JOIN users ON users.xid = plays.user_xid
    JOIN channels ON channels.xid = game_plays.channel_xid
    GROUP BY
        game_plays.game_id,
        game_plays.updated_at,
        game_plays.channel_xid,
        game_plays.message_xid,
        game_plays.game_link,
        game_plays.format,
        game_plays.service,
        channels.name
    ORDER BY game_plays.updated_at DESC
    ;
"""

CHANNEL_RECORDS_SQL = r"""
    SELECT
        games.id,
        games.updated_at,
        posts.message_xid,
        games.game_link,
        games.format,
        games.service,
        STRING_AGG(
            CONCAT(
                REPLACE(REPLACE(users.name, ':', ''), '@', ''),
                ':',
                users.xid
            ),
            '@'
            ORDER BY users.xid
        )
    FROM games
    JOIN plays ON plays.game_id = games.id
    JOIN users ON users.xid = plays.user_xid
    JOIN posts ON posts.game_id = games.id
        AND posts.guild_xid = games.guild_xid
        AND posts.channel_xid = games.channel_xid
    WHERE
        games.guild_xid = :guild_xid AND
        games.channel_xid = :channel_xid
    GROUP BY
        games.id,
        games.updated_at,
        posts.message_xid,
        games.game_link,
        games.format,
        games.service
    ORDER BY games.updated_at DESC
    OFFSET :offset
    LIMIT :page_size
    ;
"""


def make_scores(data: str) -> dict[str, Any]:
    scores = {}
    records = data.split("@")
    for record in records:
        name, xid = record.split(":")
        scores[name] = (xid,)
    return scores


def decomposed(combined_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decomposed_data = []
    for data in combined_data:
        for name, score_data in data["scores"].items():
            decomposed_datum = {
                "id": data["id"],
                "updated_at": data["updated_at"],
                "guild": data["guild"],
                "channel": data["channel"],
                "message": data["message"],
                "link": data["link"],
                "format": data["format"],
                "guild_name": data["guild_name"],
                "channel_name": data["channel_name"],
                "user_name": name,
                "user_xid": score_data[0],
            }
            decomposed_data.append(decomposed_datum)
    return decomposed_data


class PlaysService:
    @sync_to_async()
    def get_plays_by_game_id(self, game_id: int) -> list[Play]:
        return DatabaseSession.query(Play).filter(Play.game_id == game_id).all()

    @sync_to_async()
    def verify_game_pin(self, *, game_id: int, user_xid: int, guild_xid: int, pin: str) -> bool:
        filters = [
            Play.game_id == game_id,
            Play.user_xid == user_xid,
            Play.og_guild_xid == guild_xid,
            Play.pin == pin,
        ]
        if not (play := DatabaseSession.query(Play).filter(and_(*filters)).one_or_none()):
            return False
        play.verified_at = datetime.now(tz=UTC)
        DatabaseSession.commit()
        return True

    @sync_to_async()
    def count(self, user_xid: int, guild_xid: int) -> int:
        return int(
            DatabaseSession.query(Play)
            .join(Game)
            .filter(
                and_(
                    Play.user_xid == user_xid,
                    Game.guild_xid == guild_xid,
                ),
            )
            .count()
            or 0,
        )

    @sync_to_async()
    def user_records(
        self,
        guild_xid: int,
        user_xid: int,
        page: int = 0,
    ) -> list[dict[str, Any]] | None:
        guild = DatabaseSession.query(Guild).filter(Guild.xid == guild_xid).one_or_none()
        if not guild:
            return None

        rows = DatabaseSession.execute(
            text(USER_RECORDS_SQL),
            {
                "guild_xid": guild_xid,
                "user_xid": user_xid,
                "offset": page * USER_PAGE_SIZE,
                "page_size": USER_PAGE_SIZE,
            },
        )
        return [
            {
                "id": row[0],
                "updated_at": row[1].replace(tzinfo=tz.UTC).timestamp() * 1000,
                "guild": guild_xid,
                "channel": row[2],
                "message": row[3],
                "link": row[4],
                "format": str(GameFormat(row[5])),
                "service": str(GameService(row[6])),
                "guild_name": guild.name,
                "channel_name": row[7],
                "scores": make_scores(row[8]),
            }
            for row in rows
        ]

    @sync_to_async()
    def channel_records(
        self,
        guild_xid: int,
        channel_xid: int,
        page: int = 0,
    ) -> list[dict[str, Any]] | None:
        guild = DatabaseSession.query(Guild).filter(Guild.xid == guild_xid).one_or_none()
        if not guild:
            return None
        channel = DatabaseSession.query(Channel).filter(Channel.xid == channel_xid).one_or_none()
        if not channel:
            return None

        rows = DatabaseSession.execute(
            text(CHANNEL_RECORDS_SQL),
            {
                "guild_xid": guild_xid,
                "channel_xid": channel_xid,
                "offset": page * CHANNEL_PAGE_SIZE,
                "page_size": CHANNEL_PAGE_SIZE,
            },
        )
        combined_data = [
            {
                "id": row[0],
                "updated_at": row[1].replace(tzinfo=tz.UTC).timestamp() * 1000,
                "guild": guild_xid,
                "channel": channel_xid,
                "message": row[2],
                "link": row[3],
                "format": str(GameFormat(row[4])),
                "service": str(GameService(row[5])),
                "guild_name": guild.name,
                "channel_name": channel.name,
                "scores": make_scores(row[6]),
            }
            for row in rows
        ]
        return decomposed(combined_data)

    @sync_to_async()
    def top_records(
        self,
        guild_xid: int,
        channel_xid: int,
        monthly: bool,
        ago: int,
    ) -> list[tuple[str, Any]]:
        filters = [
            Play.game_id == Game.id,
            Game.guild_xid == guild_xid,
            Game.channel_xid == channel_xid,
        ]
        if monthly:
            target = datetime.now(tz=UTC).date() + relativedelta(months=-ago)
            filters.append(extract("year", Game.started_at) == target.year)
            filters.append(extract("month", Game.started_at) == target.month)
        result = (
            DatabaseSession.query(
                Play.user_xid,
                func.count(Play.game_id).label("count"),
            )
            .filter(*filters)
            .group_by(Play.user_xid)
            .order_by(text("count DESC"))
            .limit(10)
        )
        return result.all()

    @sync_to_async()
    def guild_analytics(self, guild_xid: int) -> dict[str, Any] | None:  # noqa: PLR0915
        guild = DatabaseSession.query(Guild).filter(Guild.xid == guild_xid).one_or_none()
        if not guild:
            return None

        # Total started games
        total_games = int(
            DatabaseSession.query(func.count(Game.id))
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.deleted_at.is_(None),
            )
            .scalar()
            or 0,
        )

        # Expired games (deleted before starting)
        expired_games = int(
            DatabaseSession.query(func.count(Game.id))
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.is_(None),
                Game.deleted_at.isnot(None),
            )
            .scalar()
            or 0,
        )

        # Fill rate
        total_attempted = total_games + expired_games
        fill_rate = round(100 * total_games / total_attempted, 1) if total_attempted else 0.0

        # Unique players (all time)
        unique_players = int(
            DatabaseSession.query(func.count(func.distinct(Play.user_xid)))
            .join(Game, Play.game_id == Game.id)
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.deleted_at.is_(None),
            )
            .scalar()
            or 0,
        )

        # Monthly active users (unique players in last 30 days)
        thirty_days_ago = datetime.now(tz=UTC) + relativedelta(days=-30)
        monthly_active_users = int(
            DatabaseSession.query(func.count(func.distinct(Play.user_xid)))
            .join(Game, Play.game_id == Game.id)
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.started_at >= thirty_days_ago,
                Game.deleted_at.is_(None),
            )
            .scalar()
            or 0,
        )

        # Repeat player rate (% of monthly players who played more than once)
        repeat_subq = (
            DatabaseSession.query(
                Play.user_xid,
                func.count(func.distinct(Game.id)).label("game_count"),
            )
            .join(Game, Play.game_id == Game.id)
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.started_at >= thirty_days_ago,
                Game.deleted_at.is_(None),
            )
            .group_by(Play.user_xid)
            .subquery()
        )
        repeat_players = int(
            DatabaseSession.query(func.count())
            .select_from(repeat_subq)
            .filter(repeat_subq.c.game_count > 1)
            .scalar()
            or 0,
        )
        repeat_player_rate = (
            round(100 * repeat_players / monthly_active_users, 1) if monthly_active_users else 0.0
        )

        # Games per day (last 30 days)
        daily_rows = (
            DatabaseSession.query(
                func.date(Game.started_at).label("day"),
                func.count(Game.id).label("count"),
            )
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.started_at >= thirty_days_ago,
                Game.deleted_at.is_(None),
            )
            .group_by(func.date(Game.started_at))
            .order_by(text("day"))
            .all()
        )
        games_per_day = [{"day": str(row[0]), "count": row[1]} for row in daily_rows]

        # Average wait time per day (last 30 days) — minutes from created_at to started_at
        wait_rows = (
            DatabaseSession.query(
                func.date(Game.started_at).label("day"),
                func.avg(
                    extract("epoch", Game.started_at) - extract("epoch", Game.created_at),
                ).label("avg_seconds"),
            )
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.started_at >= thirty_days_ago,
                Game.deleted_at.is_(None),
            )
            .group_by(func.date(Game.started_at))
            .order_by(text("day"))
            .all()
        )
        avg_wait_per_day = [
            {"day": str(row[0]), "minutes": round(float(row[1] or 0) / 60, 1)} for row in wait_rows
        ]

        # Expired games per day (last 30 days)
        expired_daily_rows = (
            DatabaseSession.query(
                func.date(Game.deleted_at).label("day"),
                func.count(Game.id).label("count"),
            )
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.is_(None),
                Game.deleted_at.isnot(None),
                Game.deleted_at >= thirty_days_ago,
            )
            .group_by(func.date(Game.deleted_at))
            .order_by(text("day"))
            .all()
        )
        expired_per_day = [{"day": str(row[0]), "count": row[1]} for row in expired_daily_rows]

        # Daily new users (users whose created_at falls on that day and who played in this guild)
        new_user_rows = (
            DatabaseSession.query(
                func.date(User.created_at).label("day"),
                func.count(func.distinct(User.xid)).label("count"),
            )
            .join(Play, Play.user_xid == User.xid)
            .join(Game, Play.game_id == Game.id)
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.deleted_at.is_(None),
                User.created_at >= thirty_days_ago,
            )
            .group_by(func.date(User.created_at))
            .order_by(text("day"))
            .all()
        )
        daily_new_users = [{"day": str(row[0]), "count": row[1]} for row in new_user_rows]

        # Most popular formats
        format_rows = (
            DatabaseSession.query(
                Game.format,
                func.count(Game.id).label("count"),
            )
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.deleted_at.is_(None),
            )
            .group_by(Game.format)
            .order_by(text("count DESC"))
            .limit(10)
            .all()
        )
        popular_formats = [
            {"format": str(GameFormat(row[0])), "count": row[1]} for row in format_rows
        ]

        # Games by hour of day (UTC, last 30 days)
        hourly_rows = (
            DatabaseSession.query(
                extract("hour", Game.started_at).label("hour"),
                func.count(Game.id).label("count"),
            )
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.started_at >= thirty_days_ago,
                Game.deleted_at.is_(None),
            )
            .group_by(extract("hour", Game.started_at))
            .order_by(text("hour"))
            .all()
        )
        games_by_hour = [{"hour": int(row[0]), "count": row[1]} for row in hourly_rows]

        # Expired games by hour of day (UTC, last 30 days)
        expired_hourly_rows = (
            DatabaseSession.query(
                extract("hour", Game.deleted_at).label("hour"),
                func.count(Game.id).label("count"),
            )
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.is_(None),
                Game.deleted_at.isnot(None),
                Game.deleted_at >= thirty_days_ago,
            )
            .group_by(extract("hour", Game.deleted_at))
            .order_by(text("hour"))
            .all()
        )
        expired_by_hour = [{"hour": int(row[0]), "count": row[1]} for row in expired_hourly_rows]

        # New users by hour of day (UTC, last 30 days)
        new_user_hourly_rows = (
            DatabaseSession.query(
                extract("hour", User.created_at).label("hour"),
                func.count(func.distinct(User.xid)).label("count"),
            )
            .join(Play, Play.user_xid == User.xid)
            .join(Game, Play.game_id == Game.id)
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.deleted_at.is_(None),
                User.created_at >= thirty_days_ago,
            )
            .group_by(extract("hour", User.created_at))
            .order_by(text("hour"))
            .all()
        )
        new_users_by_hour = [{"hour": int(row[0]), "count": row[1]} for row in new_user_hourly_rows]

        # Games by bracket per day (last 30 days)
        bracket_daily_rows = (
            DatabaseSession.query(
                func.date(Game.started_at).label("day"),
                Game.bracket,
                func.count(Game.id).label("count"),
            )
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.started_at >= thirty_days_ago,
                Game.deleted_at.is_(None),
            )
            .group_by(func.date(Game.started_at), Game.bracket)
            .order_by(text("day"))
            .all()
        )
        games_by_bracket_per_day = [
            {
                "day": str(row[0]),
                "bracket": str(GameBracket(row[1])),
                "count": row[2],
            }
            for row in bracket_daily_rows
        ]

        # Player retention by week (last 12 weeks)
        twelve_weeks_ago = datetime.now(tz=UTC) + relativedelta(weeks=-12)

        # Each player's first started game in this guild
        first_game_rows = (
            DatabaseSession.query(
                Play.user_xid,
                func.min(Game.started_at).label("first_game"),
            )
            .join(Game, Play.game_id == Game.id)
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.deleted_at.is_(None),
            )
            .group_by(Play.user_xid)
            .all()
        )
        first_game_map = {row[0]: row[1] for row in first_game_rows}

        # Players active per week (last 12 weeks)
        week_expr = func.date_trunc("week", Game.started_at)
        weekly_player_rows = (
            DatabaseSession.query(
                week_expr.label("week"),
                Play.user_xid,
            )
            .join(Game, Play.game_id == Game.id)
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.started_at >= twelve_weeks_ago,
                Game.deleted_at.is_(None),
            )
            .group_by(week_expr, Play.user_xid)
            .all()
        )

        weeks_players: dict[datetime, set[int]] = defaultdict(set)
        for row in weekly_player_rows:
            weeks_players[row[0]].add(row[1])

        player_retention = []
        for week_start in sorted(weeks_players.keys()):
            week_end = week_start + timedelta(days=7)
            new_count = 0
            returning_count = 0
            for user_xid in weeks_players[week_start]:
                first = first_game_map.get(user_xid)
                if first and first >= week_start and first < week_end:
                    new_count += 1
                else:
                    returning_count += 1
            player_retention.append(
                {
                    "week": str(week_start.date()),
                    "new": new_count,
                    "returning": returning_count,
                },
            )

        # Cumulative player growth (all time, by day)
        growth_rows = (
            DatabaseSession.query(
                func.date(func.min(Game.started_at)).label("day"),
                func.count(Play.user_xid.distinct()).label("count"),
            )
            .join(Game, Play.game_id == Game.id)
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.deleted_at.is_(None),
            )
            .group_by(Play.user_xid)
            .subquery()
        )
        daily_new_player_rows = (
            DatabaseSession.query(
                growth_rows.c.day,
                func.count().label("new_players"),
            )
            .group_by(growth_rows.c.day)
            .order_by(growth_rows.c.day)
            .all()
        )
        cumulative_players = []
        running_total = 0
        for row in daily_new_player_rows:
            running_total += row[1]
            cumulative_players.append({"day": str(row[0]), "total": running_total})

        # Median games per player (distribution histogram)
        games_per_player_rows = (
            DatabaseSession.query(
                Play.user_xid,
                func.count(Game.id).label("game_count"),
            )
            .join(Game, Play.game_id == Game.id)
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.deleted_at.is_(None),
            )
            .group_by(Play.user_xid)
            .all()
        )
        counts = sorted(row[1] for row in games_per_player_rows)
        if counts:
            mid = len(counts) // 2
            median_games = counts[mid] if len(counts) % 2 else (counts[mid - 1] + counts[mid]) / 2
        else:
            median_games = 0

        # Build histogram buckets
        count_freq = Counter(counts)
        max_count = max(counts) if counts else 0
        # Cap at 20 buckets; lump everything above into "20+"
        cap = 20
        games_histogram = [
            {"bucket": str(i), "players": count_freq.get(i, 0)}
            for i in range(1, min(max_count, cap) + 1)
        ]
        if max_count > cap:
            overflow = sum(v for k, v in count_freq.items() if k > cap)
            games_histogram.append({"bucket": f"{cap + 1}+", "players": overflow})

        # Busiest channels (top 10)
        channel_rows = (
            DatabaseSession.query(
                Channel.xid,
                Channel.name,
                func.count(Game.id).label("count"),
            )
            .join(Game, Game.channel_xid == Channel.xid)
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.deleted_at.is_(None),
            )
            .group_by(Channel.xid, Channel.name)
            .order_by(text("count DESC"))
            .limit(10)
            .all()
        )
        busiest_channels = [
            {"name": row[1] or str(row[0]), "count": row[2]} for row in channel_rows
        ]

        # Most popular services (all time)
        service_rows = (
            DatabaseSession.query(
                Game.service,
                func.count(Game.id).label("count"),
            )
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.deleted_at.is_(None),
            )
            .group_by(Game.service)
            .order_by(text("count DESC"))
            .limit(10)
            .all()
        )
        popular_services = [
            {"service": str(GameService(row[0])), "count": row[1]} for row in service_rows
        ]

        # Most popular services (last 30 days)
        service_rows_30d = (
            DatabaseSession.query(
                Game.service,
                func.count(Game.id).label("count"),
            )
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.started_at >= thirty_days_ago,
                Game.deleted_at.is_(None),
            )
            .group_by(Game.service)
            .order_by(text("count DESC"))
            .limit(10)
            .all()
        )
        popular_services_30d = [
            {"service": str(GameService(row[0])), "count": row[1]} for row in service_rows_30d
        ]

        # Top players (top 10) with user names (all time)
        player_rows = (
            DatabaseSession.query(
                Play.user_xid,
                User.name,
                func.count(Play.game_id).label("count"),
            )
            .join(Game, Play.game_id == Game.id)
            .join(User, User.xid == Play.user_xid)
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.deleted_at.is_(None),
            )
            .group_by(Play.user_xid, User.name)
            .order_by(text("count DESC"))
            .limit(10)
            .all()
        )
        top_players = [
            {"user_xid": str(row[0]), "name": row[1], "count": row[2]} for row in player_rows
        ]

        # Top players (top 10) with user names (last 30 days)
        player_rows_30d = (
            DatabaseSession.query(
                Play.user_xid,
                User.name,
                func.count(Play.game_id).label("count"),
            )
            .join(Game, Play.game_id == Game.id)
            .join(User, User.xid == Play.user_xid)
            .filter(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.started_at >= thirty_days_ago,
                Game.deleted_at.is_(None),
            )
            .group_by(Play.user_xid, User.name)
            .order_by(text("count DESC"))
            .limit(10)
            .all()
        )
        top_players_30d = [
            {"user_xid": str(row[0]), "name": row[1], "count": row[2]} for row in player_rows_30d
        ]

        return {
            "guild_name": guild.name,
            "total_games": total_games,
            "fill_rate": fill_rate,
            "unique_players": unique_players,
            "monthly_active_users": monthly_active_users,
            "repeat_player_rate": repeat_player_rate,
            "games_per_day": games_per_day,
            "avg_wait_per_day": avg_wait_per_day,
            "expired_per_day": expired_per_day,
            "daily_new_users": daily_new_users,
            "games_by_hour": games_by_hour,
            "expired_by_hour": expired_by_hour,
            "new_users_by_hour": new_users_by_hour,
            "games_by_bracket_per_day": games_by_bracket_per_day,
            "player_retention": player_retention,
            "cumulative_players": cumulative_players,
            "median_games": median_games,
            "games_histogram": games_histogram,
            "popular_formats": popular_formats,
            "busiest_channels": busiest_channels,
            "popular_services": popular_services,
            "popular_services_30d": popular_services_30d,
            "top_players": top_players,
            "top_players_30d": top_players_30d,
        }
