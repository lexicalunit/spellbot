from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async
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


class ChannelsService:
    @sync_to_async()
    def upsert(self, channel: MessageableChannel) -> ChannelData:
        """Upsert the given Discord channel into the database."""
        assert channel.guild is not None
        name_max_len = Channel.name.property.columns[0].type.length  # type: ignore
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
                index_elements=[Channel.xid],
                index_where=Channel.xid == values["xid"],
                set_={
                    "name": upsert.excluded.name,
                    "updated_at": upsert.excluded.updated_at,
                },
                where=upsert.excluded.name != Channel.name,
            )
            DatabaseSession.execute(upsert, values)
            DatabaseSession.commit()
            channel_cache[channel.id] = name

        db_channel = DatabaseSession.query(Channel).filter(Channel.xid == channel.id).one()
        return db_channel.to_data()

    @sync_to_async()
    def forget(self, xid: int) -> None:
        """Delete the channel with the given xid from the database."""
        DatabaseSession.query(Channel).filter(Channel.xid == xid).delete(synchronize_session=False)
        channel_cache.pop(xid, None)

    @sync_to_async()
    def select(self, xid: int) -> ChannelData | None:
        """Fetch the channel data for the given xid."""
        channel = DatabaseSession.query(Channel).filter(Channel.xid == xid).one_or_none()
        return channel.to_data() if channel else None

    @sync_to_async()
    def set_default_seats(self, xid: int, seats: int) -> None:
        """Set the default number of seats for games in this channel."""
        query = (
            update(Channel)  # type: ignore
            .where(Channel.xid == xid)
            .values(default_seats=seats)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async()
    def set_default_format(self, xid: int, format: int) -> None:
        """Set the default game format for this channel."""
        query = (
            update(Channel)  # type: ignore
            .where(Channel.xid == xid)
            .values(default_format=format)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async()
    def set_default_bracket(self, xid: int, bracket: int) -> None:
        """Set the default game bracket for this channel."""
        query = (
            update(Channel)  # type: ignore
            .where(Channel.xid == xid)
            .values(default_bracket=bracket)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async()
    def set_default_service(self, xid: int, service: int) -> None:
        """Set the default game service for this channel."""
        query = (
            update(Channel)  # type: ignore
            .where(Channel.xid == xid)
            .values(default_service=service)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async()
    def set_auto_verify(self, xid: int, setting: bool) -> None:
        """Set whether users are automatically verified in this channel."""
        query = (
            update(Channel)  # type: ignore
            .where(Channel.xid == xid)
            .values(auto_verify=setting)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async()
    def set_verified_only(self, xid: int, setting: bool) -> None:
        """Set whether only verified users can use this channel."""
        query = (
            update(Channel)  # type: ignore
            .where(Channel.xid == xid)
            .values(verified_only=setting)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async()
    def set_unverified_only(self, xid: int, setting: bool) -> None:
        """Set whether only unverified users can use this channel."""
        query = (
            update(Channel)  # type: ignore
            .where(Channel.xid == xid)
            .values(unverified_only=setting)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async()
    def set_motd(self, xid: int, message: str | None = None) -> str:
        """Set the message of the day for this channel."""
        if message:
            max_len = Channel.motd.property.columns[0].type.length  # type: ignore
            motd = message[:max_len]
        else:
            motd = ""
        query = (
            update(Channel)  # type: ignore
            .where(Channel.xid == xid)
            .values(motd=motd)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()
        return motd

    @sync_to_async()
    def set_extra(self, xid: int, message: str | None = None) -> str:
        """Set extra text to display in game posts for this channel."""
        if message:
            max_len = Channel.extra.property.columns[0].type.length  # type: ignore
            extra = message[:max_len]
        else:
            extra = ""
        query = (
            update(Channel)  # type: ignore
            .where(Channel.xid == xid)
            .values(extra=extra)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()
        return extra

    @sync_to_async()
    def set_voice_category(self, xid: int, value: str) -> str:
        """Set the voice channel category prefix for this channel."""
        max_len = Channel.voice_category.property.columns[0].type.length  # type: ignore
        name = value[:max_len]
        query = (
            update(Channel)  # type: ignore
            .where(Channel.xid == xid)
            .values(voice_category=name)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()
        return name

    @sync_to_async()
    def set_delete_expired(self, xid: int, value: bool) -> bool:
        """Set whether expired games should be deleted in this channel."""
        query = (
            update(Channel)  # type: ignore
            .where(Channel.xid == xid)
            .values(delete_expired=value)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()
        return value

    @sync_to_async()
    def set_blind_games(self, xid: int, value: bool) -> bool:
        """Set whether games in this channel should be created in blind mode."""
        query = (
            update(Channel)  # type: ignore
            .where(Channel.xid == xid)
            .values(blind_games=value)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()
        return value

    @sync_to_async()
    def set_voice_invite(self, xid: int, value: bool) -> bool:
        """Set whether voice channel invites should be created for games."""
        query = (
            update(Channel)  # type: ignore
            .where(Channel.xid == xid)
            .values(voice_invite=value)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()
        return value
