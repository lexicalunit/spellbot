from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pytz
from asgiref.sync import sync_to_async
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import update

from spellbot.database import DatabaseSession
from spellbot.models import Channel, ChannelDict

if TYPE_CHECKING:
    from discord.abc import MessageableChannel


class ChannelsService:
    @sync_to_async()
    def upsert(self, channel: MessageableChannel) -> ChannelDict:
        assert channel.guild is not None
        name_max_len = Channel.name.property.columns[0].type.length  # type: ignore
        raw_name = getattr(channel, "name", "")
        name = raw_name[:name_max_len]
        values = {
            "xid": channel.id,
            "guild_xid": channel.guild.id,
            "name": name,
            "updated_at": datetime.now(tz=pytz.utc),
        }
        upsert = insert(Channel).values(**values)
        upsert = upsert.on_conflict_do_update(
            index_elements=[Channel.xid],
            index_where=Channel.xid == values["xid"],
            set_={
                "name": upsert.excluded.name,
                "updated_at": upsert.excluded.updated_at,
            },
        )
        DatabaseSession.execute(upsert, values)
        DatabaseSession.commit()

        db_channel = DatabaseSession.query(Channel).filter(Channel.xid == channel.id).one()
        return db_channel.to_dict()

    @sync_to_async()
    def forget(self, xid: int) -> None:
        DatabaseSession.query(Channel).filter(Channel.xid == xid).delete(synchronize_session=False)

    @sync_to_async()
    def select(self, xid: int) -> ChannelDict | None:
        channel = DatabaseSession.query(Channel).filter(Channel.xid == xid).one_or_none()
        return channel.to_dict() if channel else None

    @sync_to_async()
    def set_default_seats(self, xid: int, seats: int) -> None:
        query = (
            update(Channel)
            .where(Channel.xid == xid)
            .values(default_seats=seats)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async()
    def set_default_format(self, xid: int, format: int) -> None:
        query = (
            update(Channel)
            .where(Channel.xid == xid)
            .values(default_format=format)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async()
    def set_default_service(self, xid: int, service: int) -> None:
        query = (
            update(Channel)
            .where(Channel.xid == xid)
            .values(default_service=service)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async()
    def set_auto_verify(self, xid: int, setting: bool) -> None:
        query = (
            update(Channel)
            .where(Channel.xid == xid)
            .values(auto_verify=setting)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async()
    def set_verified_only(self, xid: int, setting: bool) -> None:
        query = (
            update(Channel)
            .where(Channel.xid == xid)
            .values(verified_only=setting)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async()
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
    def set_motd(self, xid: int, message: str | None = None) -> str:
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
    def set_extra(self, xid: int, message: str | None = None) -> str:
        if message:
            max_len = Channel.extra.property.columns[0].type.length  # type: ignore
            extra = message[:max_len]
        else:
            extra = ""
        query = (
            update(Channel)
            .where(Channel.xid == xid)
            .values(extra=extra)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()
        return extra

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

    # TODO: Refactor how confirmation/points/ELO works.
    # @sync_to_async()
    # def set_require_confirmation(self, xid: int, value: bool) -> bool:
    #     query = (
    #         update(Channel)
    #         .where(Channel.xid == xid)
    #         .values(require_confirmation=value)
    #         .execution_options(synchronize_session=False)
    #     )
    #     DatabaseSession.execute(query)
    #     DatabaseSession.commit()
    #     return value

    @sync_to_async()
    def set_voice_invite(self, xid: int, value: bool) -> bool:
        query = (
            update(Channel)
            .where(Channel.xid == xid)
            .values(voice_invite=value)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()
        return value
