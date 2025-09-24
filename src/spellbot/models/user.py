from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, TypedDict

from sqlalchemy import BigInteger, Boolean, Column, DateTime, String, false
from sqlalchemy.orm import relationship

from . import Base, GameStatus, now

if TYPE_CHECKING:
    from . import Game


class UserDict(TypedDict):
    xid: int
    created_at: datetime
    updated_at: datetime
    name: str
    banned: bool


class User(Base):
    """Represents a Discord user."""

    __tablename__ = "users"

    xid = Column(
        BigInteger,
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of this user",
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this user was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
        doc="UTC timestamp when this user was last updated",
    )
    name = Column(
        String(100),
        nullable=False,
        doc="Most recently cached name of this user",
    )
    banned = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If true, this user is banned from using SpellBot",
    )

    queues = relationship(
        "Queue",
        primaryjoin="User.xid == Queue.user_xid",
        doc="Queues this user is currently in",
    )
    plays = relationship(
        "Play",
        primaryjoin="User.xid == Play.user_xid",
        doc="Queryset of games played by this user",
    )

    def game(self, channel_xid: int) -> Game | None:
        from spellbot.database import DatabaseSession

        from . import Game, Post, Queue

        session = DatabaseSession.object_session(self)
        queue = (
            session.query(Queue)
            .join(Game)
            .join(Post)
            .filter(
                Queue.user_xid == self.xid,
                Post.channel_xid == channel_xid,
            )
            .order_by(Game.updated_at.desc())
            .first()
        )
        return session.get(Game, queue.game_id) if queue else None

    def waiting(self, channel_xid: int) -> bool:
        game = self.game(channel_xid)
        if game is None:
            return False
        if game.status != GameStatus.PENDING.value:
            return False
        # Not required because self.game() already filters by posts + channel.
        # if not any(post.channel_xid == channel_xid for post in game.posts):
        #     return False
        return game.deleted_at is None

    def pending_games(self) -> int:
        from spellbot.database import DatabaseSession

        from . import Queue

        session = DatabaseSession.object_session(self)
        return session.query(Queue).filter(Queue.user_xid == self.xid).count()

    def to_dict(self) -> UserDict:
        return {
            "xid": self.xid,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "name": self.name,
            "banned": self.banned,
        }
