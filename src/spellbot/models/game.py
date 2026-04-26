from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum, auto
from functools import partial
from typing import TYPE_CHECKING, cast

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String
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
        doc="UTC timestamp when this games was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
        index=True,
        doc="UTC timestamp when this games was last updated",
    )
    started_at = Column(
        DateTime,
        nullable=True,
        doc="UTC timestamp when this games was started",
    )
    deleted_at = Column(
        DateTime,
        nullable=True,
        index=True,
        doc="UTC timestamp when this games was deleted",
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

    @property
    def players(self) -> list[User]:
        from spellbot.database import DatabaseSession  # allow_inline

        from . import Play, Queue, User  # allow_inline

        if self.started_at is None:
            rows = DatabaseSession.query(Queue.user_xid).filter(Queue.game_id == self.id)
        else:
            rows = DatabaseSession.query(Play.user_xid).filter(Play.game_id == self.id)
        player_xids = [int(row[0]) for row in rows]
        return DatabaseSession.query(User).filter(User.xid.in_(player_xids)).all()

    @property
    def player_pins(self) -> dict[int, str | None]:
        from spellbot.database import DatabaseSession  # allow_inline

        from . import Play  # allow_inline

        plays = DatabaseSession.query(Play).filter(Play.game_id == self.id)
        return {
            play.user_xid: play.pin if self.guild.enable_mythic_track else None for play in plays
        }

    def to_data(self) -> GameData:
        from spellbot.data.game_data import GameData  # allow_inline

        return GameData(
            id=self.id,
            created_at=self.created_at,
            updated_at=self.updated_at,
            started_at=self.started_at,
            deleted_at=self.deleted_at,
            guild_xid=self.guild_xid,
            guild=self.guild.to_data(),
            channel_xid=self.channel_xid,
            channel=self.channel.to_data(),
            posts=[post.to_data() for post in self.posts],
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
            blind=self.blind,
            players=[player.to_data() for player in self.players],
            player_pins=self.player_pins,
        )


MAX_RULES_LENGTH: int = Game.rules.property.columns[0].type.length  # type: ignore
