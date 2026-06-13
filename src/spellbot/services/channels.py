from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import delete
from sqlalchemy import select as sa_select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import update

from spellbot import audit
from spellbot.database import DatabaseSession
from spellbot.environment import running_in_pytest
from spellbot.models import Channel, web_editable_columns

if TYPE_CHECKING:
    from discord.abc import MessageableChannel

    from spellbot.data import ChannelData

channel_cache: dict[int, str] = {}


def is_cached(xid: int, name: str) -> bool:  # pragma: no cover
    """Return True if the channel xid is in the local name cache under the given name."""
    if running_in_pytest():
        return False
    return bool((cached_name := channel_cache.get(xid)) and cached_name == name)


async def upsert(channel: MessageableChannel) -> ChannelData:
    """Upsert the given Discord channel into the database."""
    assert channel.guild is not None
    name_max_len = Channel.name.property.columns[0].type.length
    raw_name = getattr(channel, "name", "")
    name = raw_name[:name_max_len]
    if not is_cached(channel.id, name):  # pragma: no branch (caching disabled in tests)
        values = {
            "xid": channel.id,
            "guild_xid": channel.guild.id,
            "name": name,
            "updated_at": datetime.now(tz=UTC),
        }
        upsert = insert(Channel).values(**values)
        upsert = upsert.on_conflict_do_update(
            index_elements=[Channel.xid],  # type: ignore
            index_where=Channel.xid == values["xid"],
            set_={
                "name": upsert.excluded.name,
                "updated_at": upsert.excluded.updated_at,
            },
            where=upsert.excluded.name != Channel.name,
        )
        await DatabaseSession.execute(upsert, values)
        await DatabaseSession.commit()
        channel_cache[channel.id] = name

    result = await DatabaseSession.execute(
        sa_select(Channel).where(Channel.xid == channel.id),  # type: ignore
    )
    db_channel = result.scalar_one()
    return db_channel.to_data()


async def forget(xid: int) -> None:
    """Delete the channel with the given xid from the database."""
    query = (
        delete(Channel)
        .where(Channel.xid == xid)  # type: ignore
        .execution_options(synchronize_session=False)
    )
    # Record the deletion in one actor-attributed transaction so the audit triggers capture it.
    async with audit.transaction():
        await DatabaseSession.execute(query)
    channel_cache.pop(xid, None)


async def select(xid: int) -> ChannelData | None:
    """Fetch the channel data for the given xid."""
    result = await DatabaseSession.execute(sa_select(Channel).where(Channel.xid == xid))  # type: ignore
    channel = result.scalar_one_or_none()
    return channel.to_data() if channel else None


async def _set_column(xid: int, **values: object) -> None:
    """Update the given columns on the channel with the given xid."""
    query = (
        update(Channel)
        .where(Channel.xid == xid)  # type: ignore
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    # Record the change in one actor-attributed transaction so the audit triggers capture it.
    async with audit.transaction():
        await DatabaseSession.execute(query)


# Channel columns that guild moderators may edit from the web admin panel, derived from
# the `[web-editable]` marker on each column's `doc`. This is an allow-list so that
# protected/internal columns (xid, name, guild_xid, ...) can never be written by
# smuggling them through the form payload.
SETTINGS_FIELDS = web_editable_columns(Channel)


async def update_settings(xid: int, **fields: object) -> None:
    """Update an allow-listed subset of this channel's configurable settings."""
    safe = {key: value for key, value in fields.items() if key in SETTINGS_FIELDS}
    if not safe:
        return
    await _set_column(xid, **safe)
