from __future__ import annotations

from typing import TypedDict

from sqlalchemy import BigInteger, Column, ForeignKey, Integer

from . import Base


class QueueDict(TypedDict):
    user_xid: int
    game_id: int
    og_guild_xid: int


class Queue(Base):
    """Represents a user in a queue to play a game."""

    __tablename__ = "queues"

    user_xid = Column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of the user in the queue",
    )
    game_id = Column(
        Integer,
        ForeignKey("games.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
        doc="The SpellBot game ID of a pending game the user is queued for",
    )
    og_guild_xid = Column(
        BigInteger,
        nullable=False,
        doc="The external Discord ID of the guild where the user entered this game",
    )

    def to_dict(self) -> QueueDict:
        return {
            "user_xid": self.user_xid,
            "game_id": self.game_id,
            "og_guild_xid": self.og_guild_xid,
        }
