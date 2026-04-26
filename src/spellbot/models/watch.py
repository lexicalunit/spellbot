from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Column, ForeignKey, String

from . import Base

if TYPE_CHECKING:
    from spellbot.data import WatchData

    from . import Guild, User  # noqa: F401


class Watch(Base):
    """Records of watched users on a per guild basis."""

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

    def to_data(self) -> WatchData:
        from spellbot.data import WatchData  # allow_inline

        return WatchData(
            guild_xid=self.guild_xid,
            user_xid=self.user_xid,
            note=self.note,
        )
