from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Column, ForeignKey

from . import Base

if TYPE_CHECKING:  # pragma: no cover
    from . import User  # noqa


class Block(Base):
    """Allows users to block other users."""

    __tablename__ = "blocks"

    user_xid = Column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
        doc="The user who is blocking someone",
    )
    blocked_user_xid = Column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
        doc="The user who is being blocked by someone",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_xid": self.user_xid,
            "blocked_user_xid": self.blocked_user_xid,
        }
