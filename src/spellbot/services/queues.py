from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select

from spellbot.database import DatabaseSession
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.models import Game, Guild, GuildMember, Post, Queue

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
) -> int:
    """
    Count games started within `within` of now, excluding banned or unpromoted guilds.

    When `only_member_of` is provided, the count is restricted to guilds where the
    given user xid has a `guild_members` row.
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
    result = await DatabaseSession.execute(stmt)
    return int(result.scalar() or 0)


async def public_active_queues(
    *,
    only_member_of: int | None = None,
) -> list[dict[str, Any]]:
    """Return rows for pending queues, optionally limited to a user's guild memberships."""
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
