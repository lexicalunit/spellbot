from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey

from . import Base, now

if TYPE_CHECKING:
    from spellbot.data import BlockData

    from . import User  # noqa: F401


class Block(Base):
    """Allows users to block other users."""

    __tablename__ = "blocks"

    created_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this games was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
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

    def to_data(self) -> BlockData:
        from spellbot.data import BlockData  # allow_inline

        return BlockData(
            created_at=self.created_at,
            updated_at=self.updated_at,
            user_xid=self.user_xid,
            blocked_user_xid=self.blocked_user_xid,
        )
