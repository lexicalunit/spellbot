from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Column, ForeignKey, Integer

from . import Base

if TYPE_CHECKING:  # pragma: no cover
    from . import Guild, User  # noqa


class Config(Base):
    """User configuration on a per guild basis."""

    __tablename__ = "configs"

    guild_xid = Column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of this guild",
    )
    user_xid = Column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of this user",
    )
    power_level = Column(
        Integer,
        nullable=True,
        doc="User's current power level",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_xid": self.user_xid,
            "guild_xid": self.guild_xid,
            "power_level": self.power_level,
        }
