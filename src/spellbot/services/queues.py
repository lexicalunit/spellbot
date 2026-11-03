# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from spellbot.database import DatabaseSession
from spellbot.models import Channel, Game, Guild, GuildMember, Play, Post, Queue
from spellbot.services.labels import BRACKET_LABEL, FORMAT_LABEL, SERVICE_LABEL

if TYPE_CHECKING:
    from sqlalchemy import Select

# How far back a started game still counts as "active". Shared by the queues page,
# `/queues.json`, and the cached public stats so all three report the same games.
STARTED_GAMES_WINDOW = timedelta(hours=2)


# The columns that describe a publicly listed game, shared by the active games and queues.
PUBLIC_GAME_COLUMNS = (
    Game.id,
    Game.guild_xid,
    Guild.name.label("guild_name"),
    Guild.locale.label("guild_locale"),
    Guild.icon.label("guild_icon"),
    Game.channel_xid,
    FORMAT_LABEL,
    BRACKET_LABEL,
    SERVICE_LABEL,
    Game.seats,
)


def publicly_visible[S: Select](
    stmt: S,
    *,
    only_member_of: int | None,
    only_mythic_track: bool,
) -> S:
    """
    Restrict a games query to guilds that allow being listed publicly.

    `only_member_of` further limits it to that user's guilds, and `only_mythic_track` to guilds
    with Mythic Track enabled.
    """
    stmt = stmt.where(Game.deleted_at.is_(None), Guild.banned.is_(False), Guild.promote.is_(True))
    if only_member_of is not None:
        stmt = stmt.join(GuildMember, GuildMember.guild_xid == Guild.xid).where(
            GuildMember.user_xid == only_member_of,
        )
    if only_mythic_track:
        stmt = stmt.where(Guild.enable_mythic_track.is_(True))
    return stmt


def seconds_since(moment: datetime, now: datetime) -> int:
    """Whole seconds from a naive UTC `moment` until `now`, never negative."""
    return max(0, int((now - moment.replace(tzinfo=UTC)).total_seconds()))


def public_game_row(row: Any, message_xid: int | None = None) -> dict[str, Any]:
    """Build the fields every publicly listed game has, with a link to its post (or channel)."""
    jump_url = f"https://discord.com/channels/{int(row.guild_xid)}/{int(row.channel_xid)}"
    if message_xid is not None:
        jump_url = f"{jump_url}/{message_xid}"
    return {
        "guild_xid": int(row.guild_xid),
        "guild_name": row.guild_name or "",
        "guild_locale": row.guild_locale or "en",
        "guild_icon": row.guild_icon,
        "format": row.format,
        "bracket": row.bracket,
        "service": row.service,
        "seats": int(row.seats),
        "jump_url": jump_url,
    }


async def public_active_games(
    within: timedelta,
    *,
    only_member_of: int | None = None,
    only_mythic_track: bool = False,
) -> list[dict[str, Any]]:
    """Return rows for games started within `within` of now, ordered newest first."""
    now = datetime.now(UTC)
    stmt = publicly_visible(
        select(*PUBLIC_GAME_COLUMNS, Game.started_at)
        .select_from(Game)
        .join(Guild, Guild.xid == Game.guild_xid)
        .where(Game.started_at.is_not(None), Game.started_at >= now - within)
        .order_by(Game.started_at.desc()),
        only_member_of=only_member_of,
        only_mythic_track=only_mythic_track,
    )
    rows = (await DatabaseSession.execute(stmt)).all()
    return [
        public_game_row(row) | {"started_seconds_ago": seconds_since(row.started_at, now)}
        for row in rows
    ]


async def public_active_queues(
    *,
    only_member_of: int | None = None,
    only_mythic_track: bool = False,
) -> list[dict[str, Any]]:
    """Return rows for pending queues, newest first, linking to each game's latest post."""
    players_col = func.count(Queue.user_xid).label("players")
    stmt = publicly_visible(
        select(*PUBLIC_GAME_COLUMNS, Game.created_at, players_col)
        .select_from(Game)
        .join(Queue, Queue.game_id == Game.id)
        .join(Guild, Guild.xid == Game.guild_xid)
        .where(Game.started_at.is_(None)),
        only_member_of=only_member_of,
        only_mythic_track=only_mythic_track,
    )
    rows = (
        await DatabaseSession.execute(
            stmt.group_by(Game.id, Guild.xid).order_by(Game.created_at.desc()),
        )
    ).all()
    if not rows:
        return []

    post_rows = (
        await DatabaseSession.execute(
            select(Post.game_id, Post.message_xid)
            .where(Post.game_id.in_([row.id for row in rows]))
            .order_by(Post.game_id, Post.created_at.desc()),
        )
    ).all()
    message_xid_by_game: dict[int, int] = {}
    for game_id, message_xid in post_rows:
        message_xid_by_game.setdefault(int(game_id), int(message_xid))

    now = datetime.now(UTC)
    return [
        public_game_row(row, message_xid_by_game.get(int(row.id)))
        | {"players": int(row.players), "wait_seconds": seconds_since(row.created_at, now)}
        for row in rows
    ]


async def viewer_played_guilds(
    user_xid: int,
    *,
    played_within: timedelta | None = None,
) -> list[dict[str, Any]]:
    """
    Return the guilds the given user has played at least one game in.

    Each row carries the guild name, locale, cached icon, a count of plays in
    that guild, and the earliest and latest play timestamps. Banned and
    unpromoted guilds are excluded. When `played_within` is provided, guilds
    whose most recent play is older than the window are excluded (the
    aggregated counts and timestamps still cover the full history). Results
    are ordered by most-recent play first.
    """
    games_played = func.count(Play.game_id).label("games_played")
    first_played_at = func.min(Play.created_at).label("first_played_at")
    last_played_at = func.max(Play.created_at).label("last_played_at")
    stmt = (
        select(
            Game.guild_xid,
            Guild.name.label("guild_name"),
            Guild.locale.label("guild_locale"),
            Guild.icon.label("guild_icon"),
            games_played,
            first_played_at,
            last_played_at,
        )
        .select_from(Play)
        .join(Game, Game.id == Play.game_id)
        .join(Guild, Guild.xid == Game.guild_xid)
        .where(
            Play.user_xid == user_xid,
            Guild.banned.is_(False),
            Guild.promote.is_(True),
        )
        .group_by(
            Game.guild_xid,
            Guild.name,
            Guild.locale,
            Guild.icon,
        )
        .order_by(last_played_at.desc())
    )
    if played_within is not None:
        cutoff = datetime.now(tz=UTC) - played_within
        stmt = stmt.having(last_played_at >= cutoff)
    rows = (await DatabaseSession.execute(stmt)).all()
    return [
        {
            "guild_xid": int(row[0]),
            "guild_name": row[1] or "",
            "guild_locale": row[2] or "en",
            "guild_icon": row[3],
            "games_played": int(row[4]),
            "first_played_at": row[5].replace(tzinfo=UTC) if row[5] is not None else None,
            "last_played_at": row[6].replace(tzinfo=UTC) if row[6] is not None else None,
        }
        for row in rows
    ]


async def viewer_played_channels(
    user_xid: int,
    guild_xid: int,
    *,
    played_within: timedelta | None = None,
) -> list[dict[str, Any]]:
    """
    Return distinct channels the given user has played at least one game in for `guild_xid`.

    Rows are sorted by channel name (then xid) and carry the channel's external
    Discord ID and most-recently cached name. When `played_within` is provided,
    channels whose most recent play by the user is older than the window are
    excluded.
    """
    last_played_at = func.max(Play.created_at).label("last_played_at")
    stmt = (
        select(
            Channel.xid,
            Channel.name,
            last_played_at,
        )
        .select_from(Play)
        .join(Game, Game.id == Play.game_id)
        .join(Channel, Channel.xid == Game.channel_xid)
        .where(
            Play.user_xid == user_xid,
            Game.guild_xid == guild_xid,
        )
        .group_by(Channel.xid, Channel.name)
        .order_by(Channel.name.asc(), Channel.xid.asc())
    )
    if played_within is not None:
        cutoff = datetime.now(tz=UTC) - played_within
        stmt = stmt.having(last_played_at >= cutoff)
    rows = (await DatabaseSession.execute(stmt)).all()
    return [
        {
            "channel_xid": int(row[0]),
            "channel_name": row[1] or "",
        }
        for row in rows
    ]


async def guild_summary(guild_xid: int) -> dict[str, Any] | None:
    """Return basic public guild fields for the notification preferences page."""
    stmt = select(
        Guild.xid,
        Guild.name,
        Guild.locale,
        Guild.icon,
    ).where(
        Guild.xid == guild_xid,
        Guild.banned.is_(False),
        Guild.promote.is_(True),
    )
    row = (await DatabaseSession.execute(stmt)).first()
    if row is None:
        return None
    return {
        "guild_xid": int(row[0]),
        "guild_name": row[1] or "",
        "guild_locale": row[2] or "en",
        "guild_icon": row[3],
    }
