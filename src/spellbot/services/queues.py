from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select

from spellbot.database import DatabaseSession
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.models import Channel, Game, Guild, GuildMember, Play, Post, Queue

FORMAT_LABEL = case(
    *((Game.format == f.value, str(f)) for f in GameFormat),
    else_="Unknown",
).label("format")

BRACKET_LABEL = case(
    *((Game.bracket == b.value, str(b)) for b in GameBracket),
    else_="Unknown",
).label("bracket")

SERVICE_LABEL = case(
    *((Game.service == s.value, s.title) for s in GameService),
    else_="Unknown",
).label("service")


async def public_recent_started_count(
    within: timedelta,
    *,
    only_member_of: int | None = None,
    only_mythic_track: bool = False,
) -> int:
    """
    Count games started within `within` of now, excluding banned or unpromoted guilds.

    When `only_member_of` is provided, the count is restricted to guilds where the
    given user xid has a `guild_members` row.

    When `only_mythic_track` is `True`, the count is further restricted to guilds that
    have mythic track enabled.
    """
    cutoff = datetime.now(UTC) - within
    stmt = (
        select(func.count(Game.id))
        .select_from(Game)
        .join(Guild, Guild.xid == Game.guild_xid)  # type: ignore
        .where(
            Game.started_at.is_not(None),
            Game.started_at >= cutoff,
            Game.deleted_at.is_(None),
            Guild.banned.is_(False),
            Guild.promote.is_(True),
        )
    )
    if only_member_of is not None:
        stmt = stmt.join(
            GuildMember,
            GuildMember.guild_xid == Guild.xid,
        ).where(GuildMember.user_xid == only_member_of)
    if only_mythic_track:
        stmt = stmt.where(Guild.enable_mythic_track.is_(True))
    result = await DatabaseSession.execute(stmt)
    return int(result.scalar() or 0)


async def public_active_games(
    within: timedelta,
    *,
    only_member_of: int | None = None,
    only_mythic_track: bool = False,
) -> list[dict[str, Any]]:
    """
    Return rows for games started within `within` of now, ordered newest first.

    The visibility, `only_member_of`, and `only_mythic_track` rules mirror
    `public_active_queues`.
    """
    cutoff = datetime.now(UTC) - within
    stmt = (
        select(
            Game.id,
            Game.guild_xid,
            Guild.name.label("guild_name"),
            Guild.locale.label("guild_locale"),
            Guild.icon.label("guild_icon"),
            Game.channel_xid,  # type: ignore
            FORMAT_LABEL,
            BRACKET_LABEL,
            SERVICE_LABEL,
            Game.seats,  # type: ignore
            Game.started_at,
        )
        .select_from(Game)
        .join(Guild, Guild.xid == Game.guild_xid)  # type: ignore
        .where(
            Game.started_at.is_not(None),
            Game.started_at >= cutoff,
            Game.deleted_at.is_(None),
            Guild.banned.is_(False),
            Guild.promote.is_(True),
        )
        .order_by(Game.started_at.desc())
    )
    if only_member_of is not None:
        stmt = stmt.join(
            GuildMember,
            GuildMember.guild_xid == Guild.xid,
        ).where(GuildMember.user_xid == only_member_of)
    if only_mythic_track:
        stmt = stmt.where(Guild.enable_mythic_track.is_(True))
    rows = (await DatabaseSession.execute(stmt)).all()
    if not rows:
        return []

    now = datetime.now(UTC)
    out: list[dict[str, Any]] = []
    for row in rows:
        guild_xid_int = int(row[1])
        channel_xid = str(int(row[5]))
        out.append(
            {
                "guild_xid": guild_xid_int,
                "guild_name": row[2] or "",
                "guild_locale": row[3] or "en",
                "guild_icon": row[4],
                "format": row[6],
                "bracket": row[7],
                "service": row[8],
                "seats": int(row[9]),
                "started_seconds_ago": max(
                    0,
                    int((now - row[10].replace(tzinfo=UTC)).total_seconds()),
                ),
                "jump_url": f"https://discord.com/channels/{guild_xid_int}/{channel_xid}",
            },
        )
    return out


async def public_active_queues(
    *,
    only_member_of: int | None = None,
    only_mythic_track: bool = False,
) -> list[dict[str, Any]]:
    """
    Return rows for pending queues, optionally limited to a user's guild memberships.

    When `only_mythic_track` is `True`, results are further restricted to guilds that
    have mythic track enabled.
    """
    players_col = func.count(Queue.user_xid).label("players")
    stmt = (
        select(
            Game.id,
            Game.guild_xid,
            Guild.name.label("guild_name"),
            Guild.locale.label("guild_locale"),
            Guild.icon.label("guild_icon"),
            Game.channel_xid,  # type: ignore
            FORMAT_LABEL,
            BRACKET_LABEL,
            SERVICE_LABEL,
            Game.seats,  # type: ignore
            Game.created_at,
            players_col,
        )
        .select_from(Game)
        .join(Queue, Queue.game_id == Game.id)
        .join(Guild, Guild.xid == Game.guild_xid)  # type: ignore
        .where(
            Game.started_at.is_(None),
            Game.deleted_at.is_(None),
            Guild.banned.is_(False),
            Guild.promote.is_(True),
        )
    )
    if only_member_of is not None:
        stmt = stmt.join(
            GuildMember,
            GuildMember.guild_xid == Guild.xid,
        ).where(GuildMember.user_xid == only_member_of)
    if only_mythic_track:
        stmt = stmt.where(Guild.enable_mythic_track.is_(True))
    rows = (
        await DatabaseSession.execute(
            stmt.group_by(
                Game.id,
                Game.guild_xid,
                Guild.name,
                Guild.locale,
                Guild.icon,
                Game.channel_xid,  # type: ignore
                Game.format,  # type: ignore
                Game.bracket,  # type: ignore
                Game.service,  # type: ignore
                Game.seats,  # type: ignore
                Game.created_at,
            ).order_by(Game.created_at.desc()),
        )
    ).all()
    if not rows:
        return []

    game_ids = [row[0] for row in rows]
    post_rows = (
        await DatabaseSession.execute(
            select(Post.game_id, Post.message_xid)
            .where(Post.game_id.in_(game_ids))
            .order_by(Post.game_id, Post.created_at.desc()),
        )
    ).all()
    message_xid_by_game: dict[int, int] = {}
    for game_id, message_xid in post_rows:
        message_xid_by_game.setdefault(int(game_id), int(message_xid))

    now = datetime.now(UTC)
    out: list[dict[str, Any]] = []
    for row in rows:
        guild_xid_int = int(row[1])
        guild_xid = str(guild_xid_int)
        channel_xid = str(int(row[5]))
        message_xid = message_xid_by_game.get(int(row[0]))
        if message_xid is not None:
            jump_url = f"https://discord.com/channels/{guild_xid}/{channel_xid}/{message_xid}"
        else:
            jump_url = f"https://discord.com/channels/{guild_xid}/{channel_xid}"
        out.append(
            {
                "guild_xid": guild_xid_int,
                "guild_name": row[2] or "",
                "guild_locale": row[3] or "en",
                "guild_icon": row[4],
                "format": row[6],
                "bracket": row[7],
                "service": row[8],
                "players": int(row[11]),
                "seats": int(row[9]),
                "wait_seconds": max(
                    0,
                    int((now - row[10].replace(tzinfo=UTC)).total_seconds()),
                ),
                "jump_url": jump_url,
            }
        )
    return out


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
    games_played = func.count(Play.game_id).label("games_played")  # type: ignore
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
        .join(Guild, Guild.xid == Game.guild_xid)  # type: ignore
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
            Channel.xid,  # type: ignore
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
        .order_by(Channel.name.asc(), Channel.xid.asc())  # type: ignore
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
        Guild.xid,  # type: ignore
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
