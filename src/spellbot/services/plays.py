# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.sql.expression import and_, extract, func, text

from spellbot.database import DatabaseSession
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.models import Channel, Game, Guild, Play, User

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from sqlalchemy.sql import ColumnElement


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


def build_user_records_count_sql(opts: RecordFilters) -> tuple[str, dict[str, Any]]:
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


def build_channel_records_count_sql(opts: RecordFilters) -> tuple[str, dict[str, Any]]:
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
        (await DatabaseSession.execute(select(Play).where(Play.game_id == game_id))).scalars().all()
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


def record_row(
    row: Sequence[Any],
    *,
    guild_xid: int,
    channel_xid: int,
    guild_name: str | None,
    channel_name: str | None,
) -> dict[str, Any]:
    """
    Shape one game record for the records pages and exports.

    `row` holds the game's own columns: id, updated_at, message, link, format, service, seats,
    bracket, locale, and scores.
    """
    game_id, updated_at, message_xid, link, format, service, seats, bracket, locale, scores = row
    return {
        "id": game_id,
        "updated_at": updated_at.replace(tzinfo=UTC).timestamp() * 1000,
        "guild": guild_xid,
        "channel": channel_xid,
        "message": message_xid,
        "link": link,
        "format": str(GameFormat(format)),
        "service": str(GameService(service)),
        "seats": seats,
        "bracket": str(GameBracket(bracket)),
        "locale": locale,
        "guild_name": guild_name,
        "channel_name": channel_name,
        "scores": make_scores(scores),
    }


def user_record_row(row: Sequence[Any]) -> dict[str, Any]:
    """Shape a row of the user records query, which carries each game's guild and channel."""
    return record_row(
        (*row[:2], *row[4:11], row[13]),
        guild_xid=row[2],
        channel_xid=row[3],
        guild_name=row[11],
        channel_name=row[12],
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
    if not await user_exists(user_xid):
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
    return [user_record_row(row) for row in rows], total


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
    guild or channel is unknown, or the channel isn't in the guild.
    """
    guild = (
        await DatabaseSession.execute(select(Guild).where(Guild.xid == guild_xid))
    ).scalar_one_or_none()
    if not guild:
        return None
    channel = (
        await DatabaseSession.execute(
            select(Channel).where(channel_in_guild(guild_xid, channel_xid)),
        )
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
        record_row(
            row,
            guild_xid=guild_xid,
            channel_xid=channel_xid,
            guild_name=guild.name,
            channel_name=channel.name,
        )
        for row in rows
    ]
    return decomposed(combined_data), total


async def user_exists(user_xid: int) -> bool:
    """Return True if the user exists."""
    return (
        await DatabaseSession.execute(select(User.xid).where(User.xid == user_xid))
    ).scalar_one_or_none() is not None


async def user_export_target_exists(user_xid: int) -> bool:
    """Return True if the user for a user-records export exists."""
    return await user_exists(user_xid)


def channel_in_guild(guild_xid: int, channel_xid: int) -> ColumnElement[bool]:
    """Filter for the channel `channel_xid`, matching only when it belongs to `guild_xid`."""
    return and_(Channel.xid == channel_xid, Channel.guild_xid == guild_xid)


async def channel_export_target_exists(guild_xid: int, channel_xid: int) -> bool:
    """Return True if the guild exists and the channel exists within it."""
    if not await guild_exists(guild_xid):
        return False
    return (
        await DatabaseSession.execute(
            select(Channel.xid).where(channel_in_guild(guild_xid, channel_xid)),
        )
    ).scalar_one_or_none() is not None


async def stream_user_records(user_xid: int) -> AsyncIterator[dict[str, Any]]:
    """Stream all game records for a user across all guilds without pagination."""
    if not await user_exists(user_xid):
        return

    result = await DatabaseSession.execute(
        text(USER_RECORDS_EXPORT_SQL),
        {"user_xid": user_xid},
    )
    for row in result:
        yield user_record_row(row)


async def stream_channel_records(
    guild_xid: int,
    channel_xid: int,
) -> AsyncIterator[dict[str, Any]]:
    """Stream all game records for a channel without pagination, one row per player."""
    guild_name = (
        await DatabaseSession.execute(select(Guild.name).where(Guild.xid == guild_xid))
    ).scalar_one_or_none()
    if guild_name is None:
        return
    channel_name = (
        await DatabaseSession.execute(
            select(Channel.name).where(channel_in_guild(guild_xid, channel_xid)),
        )
    ).scalar_one_or_none()
    if channel_name is None:
        return

    result = await DatabaseSession.execute(
        text(CHANNEL_RECORDS_EXPORT_SQL),
        {"guild_xid": guild_xid, "channel_xid": channel_xid},
    )
    for row in result:
        combined = record_row(
            row,
            guild_xid=guild_xid,
            channel_xid=channel_xid,
            guild_name=guild_name,
            channel_name=channel_name,
        )
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
        today = datetime.now(tz=UTC).date()
        year, month_index = divmod(today.year * 12 + today.month - 1 - ago, 12)
        filters.append(extract("year", Game.started_at) == year)
        filters.append(extract("month", Game.started_at) == month_index + 1)
    result = await DatabaseSession.execute(
        select(
            Play.user_xid,
            func.count(Play.game_id).label("count"),
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
        await DatabaseSession.execute(select(Guild).where(Guild.xid == guild_xid))
    ).scalar_one_or_none() is not None


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
