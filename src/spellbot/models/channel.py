from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, cast

from sqlalchemy import BigInteger, Column, DateTime, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import false, text
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.sql.sqltypes import Boolean, Integer

from spellbot.enums import GameBracket, GameFormat, GameService

from . import Base, now, web_editable

if TYPE_CHECKING:
    from spellbot.data import ChannelData

    from . import Game, Guild  # noqa: F401


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
        doc=web_editable(
            "The default number of players that should be seated at newly created games.",
        ),
    )
    default_format = Column(
        Integer(),
        default=GameFormat.COMMANDER.value,
        server_default=text(str(GameFormat.COMMANDER.value)),
        index=True,
        nullable=False,
        doc=web_editable("The default Magic: The Gathering format for this channel."),
    )
    default_bracket = Column(
        Integer(),
        default=GameBracket.NONE.value,
        server_default=text(str(GameBracket.NONE.value)),
        index=True,
        nullable=False,
        doc=web_editable("The default commander bracket for this channel"),
    )
    default_service = Column(
        Integer(),
        default=GameService.CONVOKE.value,
        server_default=text(str(GameService.CONVOKE.value)),
        index=True,
        nullable=False,
        doc=web_editable("The default service for games in this channel."),
    )
    auto_verify = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc=web_editable(
            "If enabled, this channel will trigger automatic verification of users who post there.",
        ),
    )
    unverified_only = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc=web_editable("Verified user posts will be deleted from this channel automatically."),
    )
    verified_only = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc=web_editable(
            "Unverified user posts will be deleted from this channel automatically.",
        ),
    )
    motd = Column(
        String(255),
        doc=web_editable("This channel's message of the day."),
    )
    extra = Column(
        String(255),
        doc=web_editable(
            "Extra message content (which can contain role pings) added to game posts.",
        ),
    )
    voice_category = Column(
        String(50),
        doc=web_editable(
            "The channel category name for voice channels created by this bot "
            "for games in this channel.",
        ),
        nullable=True,
        default="SpellBot Voice Channels",
        server_default=text("'SpellBot Voice Channels'"),
    )
    delete_expired = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc=web_editable(
            "If true, delete any expired games rather than updating them to show that they "
            "expired.",
        ),
    )
    voice_invite = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc=web_editable("Create voice channel invites for games in this channel."),
    )
    blind_games = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc=web_editable("Hide the player list for games created in this channel."),
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

    def to_data(self) -> ChannelData:
        from spellbot.data import ChannelData  # allow_inline

        return ChannelData(
            xid=self.xid,
            created_at=self.created_at,  # type: ignore
            updated_at=self.updated_at,  # type: ignore
            guild_xid=self.guild_xid,  # type: ignore
            name=self.name,  # type: ignore
            default_seats=self.default_seats,  # type: ignore
            default_format=GameFormat(cast("int", self.default_format)),
            default_bracket=GameBracket(cast("int", self.default_bracket)),
            default_service=GameService(cast("int", self.default_service)),
            auto_verify=self.auto_verify,  # type: ignore
            unverified_only=self.unverified_only,  # type: ignore
            verified_only=self.verified_only,  # type: ignore
            motd=self.motd,  # type: ignore
            extra=self.extra,  # type: ignore
            voice_category=self.voice_category,  # type: ignore
            voice_invite=self.voice_invite,  # type: ignore
            delete_expired=self.delete_expired,  # type: ignore
            blind_games=self.blind_games,  # type: ignore
        )
