from datetime import datetime
from typing import Optional

import discord
from asgiref.sync import sync_to_async
from sqlalchemy.dialects.postgresql import insert

from spellbot.database import DatabaseSession
from spellbot.models.channel import Channel
from spellbot.services import BaseService


class ChannelsService(BaseService):
    def __init__(self):
        self.channel: Optional[Channel] = None

    @sync_to_async()
    def upsert(self, channel: discord.TextChannel) -> None:
        name_max_len = Channel.name.property.columns[0].type.length  # type: ignore
        name = channel.name[:name_max_len]
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
        self.channel = (
            DatabaseSession.query(Channel)
            .filter(
                Channel.xid == channel.id,
            )
            .one_or_none()
        )

    @sync_to_async
    def select(self, channel_xid: int) -> bool:
        self.channel = (
            DatabaseSession.query(Channel)
            .filter(
                Channel.xid == channel_xid,
            )
            .one_or_none()
        )
        return bool(self.channel)

    @sync_to_async
    def current_default_seats(self) -> int:
        assert self.channel
        return self.channel.default_seats

    @sync_to_async
    def set_default_seats(self, seats: int) -> None:
        assert self.channel
        self.channel.default_seats = seats  # type: ignore
        DatabaseSession.commit()

    @sync_to_async
    def should_auto_verify(self) -> bool:
        assert self.channel
        return bool(self.channel.auto_verify)

    @sync_to_async
    def verified_only(self) -> bool:
        assert self.channel
        return bool(self.channel.verified_only)

    @sync_to_async
    def unverified_only(self) -> bool:
        assert self.channel
        return bool(self.channel.unverified_only)

    @sync_to_async
    def set_auto_verify(self, setting: bool) -> None:
        assert self.channel
        self.channel.auto_verify = setting  # type: ignore
        DatabaseSession.commit()

    @sync_to_async
    def set_verified_only(self, setting: bool) -> None:
        assert self.channel
        self.channel.verified_only = setting  # type: ignore
        DatabaseSession.commit()

    @sync_to_async
    def set_unverified_only(self, setting: bool) -> None:
        assert self.channel
        self.channel.unverified_only = setting  # type: ignore
        DatabaseSession.commit()
