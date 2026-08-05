from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, update

from spellbot.database import DatabaseSession, any_of
from spellbot.models import WebAction, WebActionStatus

if TYPE_CHECKING:
    from collections.abc import Iterable

    from spellbot.data import WebActionData


async def enqueue(
    *,
    user_xid: int,
    guild_xid: int,
    channel_xid: int,
    kind: str,
    locale: str,
    game_id: int | None = None,
    params: dict[str, Any] | None = None,
) -> WebActionData:
    """Record a website request for the bot to carry out, and return it."""
    action = WebAction(
        user_xid=user_xid,
        guild_xid=guild_xid,
        channel_xid=channel_xid,
        kind=kind,
        locale=locale,
        game_id=game_id,
        params=params or {},
        status=WebActionStatus.PENDING.value,
        notices=[],
    )
    DatabaseSession.add(action)
    await DatabaseSession.commit()
    return action.to_data()


async def get(action_id: int, *, user_xid: int) -> WebActionData | None:
    """
    Fetch one action by id, scoped to the user who requested it.

    Scoping by `user_xid` is what keeps the status endpoint from becoming an
    enumeration oracle over other people's requests.
    """
    stmt = select(WebAction).where(
        WebAction.id == action_id,
        WebAction.user_xid == user_xid,
    )
    result = await DatabaseSession.execute(stmt)
    action: WebAction | None = result.scalar_one_or_none()
    return action.to_data() if action else None


async def claim(guild_xids: Iterable[int], *, limit: int = 10) -> list[WebActionData]:
    """
    Claim up to `limit` pending actions for the given guilds, marking them running.

    Uses `FOR UPDATE SKIP LOCKED` so that several bot processes (or shards) can poll the
    same table concurrently without handing the same request to two workers. Restricting
    to `guild_xids` — the guilds this process is actually connected to — is what makes a
    sharded deployment route each request to a process that can act on it.
    """
    xids = list(guild_xids)
    if not xids:
        return []
    candidates = (
        select(WebAction.id)
        .where(
            WebAction.status == WebActionStatus.PENDING.value,
            any_of(WebAction.guild_xid, xids),
        )
        .order_by(WebAction.created_at.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    stmt = (
        update(WebAction)
        .where(WebAction.id.in_(candidates))
        .values(status=WebActionStatus.RUNNING.value, updated_at=datetime.now(tz=UTC))
        .returning(WebAction)
    )
    result = await DatabaseSession.execute(stmt)
    actions = list(result.scalars().all())
    await DatabaseSession.commit()
    return [action.to_data() for action in actions]


async def resolve(
    action_id: int,
    *,
    error_code: str | None = None,
    game_id: int | None = None,
    notices: list[str] | None = None,
) -> None:
    """Mark an action finished, recording why it failed and anything it wants to say."""
    values: dict[str, Any] = {
        "status": WebActionStatus.ERROR.value if error_code else WebActionStatus.DONE.value,
        "error_code": error_code,
        "resolved_at": datetime.now(tz=UTC),
        "updated_at": datetime.now(tz=UTC),
    }
    if game_id is not None:
        values["game_id"] = game_id
    if notices is not None:
        values["notices"] = notices
    await DatabaseSession.execute(
        update(WebAction).where(WebAction.id == action_id).values(**values),
    )
    await DatabaseSession.commit()


async def expire_stale(older_than: timedelta, error_code: str) -> int:
    """
    Fail actions left unclaimed or unfinished for too long, returning how many.

    Without this a request made while the bot is down would spin on the website
    forever. Rows stuck in `running` are swept too, since a worker that crashed
    mid-action will never come back to resolve its claim.
    """
    cutoff = datetime.now(tz=UTC) - older_than
    stmt = (
        update(WebAction)
        .where(
            any_of(
                WebAction.status,
                [WebActionStatus.PENDING.value, WebActionStatus.RUNNING.value],
            ),
            WebAction.created_at <= cutoff,
        )
        .values(
            status=WebActionStatus.ERROR.value,
            error_code=error_code,
            resolved_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
    )
    result = await DatabaseSession.execute(stmt)
    await DatabaseSession.commit()
    return result.rowcount or 0
