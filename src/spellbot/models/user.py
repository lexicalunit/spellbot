from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Boolean, Column, DateTime, String, false
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import and_

from . import Base, GameStatus, Play, now

if TYPE_CHECKING:
    from . import Game


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
        default=datetime.utcnow,
        server_default=now,
        doc="UTC timestamp when this user was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=now,
        onupdate=datetime.utcnow,
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
        lazy="dynamic",  # this is a sqlalchemy legacy feature not supported in 2.0
        doc="Queryset of games played by this user",
    )
    # A possible alternative -- less performant?
    #
    # plays = relationship(
    #     "Play",
    #     primaryjoin="User.xid == Play.user_xid",
    #     collection_class=attribute_mapped_collection("game_id"),
    # )
    #
    # Allows for application code like: `some_user.points[game_id].points`

    def game(self, channel_xid: int) -> Game | None:
        from spellbot.database import DatabaseSession

        from . import Game, Queue

        session = DatabaseSession.object_session(self)
        queue = (
            session.query(Queue)
            .join(Game)
            .filter(
                and_(
                    Queue.user_xid == self.xid,
                    Game.channel_xid == channel_xid,
                ),
            )
            .order_by(Game.updated_at.desc())
            .first()
        )
        return session.query(Game).get(queue.game_id) if queue else None

    def points(self, game_id: int) -> tuple[int | None, bool] | None:
        play: Play | None = self.plays.filter(Play.game_id == game_id).one_or_none()
        return (play.points, play.confirmed_at is not None) if play else None

    def waiting(self, channel_xid: int) -> bool:
        game = self.game(channel_xid)
        return bool(
            game
            and game.channel_xid == channel_xid
            and game.status == GameStatus.PENDING.value
            and not game.deleted_at,
        )

    def confirmed(self, channel_xid: int) -> bool:
        from spellbot.database import DatabaseSession

        from . import Game, Play

        session = DatabaseSession.object_session(self)
        last_game = (
            session.query(Game)
            .filter(
                Game.channel_xid == channel_xid,
                Game.status == GameStatus.STARTED.value,
            )
            .order_by(Game.started_at.desc())
            .first()
        )
        if not last_game:
            return True
        last_play = (
            session.query(Play)
            .filter(Play.user_xid == self.xid, Play.game_id == last_game.id)
            .first()
        )
        if not last_play:
            return True
        return last_play.confirmed_at is not None

    def pending_games(self) -> int:
        from spellbot.database import DatabaseSession

        from . import Queue

        session = DatabaseSession.object_session(self)
        return session.query(Queue).filter(Queue.user_xid == self.xid).count()

    def to_dict(self) -> dict[str, Any]:
        return {
            "xid": self.xid,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "name": self.name,
            "banned": self.banned,
        }
