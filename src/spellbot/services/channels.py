# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import delete
from sqlalchemy import select as sa_select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import update

from spellbot import audit
from spellbot.data import ChannelData
from spellbot.database import DatabaseSession
from spellbot.environment import running_in_pytest
from spellbot.models import Channel, column_length, web_editable_columns

if TYPE_CHECKING:
    from discord.abc import MessageableChannel


channel_cache: dict[int, str] = {}


def is_cached(xid: int, name: str) -> bool:
    """Return True if the channel xid is in the local name cache under the given name."""
    if running_in_pytest():
        return False
    return bool((cached_name := channel_cache.get(xid)) and cached_name == name)


async def write(channel: MessageableChannel, name: str) -> None:
    """Insert or update the given Discord channel's row and cache its name."""
    assert channel.guild is not None
    values = {
        "xid": channel.id,
        "guild_xid": channel.guild.id,
        "name": name,
        "updated_at": datetime.now(tz=UTC),
    }
    upsert = insert(Channel).values(**values)
    upsert = upsert.on_conflict_do_update(
        index_elements=[Channel.xid],
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


async def upsert(channel: MessageableChannel) -> ChannelData:
    """Upsert the given Discord channel into the database."""
    assert channel.guild is not None
    name_max_len = column_length(Channel.name)
    raw_name = getattr(channel, "name", "")
    name = raw_name[:name_max_len]
    if not is_cached(channel.id, name):
        await write(channel, name)

    query = sa_select(Channel).where(Channel.xid == channel.id)
    db_channel = (await DatabaseSession.execute(query)).scalar_one_or_none()
    if db_channel is None:
        # The cache is per process, so another process (e.g. the web app forgetting this
        # channel) may have deleted the row after we cached it. Write it again.
        await write(channel, name)
        db_channel = (await DatabaseSession.execute(query)).scalar_one()
    return ChannelData.from_model(db_channel)


async def forget(guild_xid: int, xid: int) -> None:
    """Delete the channel with the given xid from the database, if it belongs to the guild."""
    query = (
        delete(Channel)
        .where(Channel.xid == xid, Channel.guild_xid == guild_xid)
        .execution_options(synchronize_session=False)
    )
    # Record the deletion in one actor-attributed transaction so the audit triggers capture it.
    async with audit.transaction():
        await DatabaseSession.execute(query)
    channel_cache.pop(xid, None)


async def select(xid: int) -> ChannelData | None:
    """Fetch the channel data for the given xid."""
    result = await DatabaseSession.execute(sa_select(Channel).where(Channel.xid == xid))
    channel = result.scalar_one_or_none()
    return ChannelData.from_model(channel) if channel else None


async def in_guild(guild_xid: int, xid: int) -> bool:
    """Return True if the channel with the given xid is known and belongs to the guild."""
    result = await DatabaseSession.execute(
        sa_select(Channel.xid).where(Channel.xid == xid, Channel.guild_xid == guild_xid),
    )
    return result.scalar_one_or_none() is not None


async def set_column(guild_xid: int, xid: int, **values: object) -> None:
    """Update the given columns on the channel with the given xid, if it belongs to the guild."""
    query = (
        update(Channel)
        .where(Channel.xid == xid, Channel.guild_xid == guild_xid)
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


async def update_settings(guild_xid: int, xid: int, /, **fields: object) -> None:
    """
    Update an allow-listed subset of this channel's configurable settings.

    Only a channel belonging to `guild_xid` is changed, so a moderator of one guild can't
    reach another guild's channel by its id. The ids are positional-only so that a
    `guild_xid` smuggled in with the fields lands in `fields`, where the allow-list drops it.
    """
    safe = {key: value for key, value in fields.items() if key in SETTINGS_FIELDS}
    if not safe:
        return
    await set_column(guild_xid, xid, **safe)
