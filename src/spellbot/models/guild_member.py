from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey

from . import Base, now

if TYPE_CHECKING:
    from spellbot.data import GuildMemberData

    from . import Guild, User  # noqa: F401


class GuildMember(Base):
    """Tracks user membership within a guild."""

    __tablename__ = "guild_members"

    created_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this membership was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
        doc="UTC timestamp when this membership was last updated",
    )
    user_xid = Column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
        doc="The external Discord ID of the user",
    )
    guild_xid = Column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
        doc="The external Discord ID of the guild",
    )

    def to_data(self) -> GuildMemberData:
        from spellbot.data import GuildMemberData  # allow_inline

        return GuildMemberData(
            created_at=self.created_at,
            updated_at=self.updated_at,
            user_xid=self.user_xid,
            guild_xid=self.guild_xid,
        )
