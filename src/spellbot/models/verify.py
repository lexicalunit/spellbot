from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Column, false

from . import Base

if TYPE_CHECKING:
    from spellbot.data import VerifyData


class Verify(Base):
    """Records of a user's verification status on a per guild basis."""

    __tablename__ = "verify"

    guild_xid = Column(
        BigInteger,
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of this guild",
    )
    user_xid = Column(
        BigInteger,
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of this user",
    )
    verified = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If true, this user is considered verified for this guild",
    )

    def to_data(self) -> VerifyData:
        from spellbot.data import VerifyData  # allow_inline

        return VerifyData(
            guild_xid=self.guild_xid,
            user_xid=self.user_xid,
            verified=self.verified,
        )
