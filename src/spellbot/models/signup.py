from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Column, ForeignKey, Integer

from . import Base

if TYPE_CHECKING:  # pragma: no cover
    from . import Tourney, User  # noqa


class Signup(Base):
    """Tourneys a user has signed up for."""

    __tablename__ = "signups"

    user_xid = Column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of the user who signed up",
    )
    tourney_id = Column(
        Integer,
        ForeignKey("games.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
        doc="The SpellBot tourney ID of the tourney the user signed up for",
    )
