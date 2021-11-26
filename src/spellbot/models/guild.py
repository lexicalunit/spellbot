from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Column, DateTime, String, false
from sqlalchemy.orm import relationship

from .base import Base, now

if TYPE_CHECKING:  # pragma: no cover
    from .award import GuildAward  # noqa
    from .channel import Channel  # noqa
    from .game import Game  # noqa


class Guild(Base):
    """Represents a Discord guild."""

    __tablename__ = "guilds"

    xid = Column(BigInteger, primary_key=True, nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=now,
        doc="UTC timestamp when this guild was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=now,
        onupdate=datetime.utcnow,
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
    show_points = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="Configuration for showing points reporting on started games",
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

    def to_dict(self) -> dict:
        return {
            "xid": self.xid,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "name": self.name,
            "motd": self.motd,
            "show_links": self.show_links,
            "voice_create": self.voice_create,
            "show_points": self.show_points,
            "channels": [channel.to_dict() for channel in self.channels],
            "awards": [award.to_dict() for award in self.awards],
        }
