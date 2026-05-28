from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from dateutil import tz
from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.sql.expression import and_, extract, func, text

from spellbot.database import DatabaseSession
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.models import Block, Channel, Game, Guild, GuildMember, Play, User

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

USER_PAGE_SIZE = 25
CHANNEL_PAGE_SIZE = 10

# Whitelisted columns the records pages may sort by. The values are interpolated
# directly into the SQL so they must never come from user input verbatim; only
# keys from these maps are accepted.
USER_RECORDS_SORT_COLUMNS: dict[str, tuple[str, str]] = {
    # key -> (inner-CTE expression, outer-query expression)
    "id": ("games.id", "game_plays.game_id"),
    "updated_at": ("games.updated_at", "game_plays.updated_at"),
    "guild_name": ("guilds.name", "game_plays.guild_name"),
    "format": ("games.format", "game_plays.format"),
    "seats": ("games.seats", "game_plays.seats"),
    "bracket": ("games.bracket", "game_plays.bracket"),
}

CHANNEL_RECORDS_SORT_COLUMNS: dict[str, tuple[str, str]] = {
    # key -> (inner-CTE expression, outer-query expression)
    "id": ("games.id", "page.id"),
    "updated_at": ("games.updated_at", "page.updated_at"),
    "format": ("games.format", "page.format"),
    "seats": ("games.seats", "page.seats"),
    "bracket": ("games.bracket", "page.bracket"),
}


@dataclass
class RecordFilters:
    """Filter / sort options applied to user and channel record listings."""

    with_player_xid: int | None = None
    with_player_name: str | None = None
    guild_xid: int | None = None
    guild_name: str | None = None
    formats: list[int] = field(default_factory=list)
    brackets: list[int] = field(default_factory=list)
    from_utc: datetime | None = None
    to_utc: datetime | None = None
    sort_by: str = "updated_at"
    sort_dir: str = "desc"


def shared_filter_sql(
    opts: RecordFilters,
    *,
    include_guild: bool,
) -> tuple[list[str], dict[str, Any]]:
    """Build parameterized WHERE fragments + bind params shared by both pages."""
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if opts.with_player_xid is not None:
        clauses.append(
            "EXISTS (SELECT 1 FROM plays AS plays_wp "
            "WHERE plays_wp.game_id = games.id "
            "AND plays_wp.user_xid = :with_player_xid)",
        )
        params["with_player_xid"] = opts.with_player_xid
    elif opts.with_player_name:
        clauses.append(
            "EXISTS (SELECT 1 FROM plays AS plays_wp "
            "JOIN users AS users_wp ON users_wp.xid = plays_wp.user_xid "
            "WHERE plays_wp.game_id = games.id "
            "AND users_wp.name ILIKE :with_player_name)",
        )
        params["with_player_name"] = f"%{opts.with_player_name}%"
    if include_guild and opts.guild_xid is not None:
        clauses.append("games.guild_xid = :guild_xid_filter")
        params["guild_xid_filter"] = opts.guild_xid
    elif include_guild and opts.guild_name:
        clauses.append("guilds.name ILIKE :guild_name_filter")
        params["guild_name_filter"] = f"%{opts.guild_name}%"
    if opts.formats:
        clauses.append("games.format = ANY(:formats)")
        params["formats"] = opts.formats
    if opts.brackets:
        clauses.append("games.bracket = ANY(:brackets)")
        params["brackets"] = opts.brackets
    if opts.from_utc is not None:
        clauses.append("games.updated_at >= :from_utc")
        params["from_utc"] = opts.from_utc
    if opts.to_utc is not None:
        clauses.append("games.updated_at < :to_utc")
        params["to_utc"] = opts.to_utc
    return clauses, params


def sort_direction(opts: RecordFilters) -> str:
    return "DESC" if opts.sort_dir == "desc" else "ASC"


def build_user_records_sql(
    opts: RecordFilters,
    *,
    paginated: bool,
) -> tuple[str, dict[str, Any]]:
    inner_clauses = ["plays.user_xid = :user_xid"]
    shared, params = shared_filter_sql(opts, include_guild=True)
    inner_clauses.extend(shared)
    inner_col, outer_col = USER_RECORDS_SORT_COLUMNS.get(
        opts.sort_by,
        USER_RECORDS_SORT_COLUMNS["updated_at"],
    )
    direction = sort_direction(opts)
    paging = "OFFSET :offset LIMIT :page_size" if paginated else ""
    sql = f"""
        WITH game_plays AS (
            SELECT
                games.id AS game_id,
                games.updated_at,
                games.guild_xid,
                games.channel_xid,
                posts.message_xid,
                games.game_link,
                games.format,
                games.service,
                games.seats,
                games.bracket,
                games.locale,
                guilds.name AS guild_name
            FROM games
            JOIN plays ON plays.game_id = games.id
            JOIN posts ON posts.game_id = games.id
                AND posts.guild_xid = games.guild_xid
                AND posts.channel_xid = games.channel_xid
            JOIN guilds ON guilds.xid = games.guild_xid
            WHERE {" AND ".join(inner_clauses)}
            ORDER BY {inner_col} {direction}, games.id DESC
            {paging}
        )
        SELECT
            game_plays.game_id,
            game_plays.updated_at,
            game_plays.guild_xid,
            game_plays.channel_xid,
            game_plays.message_xid,
            game_plays.game_link,
            game_plays.format,
            game_plays.service,
            game_plays.seats,
            game_plays.bracket,
            game_plays.locale,
            game_plays.guild_name,
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
            game_plays.guild_xid,
            game_plays.channel_xid,
            game_plays.message_xid,
            game_plays.game_link,
            game_plays.format,
            game_plays.service,
            game_plays.seats,
            game_plays.bracket,
            game_plays.locale,
            game_plays.guild_name,
            channels.name
        ORDER BY {outer_col} {direction}, game_plays.game_id DESC
        ;
    """  # noqa: S608
    return sql, params


def build_user_records_count_sql(
    opts: RecordFilters,
) -> tuple[str, dict[str, Any]]:
    clauses = ["plays.user_xid = :user_xid"]
    shared, params = shared_filter_sql(opts, include_guild=True)
    clauses.extend(shared)
    sql = f"""
        SELECT COUNT(DISTINCT games.id)
        FROM games
        JOIN plays ON plays.game_id = games.id
        JOIN guilds ON guilds.xid = games.guild_xid
        WHERE {" AND ".join(clauses)}
        ;
    """  # noqa: S608
    return sql, params


def build_channel_records_sql(
    opts: RecordFilters,
    *,
    paginated: bool,
) -> tuple[str, dict[str, Any]]:
    clauses = [
        "games.guild_xid = :guild_xid",
        "games.channel_xid = :channel_xid",
    ]
    shared, params = shared_filter_sql(opts, include_guild=False)
    clauses.extend(shared)
    inner_col, outer_col = CHANNEL_RECORDS_SORT_COLUMNS.get(
        opts.sort_by,
        CHANNEL_RECORDS_SORT_COLUMNS["updated_at"],
    )
    direction = sort_direction(opts)
    paging = "OFFSET :offset LIMIT :page_size" if paginated else ""
    # Page the lean rows (no plays/users join) first, then STRING_AGG only for
    # the surviving page. All player-related filters in `shared_filter_sql` are
    # already EXISTS subqueries so the inner CTE does not need `plays`/`users`.
    sql = f"""
        WITH page AS (
            SELECT
                games.id,
                games.updated_at,
                posts.message_xid,
                games.game_link,
                games.format,
                games.service,
                games.seats,
                games.bracket,
                games.locale
            FROM games
            JOIN posts ON posts.game_id = games.id
                AND posts.guild_xid = games.guild_xid
                AND posts.channel_xid = games.channel_xid
            WHERE {" AND ".join(clauses)}
            ORDER BY {inner_col} {direction}, games.id DESC
            {paging}
        )
        SELECT
            page.id,
            page.updated_at,
            page.message_xid,
            page.game_link,
            page.format,
            page.service,
            page.seats,
            page.bracket,
            page.locale,
            STRING_AGG(
                CONCAT(
                    REPLACE(REPLACE(users.name, ':', ''), '@', ''),
                    ':',
                    users.xid
                ),
                '@'
                ORDER BY users.xid
            )
        FROM page
        JOIN plays ON plays.game_id = page.id
        JOIN users ON users.xid = plays.user_xid
        GROUP BY
            page.id,
            page.updated_at,
            page.message_xid,
            page.game_link,
            page.format,
            page.service,
            page.seats,
            page.bracket,
            page.locale
        ORDER BY {outer_col} {direction}, page.id DESC
        ;
    """  # noqa: S608
    return sql, params


def build_channel_records_count_sql(
    opts: RecordFilters,
) -> tuple[str, dict[str, Any]]:
    clauses = [
        "games.guild_xid = :guild_xid",
        "games.channel_xid = :channel_xid",
    ]
    shared, params = shared_filter_sql(opts, include_guild=False)
    clauses.extend(shared)
    # Match the page query's INNER JOIN on `posts` so the count never includes
    # games that wouldn't actually be listed. `plays` is not needed here because
    # all player-related filters are already EXISTS subqueries.
    sql = f"""
        SELECT COUNT(*)
        FROM games
        JOIN posts ON posts.game_id = games.id
            AND posts.guild_xid = games.guild_xid
            AND posts.channel_xid = games.channel_xid
        WHERE {" AND ".join(clauses)}
        ;
    """  # noqa: S608
    return sql, params


USER_RECORDS_EXPORT_SQL, _ = build_user_records_sql(RecordFilters(), paginated=False)
CHANNEL_RECORDS_EXPORT_SQL, _ = build_channel_records_sql(RecordFilters(), paginated=False)


def make_scores(data: str) -> dict[str, Any]:
    """Parse the encoded `name:xid@name:xid` scores string into a dict by player name."""
    scores = {}
    records = data.split("@")
    for record in records:
        name, xid = record.split(":")
        scores[name] = (xid,)
    return scores


def decomposed(combined_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten a list of game records into one row per player score."""
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
                "service": data["service"],
                "seats": data["seats"],
                "bracket": data["bracket"],
                "locale": data["locale"],
                "guild_name": data["guild_name"],
                "channel_name": data["channel_name"],
                "user_name": name,
                "user_xid": score_data[0],
            }
            decomposed_data.append(decomposed_datum)
    return decomposed_data


async def get_plays_by_game_id(game_id: int) -> list[Play]:
    """Fetch all plays for the given game id."""
    return (
        (await DatabaseSession.execute(select(Play).where(Play.game_id == game_id))).scalars().all()  # type: ignore
    )


async def verify_game_pin(
    *,
    game_id: int,
    user_xid: int,
    guild_xid: int,
    pin: str,
) -> bool:
    """Verify that the given pin matches the user's play record for the game."""
    filters = [
        Play.game_id == game_id,
        Play.user_xid == user_xid,
        Play.og_guild_xid == guild_xid,
        Play.pin == pin,
    ]
    if not (
        play := (
            await DatabaseSession.execute(select(Play).where(and_(*filters)))
        ).scalar_one_or_none()
    ):
        return False
    play.verified_at = datetime.now(tz=UTC)
    await DatabaseSession.commit()
    return True


async def count(user_xid: int) -> int:
    """Count the number of games played by a user across all guilds."""
    return int(
        (
            await DatabaseSession.execute(
                select(func.count()).select_from(Play).where(Play.user_xid == user_xid),
            )
        ).scalar()
        or 0,
    )


async def user_records(
    user_xid: int,
    page: int = 0,
    opts: RecordFilters | None = None,
) -> tuple[list[dict[str, Any]], int] | None:
    """
    Fetch paginated game records for a user across all guilds.

    Returns a `(rows, total_count)` tuple where `total_count` is the total number
    of distinct matching games before pagination, or `None` if the user is unknown.
    """
    user = (
        await DatabaseSession.execute(select(User).where(User.xid == user_xid))
    ).scalar_one_or_none()
    if not user:
        return None

    opts = opts or RecordFilters()
    page_sql, page_params = build_user_records_sql(opts, paginated=True)
    count_sql, count_params = build_user_records_count_sql(opts)
    base_params: dict[str, Any] = {"user_xid": user_xid}

    total = int(
        (await DatabaseSession.execute(text(count_sql), {**base_params, **count_params})).scalar()
        or 0,
    )

    rows = await DatabaseSession.execute(
        text(page_sql),
        {
            **base_params,
            **page_params,
            "offset": page * USER_PAGE_SIZE,
            "page_size": USER_PAGE_SIZE,
        },
    )
    return [
        {
            "id": row[0],
            "updated_at": row[1].replace(tzinfo=tz.UTC).timestamp() * 1000,
            "guild": row[2],
            "channel": row[3],
            "message": row[4],
            "link": row[5],
            "format": str(GameFormat(row[6])),
            "service": str(GameService(row[7])),
            "seats": row[8],
            "bracket": str(GameBracket(row[9])),
            "locale": row[10],
            "guild_name": row[11],
            "channel_name": row[12],
            "scores": make_scores(row[13]),
        }
        for row in rows
    ], total


async def channel_records(
    guild_xid: int,
    channel_xid: int,
    page: int = 0,
    opts: RecordFilters | None = None,
) -> tuple[list[dict[str, Any]], int] | None:
    """
    Fetch paginated game records for a channel.

    Returns a `(rows, total_count)` tuple where `total_count` is the total number
    of distinct matching games (not players) before pagination, or `None` if the
    guild or channel is unknown.
    """
    guild = (
        await DatabaseSession.execute(select(Guild).where(Guild.xid == guild_xid))  # type: ignore
    ).scalar_one_or_none()
    if not guild:
        return None
    channel = (
        await DatabaseSession.execute(select(Channel).where(Channel.xid == channel_xid))  # type: ignore
    ).scalar_one_or_none()
    if not channel:
        return None

    opts = opts or RecordFilters()
    page_sql, page_params = build_channel_records_sql(opts, paginated=True)
    count_sql, count_params = build_channel_records_count_sql(opts)
    base_params: dict[str, Any] = {
        "guild_xid": guild_xid,
        "channel_xid": channel_xid,
    }

    total = int(
        (await DatabaseSession.execute(text(count_sql), {**base_params, **count_params})).scalar()
        or 0,
    )

    rows = await DatabaseSession.execute(
        text(page_sql),
        {
            **base_params,
            **page_params,
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
            "seats": row[6],
            "bracket": str(GameBracket(row[7])),
            "locale": row[8],
            "guild_name": guild.name,
            "channel_name": channel.name,
            "scores": make_scores(row[9]),
        }
        for row in rows
    ]
    return decomposed(combined_data), total


async def user_export_target_exists(user_xid: int) -> bool:
    """Return True if the user for a user-records export exists."""
    return (
        await DatabaseSession.execute(
            select(User.xid).where(User.xid == user_xid),
        )
    ).scalar_one_or_none() is not None


async def channel_export_target_exists(guild_xid: int, channel_xid: int) -> bool:
    """Return True if both the guild and channel for a channel-records export exist."""
    if not await guild_exists(guild_xid):
        return False
    return (
        await DatabaseSession.execute(
            select(Channel.xid).where(Channel.xid == channel_xid),  # type: ignore
        )
    ).scalar_one_or_none() is not None


async def stream_user_records(
    user_xid: int,
) -> AsyncIterator[dict[str, Any]]:
    """Stream all game records for a user across all guilds without pagination."""
    user_exists = (
        await DatabaseSession.execute(
            select(User.xid).where(User.xid == user_xid),
        )
    ).scalar_one_or_none()
    if user_exists is None:
        return

    result = await DatabaseSession.execute(
        text(USER_RECORDS_EXPORT_SQL),
        {"user_xid": user_xid},
    )
    for row in result:
        yield {
            "id": row[0],
            "updated_at": row[1].replace(tzinfo=tz.UTC).timestamp() * 1000,
            "guild": row[2],
            "channel": row[3],
            "message": row[4],
            "link": row[5],
            "format": str(GameFormat(row[6])),
            "service": str(GameService(row[7])),
            "seats": row[8],
            "bracket": str(GameBracket(row[9])),
            "locale": row[10],
            "guild_name": row[11],
            "channel_name": row[12],
            "scores": make_scores(row[13]),
        }


async def stream_channel_records(
    guild_xid: int,
    channel_xid: int,
) -> AsyncIterator[dict[str, Any]]:
    """Stream all game records for a channel without pagination, one row per player."""
    guild_name = (
        await DatabaseSession.execute(
            select(Guild.name).where(Guild.xid == guild_xid),  # type: ignore
        )
    ).scalar_one_or_none()
    if guild_name is None:
        return
    channel_name = (
        await DatabaseSession.execute(
            select(Channel.name).where(Channel.xid == channel_xid),  # type: ignore
        )
    ).scalar_one_or_none()
    if channel_name is None:
        return

    result = await DatabaseSession.execute(
        text(CHANNEL_RECORDS_EXPORT_SQL),
        {"guild_xid": guild_xid, "channel_xid": channel_xid},
    )
    for row in result:
        combined = {
            "id": row[0],
            "updated_at": row[1].replace(tzinfo=tz.UTC).timestamp() * 1000,
            "guild": guild_xid,
            "channel": channel_xid,
            "message": row[2],
            "link": row[3],
            "format": str(GameFormat(row[4])),
            "service": str(GameService(row[5])),
            "seats": row[6],
            "bracket": str(GameBracket(row[7])),
            "locale": row[8],
            "guild_name": guild_name,
            "channel_name": channel_name,
            "scores": make_scores(row[9]),
        }
        for player_row in decomposed([combined]):
            yield player_row


async def top_records(
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
    result = await DatabaseSession.execute(
        select(
            Play.user_xid,
            func.count(Play.game_id).label("count"),  # type: ignore
        )
        .where(*filters)
        .group_by(Play.user_xid)
        .order_by(text("count DESC"))
        .limit(10),
    )
    return result.all()


async def guild_exists(guild_xid: int) -> bool:
    """Check if a guild exists."""
    return (
        await DatabaseSession.execute(select(Guild).where(Guild.xid == guild_xid))  # type: ignore
    ).scalar_one_or_none() is not None


async def analytics_summary(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
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
        (
            await DatabaseSession.execute(
                select(func.count(Game.id)).where(*base_filters),
            )
        ).scalar()
        or 0,
    )

    # Expired games (deleted before starting)
    expired_games = int(
        (
            await DatabaseSession.execute(
                select(func.count(Game.id)).where(*expired_filters),
            )
        ).scalar()
        or 0,
    )

    # Fill rate
    total_attempted = total_games + expired_games
    fill_rate = round(100 * total_games / total_attempted, 1) if total_attempted else 0.0

    # Active players (unique players in the period)
    active_players = int(
        (
            await DatabaseSession.execute(
                select(func.count(func.distinct(Play.user_xid)))
                .select_from(Play)
                .join(Game, Play.game_id == Game.id)  # type: ignore
                .where(*base_filters),
            )
        ).scalar()
        or 0,
    )

    # Repeat player rate (% of players who played more than once)
    repeat_subq = (
        select(
            Play.user_xid,
            func.count(func.distinct(Game.id)).label("game_count"),
        )
        .select_from(Play)
        .join(Game, Play.game_id == Game.id)  # type: ignore
        .where(*base_filters)
        .group_by(Play.user_xid)
        .subquery()
    )
    repeat_players = int(
        (
            await DatabaseSession.execute(
                select(func.count()).select_from(repeat_subq).where(repeat_subq.c.game_count > 1),
            )
        ).scalar()
        or 0,
    )
    repeat_player_rate = round(100 * repeat_players / active_players, 1) if active_players else 0.0

    return {
        "fill_rate": fill_rate,
        "total_games": total_games,
        "active_players": active_players,
        "repeat_player_rate": repeat_player_rate,
    }


async def analytics_activity(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
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
        await DatabaseSession.execute(
            select(
                func.date(Game.started_at).label("day"),
                func.count(Game.id).label("count"),
            )
            .where(*game_filters)
            .group_by(func.date(Game.started_at))
            .order_by(text("day")),
        )
    ).all()
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
        await DatabaseSession.execute(
            select(
                func.date(Game.deleted_at).label("day"),
                func.count(Game.id).label("count"),
            )
            .where(*expired_filters)
            .group_by(func.date(Game.deleted_at))
            .order_by(text("day")),
        )
    ).all()
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
        await DatabaseSession.execute(
            select(
                func.date(User.created_at).label("day"),
                func.count(func.distinct(User.xid)).label("count"),
            )
            .select_from(User)
            .join(Play, Play.user_xid == User.xid)
            .join(Game, Play.game_id == Game.id)  # type: ignore
            .where(*new_user_filters)
            .group_by(func.date(User.created_at))
            .order_by(text("day")),
        )
    ).all()
    daily_new_users = [{"day": str(row[0]), "count": row[1]} for row in new_user_rows]

    return {
        "games_per_day": games_per_day,
        "expired_per_day": expired_per_day,
        "daily_new_users": daily_new_users,
    }


async def analytics_wait_time(
    guild_xid: int,
    *,
    all_time: bool = False,
) -> dict[str, Any]:
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
        await DatabaseSession.execute(
            select(
                func.date(Game.started_at).label("day"),
                func.avg(
                    extract("epoch", Game.started_at) - extract("epoch", Game.created_at),
                ).label("avg_seconds"),
            )
            .where(*filters)
            .group_by(func.date(Game.started_at))
            .order_by(text("day")),
        )
    ).all()
    avg_wait_per_day = [
        {"day": str(row[0]), "minutes": round(float(row[1] or 0) / 60, 1)} for row in wait_rows
    ]

    return {"avg_wait_per_day": avg_wait_per_day}


async def analytics_brackets(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
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
        await DatabaseSession.execute(
            select(  # type: ignore
                func.date(Game.started_at).label("day"),
                Game.bracket,  # type: ignore
                func.count(Game.id).label("count"),
            )
            .where(*filters)
            .group_by(func.date(Game.started_at), Game.bracket)
            .order_by(text("day")),
        )
    ).all()
    games_by_bracket_per_day = [
        {
            "day": str(row[0]),
            "bracket": str(GameBracket(row[1])),
            "count": row[2],
        }
        for row in bracket_daily_rows
    ]

    return {"games_by_bracket_per_day": games_by_bracket_per_day}


async def analytics_retention(
    guild_xid: int,
    *,
    all_time: bool = False,
) -> dict[str, Any]:
    """Return player retention data."""
    twelve_weeks_ago = datetime.now(tz=UTC) + relativedelta(weeks=-12)

    # Each player's first started game in this guild
    first_game_rows = (
        await DatabaseSession.execute(
            select(
                Play.user_xid,
                func.min(Game.started_at).label("first_game"),
            )
            .select_from(Play)
            .join(Game, Play.game_id == Game.id)  # type: ignore
            .where(
                Game.guild_xid == guild_xid,
                Game.started_at.isnot(None),
                Game.deleted_at.is_(None),
            )
            .group_by(Play.user_xid),
        )
    ).all()
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
        await DatabaseSession.execute(
            select(
                week_expr.label("week"),
                Play.user_xid,
            )
            .select_from(Play)
            .join(Game, Play.game_id == Game.id)  # type: ignore
            .where(*filters)
            .group_by(week_expr, Play.user_xid),
        )
    ).all()

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


async def analytics_growth(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
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
        select(
            func.date(func.min(Game.started_at)).label("day"),
            func.count(Play.user_xid.distinct()).label("count"),
        )
        .select_from(Play)
        .join(Game, Play.game_id == Game.id)  # type: ignore
        .where(*filters)
        .group_by(Play.user_xid)
        .subquery()
    )
    daily_new_player_rows = (
        await DatabaseSession.execute(
            select(
                growth_rows.c.day,
                func.count().label("new_players"),
            )
            .group_by(growth_rows.c.day)
            .order_by(growth_rows.c.day),
        )
    ).all()
    cumulative_players = []
    running_total = 0
    for row in daily_new_player_rows:
        running_total += row[1]
        cumulative_players.append({"day": str(row[0]), "total": running_total})

    return {"cumulative_players": cumulative_players}


async def analytics_histogram(
    guild_xid: int,
    *,
    all_time: bool = False,
) -> dict[str, Any]:
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
        await DatabaseSession.execute(
            select(
                Play.user_xid,
                func.count(Game.id).label("game_count"),
            )
            .select_from(Play)
            .join(Game, Play.game_id == Game.id)  # type: ignore
            .where(*filters)
            .group_by(Play.user_xid),
        )
    ).all()
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


async def analytics_formats(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
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
        await DatabaseSession.execute(
            select(  # type: ignore
                Game.format,  # type: ignore
                func.count(Game.id).label("count"),
            )
            .where(*filters)
            .group_by(Game.format)
            .order_by(text("count DESC"))
            .limit(10),
        )
    ).all()
    popular_formats = [{"format": str(GameFormat(row[0])), "count": row[1]} for row in format_rows]

    return {"popular_formats": popular_formats}


async def analytics_languages(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return game languages data."""
    thirty_days_ago = datetime.now(tz=UTC) + relativedelta(days=-30)

    filters = [
        Game.guild_xid == guild_xid,
        Game.started_at.isnot(None),
        Game.deleted_at.is_(None),
    ]
    if not all_time:
        filters.append(Game.started_at >= thirty_days_ago)

    locale_rows = (
        await DatabaseSession.execute(
            select(
                Game.locale,
                func.count(Game.id).label("count"),
            )
            .where(*filters)
            .group_by(Game.locale)
            .order_by(text("count DESC"))
            .limit(10),
        )
    ).all()
    top_languages = [{"locale": row[0], "count": row[1]} for row in locale_rows]

    return {"top_languages": top_languages}


async def analytics_channels(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
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
        await DatabaseSession.execute(
            select(  # type: ignore
                Channel.xid,  # type: ignore
                Channel.name,
                func.count(Game.id).label("count"),
            )
            .select_from(Channel)
            .join(Game, Game.channel_xid == Channel.xid)
            .where(*filters)
            .group_by(Channel.xid, Channel.name)
            .order_by(text("count DESC"))
            .limit(10),
        )
    ).all()
    busiest_channels = [{"name": row[1] or str(row[0]), "count": row[2]} for row in channel_rows]

    return {"busiest_channels": busiest_channels}


async def analytics_channel_players(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return unique players per channel."""
    thirty_days_ago = datetime.now(tz=UTC) + relativedelta(days=-30)

    filters = [
        Game.guild_xid == guild_xid,
        Game.started_at.isnot(None),
        Game.deleted_at.is_(None),
    ]
    if not all_time:
        filters.append(Game.started_at >= thirty_days_ago)

    # Count distinct users per channel through plays
    channel_rows = (
        await DatabaseSession.execute(
            select(  # type: ignore
                Channel.xid,  # type: ignore
                Channel.name,
                func.count(func.distinct(Play.user_xid)).label("players"),
            )
            .select_from(Channel)
            .join(Game, Game.channel_xid == Channel.xid)
            .join(Play, Play.game_id == Game.id)
            .where(*filters)
            .group_by(Channel.xid, Channel.name)
            .order_by(text("players DESC"))
            .limit(10),
        )
    ).all()

    channel_players = [{"name": row[1] or str(row[0]), "players": row[2]} for row in channel_rows]

    return {"channel_players": channel_players}


async def analytics_services(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
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
        await DatabaseSession.execute(
            select(  # type: ignore
                Game.service,  # type: ignore
                func.count(Game.id).label("count"),
            )
            .where(*filters)
            .group_by(Game.service)
            .order_by(text("count DESC"))
            .limit(10),
        )
    ).all()
    popular_services = [
        {"service": str(GameService(row[0])), "count": row[1]} for row in service_rows
    ]

    return {"popular_services": popular_services}


async def analytics_players(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
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
        await DatabaseSession.execute(
            select(
                Play.user_xid,
                User.name,
                func.count(Play.game_id).label("count"),  # type: ignore
            )
            .select_from(Play)
            .join(Game, Play.game_id == Game.id)  # type: ignore
            .join(User, User.xid == Play.user_xid)
            .join(
                GuildMember,
                and_(
                    GuildMember.user_xid == Play.user_xid,
                    GuildMember.guild_xid == guild_xid,
                ),
            )
            .where(*filters)
            .group_by(Play.user_xid, User.name)
            .order_by(text("count DESC"))
            .limit(10),
        )
    ).all()
    top_players = [
        {"user_xid": str(row[0]), "name": row[1], "count": row[2]} for row in player_rows
    ]

    return {"top_players": top_players}


async def analytics_blocked(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return top blocked players data (only players with GuildMember records)."""
    thirty_days_ago = datetime.now(tz=UTC) + relativedelta(days=-30)

    # Get users who are members of this guild
    members_in_guild = (
        select(GuildMember.user_xid).where(GuildMember.guild_xid == guild_xid).scalar_subquery()
    )

    # Count blocks for each blocked user, filtering to only guild members
    block_filters = [Block.blocked_user_xid.in_(members_in_guild)]
    if not all_time:
        block_filters.append(Block.created_at >= thirty_days_ago)  # type: ignore
    blocked_rows = (
        await DatabaseSession.execute(
            select(
                Block.blocked_user_xid,
                User.name,
                func.count(Block.user_xid).label("count"),
            )
            .select_from(Block)
            .join(User, User.xid == Block.blocked_user_xid)
            .where(*block_filters)
            .group_by(Block.blocked_user_xid, User.name)
            .order_by(text("count DESC"))
            .limit(10),
        )
    ).all()
    top_blocked = [
        {"user_xid": str(row[0]), "name": row[1], "count": row[2]} for row in blocked_rows
    ]

    return {"top_blocked": top_blocked}


async def analytics_hour_of_day(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return games per hour of the day histogram."""
    thirty_days_ago = datetime.now(tz=UTC) + relativedelta(days=-30)

    filters = [
        Game.guild_xid == guild_xid,
        Game.started_at.isnot(None),
        Game.deleted_at.is_(None),
    ]
    if not all_time:
        filters.append(Game.started_at >= thirty_days_ago)

    hour_rows = (
        await DatabaseSession.execute(
            select(
                extract("hour", Game.started_at).label("hour"),
                func.count(Game.id).label("count"),
            )
            .where(*filters)
            .group_by(text("hour"))
            .order_by(text("hour")),
        )
    ).all()

    # Build a complete 0-23 hour array
    hour_counts = {int(row[0]): row[1] for row in hour_rows}
    games_by_hour = [{"hour": h, "count": hour_counts.get(h, 0)} for h in range(24)]

    return {"games_by_hour": games_by_hour}


async def analytics_day_of_week(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return games per day of the week histogram."""
    thirty_days_ago = datetime.now(tz=UTC) + relativedelta(days=-30)

    filters = [
        Game.guild_xid == guild_xid,
        Game.started_at.isnot(None),
        Game.deleted_at.is_(None),
    ]
    if not all_time:
        filters.append(Game.started_at >= thirty_days_ago)

    # Extract day of week (0=Sunday in most SQL dialects, but varies by DB)
    # PostgreSQL: 0=Sunday, 1=Monday, ..., 6=Saturday
    dow_rows = (
        await DatabaseSession.execute(
            select(
                extract("dow", Game.started_at).label("dow"),
                func.count(Game.id).label("count"),
            )
            .where(*filters)
            .group_by(text("dow"))
            .order_by(text("dow")),
        )
    ).all()

    # Build a complete 0-6 day array (Sunday=0 to Saturday=6)
    day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    dow_counts = {int(row[0]): row[1] for row in dow_rows}
    games_by_day = [
        {"day": day_names[d], "day_num": d, "count": dow_counts.get(d, 0)} for d in range(7)
    ]

    return {"games_by_day": games_by_day}


def normalize_rule(rule: str) -> str:
    """Normalize a rule string for comparison."""
    # Lowercase, strip whitespace, remove trailing punctuation
    normalized = rule.lower().strip()
    # Remove trailing punctuation
    while normalized and normalized[-1] in ".!?,;:":
        normalized = normalized[:-1]
    # Collapse multiple spaces and return
    return " ".join(normalized.split())


def extract_ngrams(text: str, n: int) -> list[str]:
    """Extract n-grams from text."""
    words = text.lower().split()
    # Filter out very short words (1 char) but keep meaningful short words
    words = [w.strip(".,!?;:\"'()[]") for w in words]
    words = [w for w in words if len(w) > 1]
    if len(words) < n:
        return []
    return [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]


async def analytics_rules(guild_xid: int, *, all_time: bool = False) -> dict[str, Any]:
    """Return top rules and n-gram frequencies for word cloud."""
    thirty_days_ago = datetime.now(tz=UTC) + relativedelta(days=-30)

    filters = [
        Game.guild_xid == guild_xid,
        Game.started_at.isnot(None),
        Game.deleted_at.is_(None),
        Game.rules.isnot(None),
        Game.rules != "",
    ]
    if not all_time:
        filters.append(Game.started_at >= thirty_days_ago)

    rules_result = await DatabaseSession.execute(
        select(Game.rules).where(*filters),
    )
    rules_list = [row[0] for row in rules_result.all() if row[0]]

    # Count normalized full rules
    rule_counter: Counter[str] = Counter()
    for rule in rules_list:
        normalized = normalize_rule(rule)
        if normalized:
            rule_counter[normalized] += 1

    # Get top 10 rules
    top_rules = [{"rule": rule, "count": count} for rule, count in rule_counter.most_common(10)]

    # Extract bigrams and trigrams for word cloud
    ngram_counter: Counter[str] = Counter()
    for rule in rules_list:
        normalized = normalize_rule(rule)
        if normalized:
            # Add bigrams
            for bigram in extract_ngrams(normalized, 2):
                ngram_counter[bigram] += 1
            # Add trigrams
            for trigram in extract_ngrams(normalized, 3):
                ngram_counter[trigram] += 1

    # Get top 50 n-grams for word cloud
    rule_ngrams = [
        {"phrase": phrase, "count": count} for phrase, count in ngram_counter.most_common(50)
    ]

    return {"top_rules": top_rules, "rule_ngrams": rule_ngrams}
