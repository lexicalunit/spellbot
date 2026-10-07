# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base, now

if TYPE_CHECKING:
    from spellbot.data import PostData

    from . import Channel, Game, Guild


class Post(Base):
    """Represents the Discord post where a game's embed is shown."""

    __tablename__ = "posts"

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this post was first created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
        doc="UTC timestamp when this post was last updated",
    )
    game_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("games.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
        doc="The SpellBot game ID of the game the user played",
    )
    guild_xid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of the associated guild",
    )
    channel_xid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("channels.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of the associated channel",
    )
    message_xid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        nullable=False,
        index=True,
        doc="The external Discord ID of the message where this post's embed is found",
    )

    game: Mapped["Game"] = relationship(
        "Game",
        back_populates="posts",
        doc="The game this post is associated with",
    )
    guild: Mapped["Guild"] = relationship("Guild", doc="The guild this post was created in")
    channel: Mapped["Channel"] = relationship("Channel", doc="The channel post game was created in")

    def to_data(self) -> PostData:
        from spellbot.data import PostData  # allow_inline

        return PostData(
            created_at=self.created_at,
            updated_at=self.updated_at,
            game_id=self.game_id,
            guild_xid=self.guild_xid,
            channel_xid=self.channel_xid,
            message_xid=self.message_xid,
        )
