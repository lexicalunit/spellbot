from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer

from . import Base, now

if TYPE_CHECKING:  # pragma: no cover
    from . import Game, User  # noqa


class Play(Base):
    """Records of a users game plays."""

    __tablename__ = "plays"

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=now,
        doc="UTC timestamp when this games was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=now,
        onupdate=datetime.utcnow,
        doc="UTC timestamp when this games was last updated",
    )
    user_xid = Column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of the user who played a game",
    )
    game_id = cast(
        int,
        Column(
            Integer,
            ForeignKey("games.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
            index=True,
            doc="The SpellBot game ID of the game the user played",
        ),
    )
    points = Column(
        Integer,
        nullable=True,
        doc="The number of points reported by the user",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "user_xid": self.user_xid,
            "game_id": self.game_id,
            "points": self.points,
        }
