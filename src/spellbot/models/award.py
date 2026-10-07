# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.expression import false
from sqlalchemy.sql.sqltypes import Boolean

from . import Base

if TYPE_CHECKING:
    from spellbot.data import GuildAwardData, UserAwardData

    from . import Guild


class GuildAward(Base):
    """Awards available on a guild."""

    __tablename__ = "guild_awards"

    id: Mapped[int] = mapped_column(
        Integer,
        autoincrement=True,
        nullable=False,
        primary_key=True,
        doc="The ID used to refer to this award",
    )
    guild_xid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="The guild associated with this award",
    )
    count: Mapped[int] = mapped_column(
        Integer,
        index=True,
        nullable=False,
        doc="The number of games required to achieve this award",
    )
    repeating: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If true, this award should be given every 'count' number of games",
    )
    remove: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If true, this award should be removed from instead of given to the player",
    )
    verified_only: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If true, this award will only ever apply to verified users",
    )
    unverified_only: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If true, this award will only ever apply to unverified users",
    )
    role: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="The name of the Discord role to give as the award",
    )
    message: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="The message to DM users who achieve this award",
    )

    guild: Mapped["Guild"] = relationship(
        "Guild",
        back_populates="awards",
        doc="The guild where this award is available",
    )

    def to_data(self) -> GuildAwardData:
        from spellbot.data import GuildAwardData  # allow_inline

        return GuildAwardData(
            id=self.id,
            guild_xid=self.guild_xid,
            count=self.count,
            repeating=self.repeating,
            remove=self.remove,
            role=self.role,
            message=self.message,
            verified_only=self.verified_only,
            unverified_only=self.unverified_only,
        )


class UserAward(Base):
    """Awards that a user has achieved on a per guild basis."""

    __tablename__ = "user_awards"

    user_xid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    guild_xid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    guild_award_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def to_data(self) -> UserAwardData:
        from spellbot.data import UserAwardData  # allow_inline

        return UserAwardData(
            user_xid=self.user_xid,
            guild_xid=self.guild_xid,
            guild_award_id=self.guild_award_id,
        )
