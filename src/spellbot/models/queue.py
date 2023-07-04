from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, Column, ForeignKey, Integer

from . import Base


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_xid": self.user_xid,
            "game_id": self.game_id,
        }
