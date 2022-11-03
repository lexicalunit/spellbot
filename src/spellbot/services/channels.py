from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import discord
from asgiref.sync import sync_to_async
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import update

from ..database import DatabaseSession
from ..models import Channel


class ChannelsService:
    @sync_to_async()
    def upsert(self, channel: discord.TextChannel) -> dict[str, Any]:
        name_max_len = Channel.name.property.columns[0].type.length  # type: ignore
        raw_name = getattr(channel, "name", "")
        name = raw_name[:name_max_len]
        values = {
            "xid": channel.id,
            "guild_xid": channel.guild.id,
            "name": name,
            "updated_at": datetime.utcnow(),
        }
        upsert = insert(Channel).values(**values)
        upsert = upsert.on_conflict_do_update(
            index_elements=[Channel.xid],
            index_where=Channel.xid == values["xid"],
            set_=dict(
                name=upsert.excluded.name,
                updated_at=upsert.excluded.updated_at,
            ),
        )
        DatabaseSession.execute(upsert, values)
        DatabaseSession.commit()

        channel = DatabaseSession.query(Channel).filter(Channel.xid == channel.id).one()
        return channel.to_dict()

    @sync_to_async
    def select(self, xid: int) -> Optional[dict[str, Any]]:
        channel = DatabaseSession.query(Channel).filter(Channel.xid == xid).one_or_none()
        return channel.to_dict() if channel else None

    @sync_to_async
    def set_default_seats(self, xid: int, seats: int) -> None:
        query = (
            update(Channel)
            .where(Channel.xid == xid)
            .values(default_seats=seats)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async
    def set_auto_verify(self, xid: int, setting: bool) -> None:
        query = (
            update(Channel)
            .where(Channel.xid == xid)
            .values(auto_verify=setting)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async
    def set_verified_only(self, xid: int, setting: bool) -> None:
        query = (
            update(Channel)
            .where(Channel.xid == xid)
            .values(verified_only=setting)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async
    def set_unverified_only(self, xid: int, setting: bool) -> None:
        query = (
            update(Channel)
            .where(Channel.xid == xid)
            .values(unverified_only=setting)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async()
    def set_motd(self, xid: int, message: Optional[str] = None) -> str:
        if message:
            max_len = Channel.motd.property.columns[0].type.length  # type: ignore
            motd = message[:max_len]
        else:
            motd = ""
        query = (
            update(Channel)
            .where(Channel.xid == xid)
            .values(motd=motd)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()
        return motd

    @sync_to_async()
    def set_voice_category(self, xid: int, value: str) -> str:
        max_len = Channel.voice_category.property.columns[0].type.length  # type: ignore
        name = value[:max_len]
        query = (
            update(Channel)
            .where(Channel.xid == xid)
            .values(voice_category=name)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()
        return name

    @sync_to_async()
    def set_delete_expired(self, xid: int, value: bool) -> bool:
        query = (
            update(Channel)
            .where(Channel.xid == xid)
            .values(delete_expired=value)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()
        return value

    @sync_to_async()
    def set_show_points(self, xid: int, value: bool) -> bool:
        query = (
            update(Channel)
            .where(Channel.xid == xid)
            .values(show_points=value)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()
        return value
