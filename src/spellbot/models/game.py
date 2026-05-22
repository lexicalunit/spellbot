from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum, auto
from functools import partial
from typing import TYPE_CHECKING, cast

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, select
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import false, text

from spellbot.enums import GameBracket, GameFormat, GameService

from . import Base, now

if TYPE_CHECKING:
    from spellbot.data import GameData

    from . import Channel, Guild, Post, User  # noqa: F401


class GameStatus(Enum):
    PENDING = auto()
    STARTED = auto()


class Game(Base):
    """Represents a pending or started game."""

    __tablename__ = "games"

    id = Column(
        Integer,
        autoincrement=True,
        nullable=False,
        primary_key=True,
        doc="The SpellBot game reference ID",
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this game was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
        index=True,
        doc="UTC timestamp when this game was last updated",
    )
    started_at = Column(
        DateTime,
        nullable=True,
        doc="UTC timestamp when this game was started",
    )
    deleted_at = Column(
        DateTime,
        nullable=True,
        index=True,
        doc="UTC timestamp when this game was deleted",
    )
    guild_xid = Column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="The external Discord ID of the associated guild",
    )
    channel_xid: int = cast(
        "int",
        Column(
            BigInteger,
            ForeignKey("channels.xid", ondelete="CASCADE"),
            index=True,
            nullable=False,
            doc="The external Discord ID of the associated channel",
        ),
    )
    voice_xid = Column(
        BigInteger,
        index=True,
        nullable=True,
        doc="The external Discord ID of an associated voice channel",
    )
    seats: int = cast(
        "int",
        Column(
            Integer,
            index=True,
            nullable=False,
            doc="The number of seats (open or occupied) available at this game",
        ),
    )
    status: int = cast(
        "int",
        Column(
            Integer(),
            default=GameStatus.PENDING.value,
            server_default=text(str(GameStatus.PENDING.value)),
            index=True,
            nullable=False,
            doc="Pending or started status of this game",
        ),
    )
    format: int = cast(
        "int",
        Column(
            Integer(),
            default=GameFormat.COMMANDER.value,
            server_default=text(str(GameFormat.COMMANDER.value)),
            index=True,
            nullable=False,
            doc="The Magic: The Gathering format for this game",
        ),
    )
    bracket: int = cast(
        "int",
        Column(
            Integer(),
            default=GameBracket.NONE.value,
            server_default=text(str(GameBracket.NONE.value)),
            index=True,
            nullable=False,
            doc="The commander bracket for this game",
        ),
    )
    service: int = cast(
        "int",
        Column(
            Integer(),
            default=GameService.CONVOKE.value,
            server_default=text(str(GameService.CONVOKE.value)),
            index=True,
            nullable=False,
            doc="The service that will be used to create this game",
        ),
    )
    game_link = Column(String(255), doc="The generated link for this game")
    password = Column(String(255), nullable=True, doc="The password for this game")
    voice_invite_link = Column(String(255), doc="The voice channel invite link for this game")
    rules = Column(String(255), nullable=True, index=True, doc="Additional rules for this game")
    blind = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="Configuration for blind games",
    )
    locale = Column(
        String(255),
        nullable=False,
        default="en",
        server_default=text("'en'"),
        doc="The preferred locale for this game",
    )

    posts = relationship(
        "Post",
        back_populates="game",
        uselist=True,
        doc="The posts associated with this game",
    )
    guild = relationship(
        "Guild",
        back_populates="games",
        doc="The guild this game was created in",
    )
    channel = relationship(
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
                select(Play.user_xid).where(Play.game_id == self.id),  # type: ignore
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
            select(Play).where(Play.game_id == self.id),  # type: ignore
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
            id=self.id,  # type: ignore
            created_at=self.created_at,  # type: ignore
            updated_at=self.updated_at,  # type: ignore
            started_at=self.started_at,  # type: ignore
            deleted_at=self.deleted_at,  # type: ignore
            guild_xid=self.guild_xid,  # type: ignore
            guild=await guild.to_data(),
            channel_xid=self.channel_xid,
            channel=channel.to_data(),
            posts=[post.to_data() for post in posts],
            voice_xid=self.voice_xid,  # type: ignore
            voice_invite_link=self.voice_invite_link,  # type: ignore
            seats=self.seats,
            status=self.status,
            format=self.format,
            bracket=self.bracket,
            service=self.service,
            game_link=self.game_link,  # type: ignore
            password=self.password,  # type: ignore
            rules=self.rules,  # type: ignore
            blind=self.blind,  # type: ignore
            locale=self.locale,  # type: ignore
            players=[player.to_data() for player in players],
            player_pins=await self.player_pins(),
        )


MAX_RULES_LENGTH: int = Game.rules.property.columns[0].type.length
