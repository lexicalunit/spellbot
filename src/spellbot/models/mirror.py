from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, TypedDict

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey

from . import Base, now

if TYPE_CHECKING:
    from . import Channel, Guild  # noqa: F401


class MirrorDict(TypedDict):
    created_at: datetime
    updated_at: datetime
    from_guild_xid: int
    from_channel_xid: int
    to_guild_xid: int
    to_channel_xid: int


class Mirror(Base):
    """Represents configuration for mirroring game posts between two channels."""

    __tablename__ = "mirrors"

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=now,
        doc="UTC timestamp when this post was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=now,
        onupdate=datetime.utcnow,
        doc="UTC timestamp when this post was last updated",
    )
    from_guild_xid = Column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of the associated guild",
    )
    from_channel_xid = Column(
        BigInteger,
        ForeignKey("channels.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of the associated channel",
    )
    to_guild_xid = Column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of the associated guild",
    )
    to_channel_xid = Column(
        BigInteger,
        ForeignKey("channels.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of the associated channel",
    )

    def to_dict(self) -> MirrorDict:
        return {
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "from_guild_xid": self.from_guild_xid,
            "from_channel_xid": self.from_channel_xid,
            "to_guild_xid": self.to_guild_xid,
            "to_channel_xid": self.to_channel_xid,
        }
