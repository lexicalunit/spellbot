from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey

from . import Base, now

if TYPE_CHECKING:  # pragma: no cover
    from . import User  # noqa


class Block(Base):
    """Allows users to block other users."""

    __tablename__ = "blocks"

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
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "user_xid": self.user_xid,
            "blocked_user_xid": self.blocked_user_xid,
        }
