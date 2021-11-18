from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Column, ForeignKey

from .base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .user import User  # noqa


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

    def to_dict(self) -> dict:
        return {
            "user_xid": self.user_xid,
            "blocked_user_xid": self.blocked_user_xid,
        }
