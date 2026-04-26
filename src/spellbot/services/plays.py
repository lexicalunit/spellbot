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
from spellbot.models import Block, Channel, Game, Guild, GuildMember, Play, User

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
        """Fetch all plays for the given game id."""
        return DatabaseSession.query(Play).filter(Play.game_id == game_id).all()

    @sync_to_async()
    def verify_game_pin(self, *, game_id: int, user_xid: int, guild_xid: int, pin: str) -> bool:
        """Verify that the given pin matches the user's play record for the game."""
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
        """Count the number of games played by a user in a guild."""
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
        """Fetch paginated game records for a user in a guild."""
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
        """Fetch paginated game records for a channel."""
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
        """Fetch top players by game count for a channel."""
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
    def guild_exists(self, guild_xid: int) -> bool:
        """Check if a guild exists."""
        return DatabaseSession.query(Guild).filter(Guild.xid == guild_xid).one_or_none() is not None

    @sync_to_async()
    def analytics_summary(self, guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
        """Return summary stats for the analytics dashboard."""
        thirty_days_ago = datetime.now(tz=UTC) + relativedelta(days=-30)

        # Base filters for started games
        base_filters = [
            Game.guild_xid == guild_xid,
            Game.started_at.isnot(None),
            Game.deleted_at.is_(None),
        ]
        if not all_time:
            base_filters.append(Game.started_at >= thirty_days_ago)

        # Base filters for expired games
        expired_filters = [
            Game.guild_xid == guild_xid,
            Game.started_at.is_(None),
            Game.deleted_at.isnot(None),
        ]
        if not all_time:
            expired_filters.append(Game.deleted_at >= thirty_days_ago)

        # Total started games
        total_games = int(
            DatabaseSession.query(func.count(Game.id)).filter(*base_filters).scalar() or 0,
        )

        # Expired games (deleted before starting)
        expired_games = int(
            DatabaseSession.query(func.count(Game.id)).filter(*expired_filters).scalar() or 0,
        )

        # Fill rate
        total_attempted = total_games + expired_games
        fill_rate = round(100 * total_games / total_attempted, 1) if total_attempted else 0.0

        # Active players (unique players in the period)
        active_players = int(
            DatabaseSession.query(func.count(func.distinct(Play.user_xid)))
            .join(Game, Play.game_id == Game.id)
            .filter(*base_filters)
            .scalar()
            or 0,
        )

        # Repeat player rate (% of players who played more than once)
        repeat_subq = (
            DatabaseSession.query(
                Play.user_xid,
                func.count(func.distinct(Game.id)).label("game_count"),
            )
            .join(Game, Play.game_id == Game.id)
            .filter(*base_filters)
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
            round(100 * repeat_players / active_players, 1) if active_players else 0.0
        )

        return {
            "fill_rate": fill_rate,
            "total_games": total_games,
            "active_players": active_players,
            "repeat_player_rate": repeat_player_rate,
        }

    @sync_to_async()
    def analytics_activity(self, guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
        """Return daily activity data."""
        thirty_days_ago = datetime.now(tz=UTC) + relativedelta(days=-30)

        # Games per day
        game_filters = [
            Game.guild_xid == guild_xid,
            Game.started_at.isnot(None),
            Game.deleted_at.is_(None),
        ]
        if not all_time:
            game_filters.append(Game.started_at >= thirty_days_ago)

        daily_rows = (
            DatabaseSession.query(
                func.date(Game.started_at).label("day"),
                func.count(Game.id).label("count"),
            )
            .filter(*game_filters)
            .group_by(func.date(Game.started_at))
            .order_by(text("day"))
            .all()
        )
        games_per_day = [{"day": str(row[0]), "count": row[1]} for row in daily_rows]

        # Expired games per day
        expired_filters = [
            Game.guild_xid == guild_xid,
            Game.started_at.is_(None),
            Game.deleted_at.isnot(None),
        ]
        if not all_time:
            expired_filters.append(Game.deleted_at >= thirty_days_ago)

        expired_daily_rows = (
            DatabaseSession.query(
                func.date(Game.deleted_at).label("day"),
                func.count(Game.id).label("count"),
            )
            .filter(*expired_filters)
            .group_by(func.date(Game.deleted_at))
            .order_by(text("day"))
            .all()
        )
        expired_per_day = [{"day": str(row[0]), "count": row[1]} for row in expired_daily_rows]

        # Daily new users
        new_user_filters = [
            Game.guild_xid == guild_xid,
            Game.started_at.isnot(None),
            Game.deleted_at.is_(None),
        ]
        if not all_time:
            new_user_filters.append(User.created_at >= thirty_days_ago)

        new_user_rows = (
            DatabaseSession.query(
                func.date(User.created_at).label("day"),
                func.count(func.distinct(User.xid)).label("count"),
            )
            .join(Play, Play.user_xid == User.xid)
            .join(Game, Play.game_id == Game.id)
            .filter(*new_user_filters)
            .group_by(func.date(User.created_at))
            .order_by(text("day"))
            .all()
        )
        daily_new_users = [{"day": str(row[0]), "count": row[1]} for row in new_user_rows]

        return {
            "games_per_day": games_per_day,
            "expired_per_day": expired_per_day,
            "daily_new_users": daily_new_users,
        }

    @sync_to_async()
    def analytics_wait_time(self, guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
        """Return average wait time per day."""
        thirty_days_ago = datetime.now(tz=UTC) + relativedelta(days=-30)

        filters = [
            Game.guild_xid == guild_xid,
            Game.started_at.isnot(None),
            Game.deleted_at.is_(None),
        ]
        if not all_time:
            filters.append(Game.started_at >= thirty_days_ago)

        wait_rows = (
            DatabaseSession.query(
                func.date(Game.started_at).label("day"),
                func.avg(
                    extract("epoch", Game.started_at) - extract("epoch", Game.created_at),
                ).label("avg_seconds"),
            )
            .filter(*filters)
            .group_by(func.date(Game.started_at))
            .order_by(text("day"))
            .all()
        )
        avg_wait_per_day = [
            {"day": str(row[0]), "minutes": round(float(row[1] or 0) / 60, 1)} for row in wait_rows
        ]

        return {"avg_wait_per_day": avg_wait_per_day}

    @sync_to_async()
    def analytics_brackets(self, guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
        """Return games by bracket per day."""
        thirty_days_ago = datetime.now(tz=UTC) + relativedelta(days=-30)

        filters = [
            Game.guild_xid == guild_xid,
            Game.started_at.isnot(None),
            Game.deleted_at.is_(None),
        ]
        if not all_time:
            filters.append(Game.started_at >= thirty_days_ago)

        bracket_daily_rows = (
            DatabaseSession.query(
                func.date(Game.started_at).label("day"),
                Game.bracket,
                func.count(Game.id).label("count"),
            )
            .filter(*filters)
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

        return {"games_by_bracket_per_day": games_by_bracket_per_day}

    @sync_to_async()
    def analytics_retention(self, guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
        """Return player retention data."""
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

        # Players active per week
        week_expr = func.date_trunc("week", Game.started_at)
        filters = [
            Game.guild_xid == guild_xid,
            Game.started_at.isnot(None),
            Game.deleted_at.is_(None),
        ]
        if not all_time:
            filters.append(Game.started_at >= twelve_weeks_ago)

        weekly_player_rows = (
            DatabaseSession.query(
                week_expr.label("week"),
                Play.user_xid,
            )
            .join(Game, Play.game_id == Game.id)
            .filter(*filters)
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

        return {"player_retention": player_retention}

    @sync_to_async()
    def analytics_growth(self, guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
        """Return cumulative player growth data."""
        thirty_days_ago = datetime.now(tz=UTC) + relativedelta(days=-30)

        filters = [
            Game.guild_xid == guild_xid,
            Game.started_at.isnot(None),
            Game.deleted_at.is_(None),
        ]
        if not all_time:
            filters.append(Game.started_at >= thirty_days_ago)

        growth_rows = (
            DatabaseSession.query(
                func.date(func.min(Game.started_at)).label("day"),
                func.count(Play.user_xid.distinct()).label("count"),
            )
            .join(Game, Play.game_id == Game.id)
            .filter(*filters)
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

        return {"cumulative_players": cumulative_players}

    @sync_to_async()
    def analytics_histogram(self, guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
        """Return games per player histogram data."""
        thirty_days_ago = datetime.now(tz=UTC) + relativedelta(days=-30)

        filters = [
            Game.guild_xid == guild_xid,
            Game.started_at.isnot(None),
            Game.deleted_at.is_(None),
        ]
        if not all_time:
            filters.append(Game.started_at >= thirty_days_ago)

        games_per_player_rows = (
            DatabaseSession.query(
                Play.user_xid,
                func.count(Game.id).label("game_count"),
            )
            .join(Game, Play.game_id == Game.id)
            .filter(*filters)
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

        return {"median_games": median_games, "games_histogram": games_histogram}

    @sync_to_async()
    def analytics_formats(self, guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
        """Return popular formats data."""
        thirty_days_ago = datetime.now(tz=UTC) + relativedelta(days=-30)

        filters = [
            Game.guild_xid == guild_xid,
            Game.started_at.isnot(None),
            Game.deleted_at.is_(None),
        ]
        if not all_time:
            filters.append(Game.started_at >= thirty_days_ago)

        format_rows = (
            DatabaseSession.query(
                Game.format,
                func.count(Game.id).label("count"),
            )
            .filter(*filters)
            .group_by(Game.format)
            .order_by(text("count DESC"))
            .limit(10)
            .all()
        )
        popular_formats = [
            {"format": str(GameFormat(row[0])), "count": row[1]} for row in format_rows
        ]

        return {"popular_formats": popular_formats}

    @sync_to_async()
    def analytics_channels(self, guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
        """Return busiest channels data."""
        thirty_days_ago = datetime.now(tz=UTC) + relativedelta(days=-30)

        filters = [
            Game.guild_xid == guild_xid,
            Game.started_at.isnot(None),
            Game.deleted_at.is_(None),
        ]
        if not all_time:
            filters.append(Game.started_at >= thirty_days_ago)

        channel_rows = (
            DatabaseSession.query(
                Channel.xid,
                Channel.name,
                func.count(Game.id).label("count"),
            )
            .join(Game, Game.channel_xid == Channel.xid)
            .filter(*filters)
            .group_by(Channel.xid, Channel.name)
            .order_by(text("count DESC"))
            .limit(10)
            .all()
        )
        busiest_channels = [
            {"name": row[1] or str(row[0]), "count": row[2]} for row in channel_rows
        ]

        return {"busiest_channels": busiest_channels}

    @sync_to_async()
    def analytics_services(self, guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
        """Return popular services data."""
        thirty_days_ago = datetime.now(tz=UTC) + relativedelta(days=-30)

        filters = [
            Game.guild_xid == guild_xid,
            Game.started_at.isnot(None),
            Game.deleted_at.is_(None),
        ]
        if not all_time:
            filters.append(Game.started_at >= thirty_days_ago)

        service_rows = (
            DatabaseSession.query(
                Game.service,
                func.count(Game.id).label("count"),
            )
            .filter(*filters)
            .group_by(Game.service)
            .order_by(text("count DESC"))
            .limit(10)
            .all()
        )
        popular_services = [
            {"service": str(GameService(row[0])), "count": row[1]} for row in service_rows
        ]

        return {"popular_services": popular_services}

    @sync_to_async()
    def analytics_players(self, guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
        """Return top players data (only players with GuildMember records)."""
        thirty_days_ago = datetime.now(tz=UTC) + relativedelta(days=-30)

        filters = [
            Game.guild_xid == guild_xid,
            Game.started_at.isnot(None),
            Game.deleted_at.is_(None),
            GuildMember.guild_xid == guild_xid,
        ]
        if not all_time:
            filters.append(Game.started_at >= thirty_days_ago)

        player_rows = (
            DatabaseSession.query(
                Play.user_xid,
                User.name,
                func.count(Play.game_id).label("count"),
            )
            .join(Game, Play.game_id == Game.id)
            .join(User, User.xid == Play.user_xid)
            .join(
                GuildMember,
                and_(
                    GuildMember.user_xid == Play.user_xid,
                    GuildMember.guild_xid == guild_xid,
                ),
            )
            .filter(*filters)
            .group_by(Play.user_xid, User.name)
            .order_by(text("count DESC"))
            .limit(10)
            .all()
        )
        top_players = [
            {"user_xid": str(row[0]), "name": row[1], "count": row[2]} for row in player_rows
        ]

        return {"top_players": top_players}

    @sync_to_async()
    def analytics_blocked(self, guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
        """Return top blocked players data (only players with GuildMember records)."""
        thirty_days_ago = datetime.now(tz=UTC) + relativedelta(days=-30)

        # Get users who are members of this guild
        members_in_guild = (
            DatabaseSession.query(GuildMember.user_xid)
            .filter(GuildMember.guild_xid == guild_xid)
            .scalar_subquery()
        )

        # Count blocks for each blocked user, filtering to only guild members
        block_filters = [Block.blocked_user_xid.in_(members_in_guild)]
        if not all_time:
            block_filters.append(Block.created_at >= thirty_days_ago)
        blocked_rows = (
            DatabaseSession.query(
                Block.blocked_user_xid,
                User.name,
                func.count(Block.user_xid).label("count"),
            )
            .join(User, User.xid == Block.blocked_user_xid)
            .filter(*block_filters)
            .group_by(Block.blocked_user_xid, User.name)
            .order_by(text("count DESC"))
            .limit(10)
            .all()
        )
        top_blocked = [
            {"user_xid": str(row[0]), "name": row[1], "count": row[2]} for row in blocked_rows
        ]

        return {"top_blocked": top_blocked}
