from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.sql.expression import and_, not_, or_
from sqlalchemy.sql.expression import cast as sa_cast

from spellbot.database import DatabaseSession
from spellbot.models import Alert, Game, GameStatus, Queue, User

if TYPE_CHECKING:
    from collections.abc import Iterable

    from spellbot.data import AlertData

ACTIVE_HOURS_MAX_LENGTH = 8


def parse_active_hours(raw: Any) -> dict[str, Any] | None:
    """
    Validate and canonicalize an active_hours payload.

    Returns None when `raw` is falsy. Raises ValueError for any structural or
    semantic problem (out-of-range hours, equal start/end, range exceeding
    `ACTIVE_HOURS_MAX_LENGTH`, unknown timezone).
    """
    if not raw:
        return None
    if not isinstance(raw, dict):
        msg = "active_hours must be an object"
        raise ValueError(msg)  # noqa: TRY004
    try:
        start = int(raw["start"])
        end = int(raw["end"])
        tz_name = str(raw["tz"])
    except (KeyError, TypeError, ValueError) as ex:
        msg = "active_hours requires integer start/end and tz"
        raise ValueError(msg) from ex
    if not (0 <= start <= 23) or not (0 <= end <= 23):
        msg = "active_hours start/end must be between 0 and 23"
        raise ValueError(msg)
    if start == end:
        msg = "active_hours start and end must differ"
        raise ValueError(msg)
    length = (end - start) % 24
    if length > ACTIVE_HOURS_MAX_LENGTH:
        msg = f"active_hours range must be {ACTIVE_HOURS_MAX_LENGTH} hours or less"
        raise ValueError(msg)
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError) as ex:
        msg = f"invalid timezone: {tz_name}"
        raise ValueError(msg) from ex
    return {"start": start, "end": end, "tz": tz_name}


def is_within_active_hours(active_hours: Any, now_utc: datetime) -> bool:
    """Return whether `now_utc` falls within the user's active window."""
    if not active_hours or not isinstance(active_hours, dict):
        return True
    try:
        tz = ZoneInfo(str(active_hours["tz"]))
        start = int(active_hours["start"])
        end = int(active_hours["end"])
    except KeyError, TypeError, ValueError, ZoneInfoNotFoundError:
        return True
    if start == end:
        return True
    local_hour = now_utc.astimezone(tz).hour
    if start < end:
        return start <= local_hour < end
    return local_hour >= start or local_hour < end


async def upsert(
    guild_xid: int,
    user_xid: int,
    *,
    formats: Iterable[int] = (),
    brackets: Iterable[int] = (),
    channels: Iterable[int] = (),
    active_hours: dict[str, Any] | None = None,
) -> AlertData:
    """Create or update the notification preferences for a user in a guild."""
    preferences: dict[str, Any] = {
        "formats": sorted({int(v) for v in formats}),
        "brackets": sorted({int(v) for v in brackets}),
        "channels": sorted({int(v) for v in channels}),
    }
    if active_hours is not None:
        preferences["active_hours"] = parse_active_hours(active_hours)
    stmt = insert(Alert).values(
        guild_xid=guild_xid,
        user_xid=user_xid,
        preferences=preferences,
        deleted_at=None,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_alerts_guild_user",
        set_={"preferences": stmt.excluded.preferences, "deleted_at": None},
    )
    await DatabaseSession.execute(stmt)
    await DatabaseSession.commit()
    result = await DatabaseSession.execute(
        select(Alert).where(
            and_(
                Alert.guild_xid == guild_xid,
                Alert.user_xid == user_xid,
                Alert.deleted_at.is_(None),
            ),
        ),
    )
    record = result.scalar_one()
    return record.to_data()


async def get_for_user_guild(
    guild_xid: int,
    user_xid: int,
    *,
    include_deleted: bool = False,
) -> AlertData | None:
    """
    Return the alert preferences for a user in a guild, if any.

    By default soft-deleted alerts are excluded. Pass `include_deleted=True` to
    retrieve a previously turned-off alert so its preferences can be restored.
    """
    clauses = [Alert.guild_xid == guild_xid, Alert.user_xid == user_xid]
    if not include_deleted:
        clauses.append(Alert.deleted_at.is_(None))
    result = await DatabaseSession.execute(select(Alert).where(and_(*clauses)))
    record = result.scalar_one_or_none()
    if record is None:
        return None
    return record.to_data()


async def get_guild_xids_for_user(user_xid: int) -> set[int]:
    """Return the set of guild xids the user has notification preferences for."""
    result = await DatabaseSession.execute(
        select(Alert.guild_xid).where(Alert.user_xid == user_xid, Alert.deleted_at.is_(None)),
    )
    return {int(row[0]) for row in result}


async def delete(guild_xid: int, user_xid: int) -> bool:
    """
    Soft delete the notification preferences for a user in a guild.

    Only active (non-deleted) rows are touched, so the preference payload is
    preserved and can be restored later by calling `upsert` again. Returns
    True if an active row was soft deleted, False if no active preferences
    existed (either never created or already turned off).
    """
    query = (
        update(Alert)
        .where(
            and_(
                Alert.guild_xid == guild_xid,
                Alert.user_xid == user_xid,
                Alert.deleted_at.is_(None),
            ),
        )
        .values(deleted_at=datetime.now(tz=UTC))
    )
    result = await DatabaseSession.execute(query)
    await DatabaseSession.commit()
    return bool(result.rowcount != 0)


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
        select(Alert)
        .join(User, User.xid == Alert.user_xid)
        .where(
            and_(
                Alert.deleted_at.is_(None),
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
    now_utc = datetime.now(tz=UTC)
    return [
        int(alert.user_xid)
        for alert in result.scalars()
        if is_within_active_hours((alert.preferences or {}).get("active_hours"), now_utc)
    ]


async def mark_notified(game_id: int) -> None:
    """Record that the notification pass has completed for a game."""
    await DatabaseSession.execute(
        update(Game).where(Game.id == game_id).values(notified_at=datetime.now(tz=UTC)),
    )
    await DatabaseSession.commit()
