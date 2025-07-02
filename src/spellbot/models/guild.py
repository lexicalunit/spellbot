from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, TypedDict, cast

from sqlalchemy import BigInteger, Boolean, Column, DateTime, String, false, null
from sqlalchemy.orm import relationship

from . import Base, now

if TYPE_CHECKING:
    from collections.abc import Iterable

    from . import Channel, ChannelDict, Game, GuildAward, GuildAwardDict  # noqa: F401


class GuildDict(TypedDict):
    xid: int
    created_at: datetime
    updated_at: datetime
    name: str
    motd: str
    show_links: bool
    voice_create: bool
    use_max_bitrate: bool
    channels: list[ChannelDict]
    awards: list[GuildAwardDict]
    banned: bool
    notice: str
    suggest_voice_category: str
    enable_mythic_track: bool


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

    def to_dict(self) -> GuildDict:
        return {
            "xid": self.xid,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "name": self.name,
            "motd": self.motd,
            "show_links": self.show_links,
            "voice_create": self.voice_create,
            "use_max_bitrate": self.use_max_bitrate,
            "channels": sorted(
                [channel.to_dict() for channel in cast("Iterable[Channel]", self.channels)],
                key=lambda c: c["xid"],
            ),
            "awards": sorted(
                [award.to_dict() for award in cast("Iterable[GuildAward]", self.awards)],
                key=lambda c: c["id"],
            ),
            "banned": self.banned,
            "notice": self.notice,
            "suggest_voice_category": self.suggest_voice_category,
            "enable_mythic_track": self.enable_mythic_track,
        }
