# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum, auto
from functools import partial
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.expression import false, text

from spellbot.enums import GameBracket, GameFormat, GameService

from . import Base, now

if TYPE_CHECKING:
    from spellbot.data import GameData

    from . import Channel, Guild, Post, User


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
        String(255), doc="The generated link for this game"
    )
    password: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="The password for this game"
    )
    voice_invite_link: Mapped[str | None] = mapped_column(
        String(255), doc="The voice channel invite link for this game"
    )
    rules: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True, doc="Additional rules for this game"
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
    blind: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="Configuration for blind games",
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

    async def players(self) -> list[User]:
        from spellbot.database import DatabaseSession, any_of  # allow_inline

        from . import Play, Queue, User  # allow_inline

        if self.started_at is None:
            xid_result = await DatabaseSession.execute(
                select(Queue.user_xid).where(Queue.game_id == self.id),
            )
        else:
            xid_result = await DatabaseSession.execute(
                select(Play.user_xid).where(Play.game_id == self.id),
            )
        player_xids = [int(row[0]) for row in xid_result]
        users_result = await DatabaseSession.execute(
            select(User).where(any_of(User.xid, player_xids)),
        )
        return list(users_result.scalars().all())

    async def player_pins(self) -> dict[int, str | None]:
        from spellbot.database import DatabaseSession  # allow_inline

        from . import Play  # allow_inline

        plays_result = await DatabaseSession.execute(
            select(Play).where(Play.game_id == self.id),
        )
        guild = await self.awaitable_attrs.guild
        enable_mythic_track = guild.enable_mythic_track
        return {
            play.user_xid: play.pin if enable_mythic_track else None
            for play in plays_result.scalars().all()
        }

    async def to_data(self) -> GameData:
        from spellbot.data.game_data import GameData  # allow_inline

        guild = await self.awaitable_attrs.guild
        channel = await self.awaitable_attrs.channel
        posts = await self.awaitable_attrs.posts
        players = await self.players()
        return GameData(
            id=self.id,
            created_at=self.created_at,
            updated_at=self.updated_at,
            started_at=self.started_at,
            deleted_at=self.deleted_at,
            guild_xid=self.guild_xid,
            guild=await guild.to_data(),
            channel_xid=self.channel_xid,
            channel=channel.to_data(),
            posts=[post.to_data() for post in posts],
            voice_xid=self.voice_xid,
            voice_invite_link=self.voice_invite_link,
            seats=self.seats,
            status=self.status,
            format=self.format,
            bracket=self.bracket,
            service=self.service,
            game_link=self.game_link,
            password=self.password,
            rules=self.rules,
            war_id=self.war_id,
            war_title=self.war_title,
            blind=self.blind,
            locale=self.locale,
            players=[player.to_data() for player in players],
            player_pins=await self.player_pins(),
        )


MAX_RULES_LENGTH: int = Game.rules.property.columns[0].type.length
