from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import delete
from sqlalchemy import select as sa_select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import update

from spellbot.database import DatabaseSession
from spellbot.environment import running_in_pytest
from spellbot.models import Channel

if TYPE_CHECKING:
    from discord.abc import MessageableChannel

    from spellbot.data import ChannelData

channel_cache: dict[int, str] = {}


def is_cached(xid: int, name: str) -> bool:  # pragma: no cover
    if running_in_pytest():
        return False
    return bool((cached_name := channel_cache.get(xid)) and cached_name == name)


async def upsert(channel: MessageableChannel) -> ChannelData:
    assert channel.guild is not None
    name_max_len = Channel.name.property.columns[0].type.length
    raw_name = getattr(channel, "name", "")
    name = raw_name[:name_max_len]
    if not is_cached(channel.id, name):  # pragma: no branch
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

    result = await DatabaseSession.execute(
        sa_select(Channel).where(Channel.xid == channel.id),
    )
    db_channel = result.scalar_one()
    return db_channel.to_data()


async def forget(xid: int) -> None:
    await DatabaseSession.execute(
        delete(Channel).where(Channel.xid == xid).execution_options(synchronize_session=False),
    )
    channel_cache.pop(xid, None)


async def select(xid: int) -> ChannelData | None:
    result = await DatabaseSession.execute(sa_select(Channel).where(Channel.xid == xid))
    channel = result.scalar_one_or_none()
    return channel.to_data() if channel else None


async def _set_column(xid: int, **values: object) -> None:
    query = (
        update(Channel)
        .where(Channel.xid == xid)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    await DatabaseSession.execute(query)
    await DatabaseSession.commit()


async def set_default_seats(xid: int, seats: int) -> None:
    await _set_column(xid, default_seats=seats)


async def set_default_format(xid: int, format: int) -> None:
    await _set_column(xid, default_format=format)


async def set_default_bracket(xid: int, bracket: int) -> None:
    await _set_column(xid, default_bracket=bracket)


async def set_default_service(xid: int, service: int) -> None:
    await _set_column(xid, default_service=service)


async def set_auto_verify(xid: int, setting: bool) -> None:
    await _set_column(xid, auto_verify=setting)


async def set_verified_only(xid: int, setting: bool) -> None:
    await _set_column(xid, verified_only=setting)


async def set_unverified_only(xid: int, setting: bool) -> None:
    await _set_column(xid, unverified_only=setting)


async def set_motd(xid: int, message: str | None = None) -> str:
    if message:
        max_len = Channel.motd.property.columns[0].type.length
        motd = message[:max_len]
    else:
        motd = ""
    await _set_column(xid, motd=motd)
    return motd


async def set_extra(xid: int, message: str | None = None) -> str:
    if message:
        max_len = Channel.extra.property.columns[0].type.length
        extra = message[:max_len]
    else:
        extra = ""
    await _set_column(xid, extra=extra)
    return extra


async def set_voice_category(xid: int, value: str) -> str:
    max_len = Channel.voice_category.property.columns[0].type.length
    name = value[:max_len]
    await _set_column(xid, voice_category=name)
    return name


async def set_delete_expired(xid: int, value: bool) -> bool:
    await _set_column(xid, delete_expired=value)
    return value


async def set_blind_games(xid: int, value: bool) -> bool:
    await _set_column(xid, blind_games=value)
    return value


async def set_voice_invite(xid: int, value: bool) -> bool:
    await _set_column(xid, voice_invite=value)
    return value
