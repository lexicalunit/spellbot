from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Column, DateTime, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import false, text
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.sql.sqltypes import Boolean, Integer

from . import Base, now

if TYPE_CHECKING:  # pragma: no cover
    from . import Game, Guild  # noqa


class Channel(Base):
    """Represents a Discord text channel."""

    __tablename__ = "channels"

    xid = Column(
        BigInteger,
        primary_key=True,
        nullable=False,
        doc="The external Discord ID for a channel",
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=now,
        doc="UTC timestamp when this channel was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=now,
        onupdate=datetime.utcnow,
        doc="UTC timestamp when this channel was last updated",
    )
    guild_xid = Column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The guild associated with this channel",
    )
    name = Column(
        String(100),
        doc="Most recently cached name of this channel",
    )
    default_seats = Column(
        Integer,
        nullable=False,
        default=4,
        server_default=text("4"),
        doc="The default number of players that should be seated at newly created games.",
    )
    auto_verify = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="Channels that will trigger automatic verification of users who post there.",
    )
    unverified_only = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="Verified user posts will be deleted from this channel automatically.",
    )
    verified_only = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="Unverified user posts will be deleted from this channel automatically.",
    )
    motd = Column(
        String(255),
        doc="Channel message of the day",
    )
    voice_category = Column(
        String(50),
        doc="Category name for voice channels for games in this channel.",
        nullable=True,
        default="SpellBot Voice Channels",
        server_default=text("'SpellBot Voice Channels'"),
    )
    delete_expired = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If true delete any expired games rather than updating them to show their expiration.",
    )
    show_points = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="Configuration for showing points reporting on started games",
    )

    guild = relationship(
        "Guild",
        back_populates="channels",
        doc="The guild where this channel exists",
    )
    games = relationship(
        "Game",
        back_populates="channel",
        uselist=True,
        doc="The games created in this channel",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "xid": self.xid,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "guild_xid": self.guild_xid,
            "name": self.name,
            "default_seats": self.default_seats,
            "auto_verify": self.auto_verify,
            "unverified_only": self.unverified_only,
            "verified_only": self.verified_only,
            "motd": self.motd,
            "voice_category": self.voice_category,
            "delete_expired": self.delete_expired,
            "show_points": self.show_points,
        }
