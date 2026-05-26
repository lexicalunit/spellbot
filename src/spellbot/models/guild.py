from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, cast

from sqlalchemy import BigInteger, Boolean, Column, DateTime, String, false, null, true
from sqlalchemy.orm import relationship

from . import Base, now

if TYPE_CHECKING:
    from collections.abc import Iterable

    from spellbot.data import GuildData

    from . import Channel, Game, GuildAward  # noqa: F401


class Guild(Base):
    """Represents a Discord guild."""

    __tablename__ = "guilds"

    xid: int = cast("int", Column(BigInteger, primary_key=True, nullable=False))
    created_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this guild was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
        doc="UTC timestamp when this guild was last updated",
    )
    name = Column(
        String(100),
        doc="Most recently cached name of this guild",
    )
    motd = Column(
        String(255),
        doc="Guild message of the day",
    )
    show_links = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="Configuration for showing game related links publicly",
    )
    voice_create = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="Configuration for automatically created voice channels for games",
    )
    use_max_bitrate = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="Configuration for using maximum bitrate for created voice channels",
    )
    banned = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If true, this guild is banned from using SpellBot",
    )
    notice = Column(
        String(255),
        doc="Notice to display to users in this guild",
        nullable=True,
        default=None,
        server_default=null(),
    )
    suggest_voice_category = Column(
        String(100),
        doc="Category to use when suggesting voice channels for games",
        nullable=True,
        default=None,
        server_default=null(),
    )
    enable_mythic_track = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If true, enable mythic track for this guild",
    )
    active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
        doc="If false, the bot is no longer a member of this guild",
    )
    locale = Column(
        String(10),
        nullable=False,
        default="en",
        server_default="en",
        doc="The guild's preferred locale from Discord",
    )
    icon = Column(
        String(255),
        nullable=True,
        default=None,
        server_default=null(),
        doc="Cached Discord CDN URL for this guild's icon",
    )
    promote = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
        doc="If true, this guild may be advertised on public SpellBot pages",
    )

    games = relationship(
        "Game",
        back_populates="guild",
        uselist=True,
        doc="Games played on this guild",
    )
    channels = relationship(
        "Channel",
        back_populates="guild",
        uselist=True,
        doc="Channels on this guild",
    )
    awards = relationship(
        "GuildAward",
        back_populates="guild",
        uselist=True,
        order_by="GuildAward.count",
        doc="Awards available in this guild",
    )

    async def to_data(self) -> GuildData:
        from spellbot.data import GuildData  # allow_inline

        channels = await self.awaitable_attrs.channels
        awards = await self.awaitable_attrs.awards
        return GuildData(
            xid=self.xid,
            created_at=self.created_at,  # type: ignore
            updated_at=self.updated_at,  # type: ignore
            name=self.name,  # type: ignore
            motd=self.motd,  # type: ignore
            show_links=self.show_links,  # type: ignore
            voice_create=self.voice_create,  # type: ignore
            use_max_bitrate=self.use_max_bitrate,  # type: ignore
            channels=sorted(
                [channel.to_data() for channel in cast("Iterable[Channel]", channels)],
                key=lambda c: c.xid,
            ),
            awards=sorted(
                [award.to_data() for award in cast("Iterable[GuildAward]", awards)],
                key=lambda c: c.id,
            ),
            banned=self.banned,  # type: ignore
            notice=self.notice,  # type: ignore
            suggest_voice_category=self.suggest_voice_category,  # type: ignore
            enable_mythic_track=self.enable_mythic_track,  # type: ignore
            active=self.active,  # type: ignore
            locale=self.locale,  # type: ignore
            icon=self.icon,  # type: ignore
            promote=self.promote,  # type: ignore
        )
