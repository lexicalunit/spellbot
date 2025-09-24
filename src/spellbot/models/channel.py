from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, TypedDict, cast

from sqlalchemy import BigInteger, Column, DateTime, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import false, text
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.sql.sqltypes import Boolean, Integer

from spellbot.enums import GameBracket, GameFormat, GameService

from . import Base, now

if TYPE_CHECKING:
    from . import Game, Guild  # noqa: F401


class ChannelDict(TypedDict):
    xid: int
    created_at: datetime
    updated_at: datetime
    guild_xid: int
    name: str
    default_seats: int
    default_format: GameFormat
    default_bracket: GameBracket
    default_service: GameService
    auto_verify: bool
    unverified_only: bool
    verified_only: bool
    motd: str
    extra: str
    voice_category: str
    voice_invite: bool
    delete_expired: bool
    blind_games: bool


class Channel(Base):
    """Represents a Discord text channel."""

    __tablename__ = "channels"

    xid: int = cast(
        "int",
        Column(
            BigInteger,
            primary_key=True,
            nullable=False,
            doc="The external Discord ID for a channel",
        ),
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this channel was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
        doc="UTC timestamp when this channel was last updated",
    )
    guild_xid = Column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The guild associated with this channel",
    )
    name = Column(
        String(100),
        doc="Most recently cached name of this channel",
    )
    default_seats = Column(
        Integer,
        nullable=False,
        default=4,
        server_default=text("4"),
        doc="The default number of players that should be seated at newly created games.",
    )
    default_format = Column(
        Integer(),
        default=GameFormat.COMMANDER.value,
        server_default=text(str(GameFormat.COMMANDER.value)),
        index=True,
        nullable=False,
        doc="The default Magic: The Gathering format for this channel",
    )
    default_bracket = Column(
        Integer(),
        default=GameBracket.NONE.value,
        server_default=text(str(GameBracket.NONE.value)),
        index=True,
        nullable=False,
        doc="The default commander bracket for this channel",
    )
    default_service = Column(
        Integer(),
        default=GameService.SPELLTABLE.value,
        server_default=text(str(GameService.SPELLTABLE.value)),
        index=True,
        nullable=False,
        doc="The default service for games in this channel",
    )
    auto_verify = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="Channels that will trigger automatic verification of users who post there.",
    )
    unverified_only = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="Verified user posts will be deleted from this channel automatically.",
    )
    verified_only = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="Unverified user posts will be deleted from this channel automatically.",
    )
    motd = Column(
        String(255),
        doc="Channel message of the day",
    )
    extra = Column(
        String(255),
        doc="Extra message content (which can contain alerts)",
    )
    voice_category = Column(
        String(50),
        doc="Category name for voice channels for games in this channel.",
        nullable=True,
        default="SpellBot Voice Channels",
        server_default=text("'SpellBot Voice Channels'"),
    )
    delete_expired = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If true delete any expired games rather than updating them to show their expiration.",
    )
    voice_invite = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="Configuration for creating voice invites for games in this channel.",
    )
    blind_games = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="Configuration for creating blind games in this channel.",
    )

    guild = relationship(
        "Guild",
        back_populates="channels",
        doc="The guild where this channel exists",
    )
    games = relationship(
        "Game",
        back_populates="channel",
        uselist=True,
        doc="The games created in this channel",
    )

    def to_dict(self) -> ChannelDict:
        return {
            "xid": self.xid,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "guild_xid": self.guild_xid,
            "name": self.name,
            "default_seats": self.default_seats,
            "default_format": GameFormat(cast("int", self.default_format)),
            "default_bracket": GameBracket(cast("int", self.default_bracket)),
            "default_service": GameService(cast("int", self.default_service)),
            "auto_verify": self.auto_verify,
            "unverified_only": self.unverified_only,
            "verified_only": self.verified_only,
            "motd": self.motd,
            "extra": self.extra,
            "voice_category": self.voice_category,
            "voice_invite": self.voice_invite,
            "delete_expired": self.delete_expired,
            "blind_games": self.blind_games,
        }
