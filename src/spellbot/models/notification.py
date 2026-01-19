from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, TypedDict, cast

from sqlalchemy import BigInteger, Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql.expression import text

from spellbot.enums import GameBracket, GameFormat, GameService

from . import Base, now

if TYPE_CHECKING:
    from spellbot.services import NotificationData


class NotificationDict(TypedDict):
    id: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    deleted_at: datetime | None
    guild: int
    channel: int
    message: int | None
    players: list[str]
    format: int
    bracket: int
    service: int
    link: str


class Notification(Base):
    """Represents a Discord notification message."""

    __tablename__ = "notifications"

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
        doc="UTC timestamp when this game was deleted",
    )
    guild = Column(
        BigInteger,
        index=True,
        nullable=False,
        doc="The external Discord ID of the associated guild",
    )
    channel = Column(
        BigInteger,
        index=True,
        nullable=False,
        doc="The external Discord ID of the associated channel",
    )
    message = Column(
        BigInteger,
        index=True,
        nullable=True,
        doc="The external Discord ID of the associated message",
    )
    players = Column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        default=list,
        doc="List of players in this game",
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
            default=GameService.SPELLTABLE.value,
            server_default=text(str(GameService.SPELLTABLE.value)),
            index=True,
            nullable=False,
            doc="The service that created this game",
        ),
    )
    link = Column(
        String(255),
        nullable=False,
        doc="The link of this game",
    )

    def to_dict(self) -> NotificationDict:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "deleted_at": self.deleted_at,
            "guild": self.guild,
            "channel": self.channel,
            "message": self.message,
            "players": self.players,
            "format": self.format,
            "bracket": self.bracket,
            "service": self.service,
            "link": self.link,
        }

    def to_data(self) -> NotificationData:
        from spellbot.services import NotificationData  # allow_inline: avoid circular

        return NotificationData.from_db(self)
