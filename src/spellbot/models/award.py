from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import false
from sqlalchemy.sql.sqltypes import Boolean

from . import Base

if TYPE_CHECKING:  # pragma: no cover
    from . import Guild, User  # noqa


class GuildAward(Base):
    """Awards available on a guild."""

    __tablename__ = "guild_awards"

    id = Column(
        Integer,
        autoincrement=True,
        nullable=False,
        primary_key=True,
        doc="The ID used to refer to this award",
    )
    guild_xid = Column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="The guild associated with this award",
    )
    count = Column(
        Integer,
        index=True,
        nullable=False,
        doc="The number of games required to achieve this award",
    )
    repeating = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If true, this award should be given every 'count' number of games",
    )
    remove = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If true, this award should be removed from instead of given to the player",
    )
    verified_only = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If true, this award will only ever apply to verified users",
    )
    unverified_only = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If true, this award will only ever apply to unverified users",
    )
    role = Column(
        String(100),
        nullable=False,
        doc="The name of the Discord role to give as the award",
    )
    message = Column(
        String(500),
        nullable=False,
        doc="The message to DM users who achieve this award",
    )

    guild = relationship(
        "Guild",
        back_populates="awards",
        doc="The guild where this award is available",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "guild_xid": self.guild_xid,
            "count": self.count,
            "repeating": self.repeating,
            "remove": self.remove,
            "role": self.role,
            "message": self.message,
            "verified_only": self.verified_only,
            "unverified_only": self.unverified_only,
        }


class UserAward(Base):
    """Awards that a user has achieved on a per guild basis."""

    __tablename__ = "user_awards"

    user_xid = Column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    guild_xid = Column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    guild_award_id = Column(Integer, nullable=True)
