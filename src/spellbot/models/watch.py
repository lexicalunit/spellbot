from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Column, ForeignKey, String

from .base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .guild import Guild  # noqa
    from .user import User  # noqa


class Watch(Base):
    __tablename__ = "watches"

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
        doc="The external Discord ID of a user for moderators to keep an eye on",
    )
    note = Column(
        String(1024),
        doc="The note to DM to moderators when this user enters a game",
    )

    def to_dict(self) -> dict:
        return {
            "guild_xid": self.guild_xid,
            "user_xid": self.user_xid,
            "note": self.note,
        }
