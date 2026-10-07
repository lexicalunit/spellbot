# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from . import Base

if TYPE_CHECKING:
    from spellbot.data import QueueData


class Queue(Base):
    """Represents a user in a queue to play a game."""

    __tablename__ = "queues"

    user_xid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of the user in the queue",
    )
    game_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("games.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
        doc="The SpellBot game ID of a pending game the user is queued for",
    )
    og_guild_xid: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        doc="The external Discord ID of the guild where the user entered this game",
    )

    def to_data(self) -> QueueData:
        from spellbot.data import QueueData  # allow_inline

        return QueueData(
            user_xid=self.user_xid,
            game_id=self.game_id,
            og_guild_xid=self.og_guild_xid,
        )
