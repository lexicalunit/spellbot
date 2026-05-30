from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.sql.expression import and_, not_, or_
from sqlalchemy.sql.expression import cast as sa_cast

from spellbot.database import DatabaseSession
from spellbot.models import Alert, Game, GameStatus, Queue, User

if TYPE_CHECKING:
    from collections.abc import Iterable

    from spellbot.data import AlertData


async def upsert(
    guild_xid: int,
    user_xid: int,
    *,
    formats: Iterable[int] = (),
    brackets: Iterable[int] = (),
    channels: Iterable[int] = (),
) -> AlertData:
    """Create or update the notification preferences for a user in a guild."""
    preferences = {
        "formats": sorted({int(v) for v in formats}),
        "brackets": sorted({int(v) for v in brackets}),
        "channels": sorted({int(v) for v in channels}),
    }
    stmt = insert(Alert).values(
        guild_xid=guild_xid,
        user_xid=user_xid,
        preferences=preferences,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_alerts_guild_user",
        set_={"preferences": stmt.excluded.preferences},
    )
    await DatabaseSession.execute(stmt)
    await DatabaseSession.commit()
    result = await DatabaseSession.execute(
        select(Alert).where(
            and_(Alert.guild_xid == guild_xid, Alert.user_xid == user_xid),
        ),
    )
    record = result.scalar_one()
    return record.to_data()


async def get_for_user_guild(guild_xid: int, user_xid: int) -> AlertData | None:
    """Return the alert preferences for a user in a guild, if any."""
    result = await DatabaseSession.execute(
        select(Alert).where(
            and_(Alert.guild_xid == guild_xid, Alert.user_xid == user_xid),
        ),
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None
    return record.to_data()


def matches_or_empty(key: str, value: int) -> Any:
    """JSONB predicate: the preference list at key is empty or contains value."""
    column = Alert.preferences[key]
    return or_(
        func.coalesce(func.jsonb_array_length(column), 0) == 0,
        column.contains(sa_cast([value], JSONB)),
    )


async def find_matching_user_xids(
    *,
    guild_xid: int,
    format: int,
    bracket: int,
    channel_xid: int,
) -> list[int]:
    """Return user xids whose alerts match the game's format, bracket, and channel."""
    pending_queue = (
        select(Queue.user_xid)
        .join(Game, Game.id == Queue.game_id)
        .where(
            Game.status == GameStatus.PENDING.value,  # type: ignore[arg-type]
            Game.deleted_at.is_(None),
            Game.started_at.is_(None),
        )
    )
    stmt = (
        select(Alert.user_xid)
        .join(User, User.xid == Alert.user_xid)
        .where(
            and_(
                Alert.guild_xid == guild_xid,
                User.banned.is_(False),
                matches_or_empty("formats", format),
                matches_or_empty("brackets", bracket),
                matches_or_empty("channels", channel_xid),
                not_(Alert.user_xid.in_(pending_queue)),
            ),
        )
    )
    result = await DatabaseSession.execute(stmt)
    return [int(row[0]) for row in result]


async def mark_notified(game_id: int) -> None:
    """Record that the notification pass has completed for a game."""
    await DatabaseSession.execute(
        update(Game).where(Game.id == game_id).values(notified_at=datetime.now(tz=UTC)),
    )
    await DatabaseSession.commit()
