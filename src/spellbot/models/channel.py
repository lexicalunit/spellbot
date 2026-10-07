# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.expression import false, text
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.sql.sqltypes import Boolean, Integer

from spellbot.enums import GameBracket, GameFormat, GameService

from . import Base, now, web_editable

if TYPE_CHECKING:
    from spellbot.data import ChannelData

    from . import Game, Guild


class Channel(Base):
    """Represents a Discord text channel."""

    __tablename__ = "channels"

    xid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        nullable=False,
        doc="The external Discord ID for a channel",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this channel was first created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
        doc="UTC timestamp when this channel was last updated",
    )
    guild_xid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The guild associated with this channel",
    )
    name: Mapped[str | None] = mapped_column(
        String(100),
        doc="Most recently cached name of this channel",
    )
    default_seats: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=4,
        server_default=text("4"),
        doc=web_editable(
            "The default number of players that should be seated at newly created games.",
        ),
    )
    default_format: Mapped[int] = mapped_column(
        Integer(),
        default=GameFormat.COMMANDER.value,
        server_default=text(str(GameFormat.COMMANDER.value)),
        index=True,
        nullable=False,
        doc=web_editable("The default Magic: The Gathering format for this channel."),
    )
    default_bracket: Mapped[int] = mapped_column(
        Integer(),
        default=GameBracket.NONE.value,
        server_default=text(str(GameBracket.NONE.value)),
        index=True,
        nullable=False,
        doc=web_editable("The default commander bracket for this channel"),
    )
    default_service: Mapped[int] = mapped_column(
        Integer(),
        default=GameService.CONVOKE.value,
        server_default=text(str(GameService.CONVOKE.value)),
        index=True,
        nullable=False,
        doc=web_editable("The default service for games in this channel."),
    )
    auto_verify: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc=web_editable(
            "If enabled, this channel will trigger automatic verification of users who post there.",
        ),
    )
    unverified_only: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc=web_editable("Verified user posts will be deleted from this channel automatically."),
    )
    verified_only: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc=web_editable(
            "Unverified user posts will be deleted from this channel automatically.",
        ),
    )
    motd: Mapped[str | None] = mapped_column(
        String(255),
        doc=web_editable("This channel's message of the day."),
    )
    extra: Mapped[str | None] = mapped_column(
        String(255),
        doc=web_editable(
            "Extra message content (which can contain role pings) added to game posts.",
        ),
    )
    voice_category: Mapped[str | None] = mapped_column(
        String(50),
        doc=web_editable(
            "The channel category name for voice channels created by this bot "
            "for games in this channel.",
        ),
        nullable=True,
        default="SpellBot Voice Channels",
        server_default=text("'SpellBot Voice Channels'"),
    )
    delete_expired: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc=web_editable(
            "If true, delete any expired games rather than updating them to show that they "
            "expired.",
        ),
    )
    voice_invite: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc=web_editable("Create voice channel invites for games in this channel."),
    )
    blind_games: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc=web_editable("Hide the player list for games created in this channel."),
    )
    to_mode: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc=web_editable(
            "Tournament organizer mode: when enabled, user blocks are not enforced "
            "for games in this channel.",
        ),
    )
    competitive_mode: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc=web_editable(
            "Create Convoke games for this channel in competitive mode.",
        ),
    )

    guild: Mapped["Guild"] = relationship(
        "Guild",
        back_populates="channels",
        doc="The guild where this channel exists",
    )
    games: Mapped[list["Game"]] = relationship(
        "Game",
        back_populates="channel",
        uselist=True,
        doc="The games created in this channel",
    )

    def to_data(self) -> ChannelData:
        from spellbot.data import ChannelData  # allow_inline

        return ChannelData(
            xid=self.xid,
            created_at=self.created_at,
            updated_at=self.updated_at,
            guild_xid=self.guild_xid,
            name=self.name,
            default_seats=self.default_seats,
            default_format=GameFormat(self.default_format),
            default_bracket=GameBracket(self.default_bracket),
            default_service=GameService(self.default_service),
            auto_verify=self.auto_verify,
            unverified_only=self.unverified_only,
            verified_only=self.verified_only,
            motd=self.motd,
            extra=self.extra,
            voice_category=self.voice_category,
            voice_invite=self.voice_invite,
            delete_expired=self.delete_expired,
            blind_games=self.blind_games,
            to_mode=self.to_mode,
            competitive_mode=self.competitive_mode,
        )
