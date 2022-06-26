from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Column, ForeignKey, Integer

from . import Base

if TYPE_CHECKING:  # pragma: no cover
    from . import Game, User  # noqa


class Play(Base):
    """Records of a users game plays."""

    __tablename__ = "plays"

    user_xid = Column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of the user who played a game",
    )
    game_id = Column(
        Integer,
        ForeignKey("games.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
        doc="The SpellBot game ID of the game the user played",
    )
    points = Column(
        Integer,
        nullable=True,
        doc="The number of points reported by the user",
    )
