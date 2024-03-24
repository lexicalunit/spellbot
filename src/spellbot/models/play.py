from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, TypedDict, cast

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer

from . import Base, now

if TYPE_CHECKING:
    from . import Game, User  # noqa: F401


class PlayDict(TypedDict):
    created_at: datetime
    updated_at: datetime
    user_xid: int
    game_id: int
    og_guild_xid: int
    points: int | None
    confirmed_at: datetime


class Play(Base):
    """Records of a users game plays."""

    __tablename__ = "plays"

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=now,
        doc="UTC timestamp when this play was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=now,
        onupdate=datetime.utcnow,
        doc="UTC timestamp when this play was last updated",
    )
    user_xid = Column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of the user who played this game",
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
    og_guild_xid = Column(
        BigInteger,
        nullable=False,
        doc="The external Discord ID of the guild where the user entered this game",
    )
    points = Column(
        Integer,
        nullable=True,
        doc="The number of points reported by the user",
    )
    confirmed_at = Column(
        DateTime,
        nullable=True,
        default=None,
        doc="UTC timestamp when this play was confirmed",
    )

    def to_dict(self) -> PlayDict:
        return {
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "user_xid": self.user_xid,
            "game_id": self.game_id,
            "og_guild_xid": self.og_guild_xid,
            "points": self.points,
            "confirmed_at": self.confirmed_at,
        }
