from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, TypedDict

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from . import Base, now

if TYPE_CHECKING:
    from . import Channel, Game, Guild  # noqa: F401


class PostDict(TypedDict):
    created_at: datetime
    updated_at: datetime
    game_id: int
    guild_xid: int
    channel_xid: int
    message_xid: int
    jump_link: str


class Post(Base):
    """Represents the Discord post where a game's embed is shown."""

    __tablename__ = "posts"

    created_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this post was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
        doc="UTC timestamp when this post was last updated",
    )
    game_id = Column(
        Integer,
        ForeignKey("games.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
        doc="The SpellBot game ID of the game the user played",
    )
    guild_xid = Column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of the associated guild",
    )
    channel_xid = Column(
        BigInteger,
        ForeignKey("channels.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of the associated channel",
    )
    message_xid = Column(
        BigInteger,
        primary_key=True,
        nullable=False,
        index=True,
        doc="The external Discord ID of the message where this post's embed is found",
    )

    game = relationship(
        "Game",
        back_populates="posts",
        doc="The game this post is associated with",
    )
    guild = relationship("Guild", doc="The guild this post was created in")
    channel = relationship("Channel", doc="The channel post game was created in")

    @property
    def jump_link(self) -> str:
        guild = self.guild_xid
        channel = self.channel_xid
        message = self.message_xid
        return f"https://discordapp.com/channels/{guild}/{channel}/{message}"

    def to_dict(self) -> PostDict:
        return {
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "game_id": self.game_id,
            "guild_xid": self.guild_xid,
            "channel_xid": self.channel_xid,
            "message_xid": self.message_xid,
            "jump_link": self.jump_link,
        }
