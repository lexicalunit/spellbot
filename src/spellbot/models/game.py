# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum, auto
from functools import partial
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.expression import false, text

from spellbot.enums import GameBracket, GameFormat, GameService

from . import Base, column_length, now

if TYPE_CHECKING:
    from . import Channel, Guild, Post


class GameStatus(Enum):
    PENDING = auto()
    STARTED = auto()


class Game(Base):
    """Represents a pending or started game."""

    __tablename__ = "games"

    id: Mapped[int] = mapped_column(
        Integer,
        autoincrement=True,
        nullable=False,
        primary_key=True,
        doc="The SpellBot game reference ID",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this game was first created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
        index=True,
        doc="UTC timestamp when this game was last updated",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        doc="UTC timestamp when this game was started",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
        doc="UTC timestamp when this game was deleted",
    )
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
        doc="UTC timestamp when alert notifications were processed for this game",
    )
    guild_xid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="The external Discord ID of the associated guild",
    )
    channel_xid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("channels.xid", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="The external Discord ID of the associated channel",
    )
    voice_xid: Mapped[int | None] = mapped_column(
        BigInteger,
        index=True,
        nullable=True,
        doc="The external Discord ID of an associated voice channel",
    )
    seats: Mapped[int] = mapped_column(
        Integer,
        index=True,
        nullable=False,
        doc="The number of seats (open or occupied) available at this game",
    )
    status: Mapped[int] = mapped_column(
        Integer(),
        default=GameStatus.PENDING.value,
        server_default=text(str(GameStatus.PENDING.value)),
        index=True,
        nullable=False,
        doc="Pending or started status of this game",
    )
    format: Mapped[int] = mapped_column(
        Integer(),
        default=GameFormat.COMMANDER.value,
        server_default=text(str(GameFormat.COMMANDER.value)),
        index=True,
        nullable=False,
        doc="The Magic: The Gathering format for this game",
    )
    bracket: Mapped[int] = mapped_column(
        Integer(),
        default=GameBracket.NONE.value,
        server_default=text(str(GameBracket.NONE.value)),
        index=True,
        nullable=False,
        doc="The commander bracket for this game",
    )
    service: Mapped[int] = mapped_column(
        Integer(),
        default=GameService.CONVOKE.value,
        server_default=text(str(GameService.CONVOKE.value)),
        index=True,
        nullable=False,
        doc="The service that will be used to create this game",
    )
    game_link: Mapped[str | None] = mapped_column(
        String(255),
        doc="The generated link for this game",
    )
    password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="The password for this game",
    )
    voice_invite_link: Mapped[str | None] = mapped_column(
        String(255),
        doc="The voice channel invite link for this game",
    )
    rules: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        doc="Additional rules for this game",
    )
    war_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        doc="Convoke Guild War UUID when this game is tagged as a war match",
    )
    war_title: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
        doc="Cached Convoke Guild War title for embeds",
    )
    convoke_guild_name: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        doc="Name of the Convoke guild linked to this game's Discord server, for embeds",
    )
    convoke_guild_url: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Convoke page of the guild linked to this game's Discord server, for embeds",
    )
    blind: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="Configuration for blind games",
    )
    to_mode: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If the game's channel had tournament organizer mode enabled when it was created",
    )
    competitive_mode: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If the game's channel had competitive mode enabled when it was created",
    )
    locale: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="en",
        server_default=text("'en'"),
        doc="The preferred locale for this game",
    )
    # The DB column is named `metadata` but SQLAlchemy reserves the `metadata`
    # attribute on declarative models, so the Python attribute is `game_metadata`.
    game_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        doc="Post-game report data reported by the game service (e.g. Convoke)",
    )

    posts: Mapped[list["Post"]] = relationship(
        "Post",
        back_populates="game",
        uselist=True,
        doc="The posts associated with this game",
    )
    guild: Mapped["Guild"] = relationship(
        "Guild",
        back_populates="games",
        doc="The guild this game was created in",
    )
    channel: Mapped["Channel"] = relationship(
        "Channel",
        back_populates="games",
        doc="The channel this game was created in",
    )


MAX_RULES_LENGTH: int = column_length(Game.rules)
