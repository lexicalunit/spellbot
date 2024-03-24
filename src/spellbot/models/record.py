from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, TypedDict

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from . import Base, now

if TYPE_CHECKING:
    from . import Channel, Guild, User  # noqa: F401


class RecordDict(TypedDict):
    created_at: datetime
    updated_at: datetime
    guild_xid: int
    channel_xid: int
    user_xid: int
    elo: int


class Record(Base):
    """A users record (ELO) for a competitive ranked channel."""

    __tablename__ = "records"

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=now,
        doc="UTC timestamp when this record was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=now,
        onupdate=datetime.utcnow,
        doc="UTC timestamp when this record was last updated",
    )
    guild_xid = Column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of the associated guild",
    )
    channel_xid = Column(
        BigInteger,
        ForeignKey("channels.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of the associated channel",
    )
    user_xid = Column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of the associated user",
    )
    elo = Column(
        Integer,
        nullable=False,
        default=1500,
        server_default="1500",
        doc="The user's current ELO score for this channel",
    )

    guild = relationship("Guild", doc="The guild associated with this record")
    channel = relationship("Channel", doc="The channel associated with this record")
    user = relationship("User", doc="The user associated with this record")

    def to_dict(self) -> RecordDict:
        return {
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "guild_xid": self.guild_xid,
            "channel_xid": self.channel_xid,
            "user_xid": self.user_xid,
            "elo": self.elo,
        }
