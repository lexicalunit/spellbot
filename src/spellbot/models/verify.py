from sqlalchemy import BigInteger, Boolean, Column, false

from . import Base


class Verify(Base):
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
