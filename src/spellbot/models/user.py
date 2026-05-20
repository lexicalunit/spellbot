from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Column, DateTime, String, false, func, select
from sqlalchemy.orm import relationship

from spellbot.models import GameStatus

from . import Base, now

if TYPE_CHECKING:
    from spellbot.data import GameData, UserData

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
    playgroup_user_id = Column(
        BigInteger,
        nullable=True,
        default=None,
        doc="The Playgroup Live user ID linked to this Discord user",
    )
    locale = Column(
        String(10),
        nullable=False,
        default="en",
        server_default="en",
        doc="The user's preferred locale from Discord interactions",
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

    async def game(self, channel_xid: int) -> Game | None:
        from spellbot.database import DatabaseSession  # allow_inline

        from . import Game, Post, Queue  # allow_inline

        queue_result = await DatabaseSession.execute(
            select(Queue)
            .join(Game)
            .join(Post)
            .where(
                Queue.user_xid == self.xid,
                Post.channel_xid == channel_xid,
                Game.deleted_at.is_(None),
            )
            .order_by(Game.updated_at.desc()),
        )
        queue = queue_result.scalars().first()
        if queue is None:
            return None
        return await DatabaseSession.get(Game, queue.game_id)

    async def waiting(self, channel_xid: int) -> GameData | None:
        game = await self.game(channel_xid)
        if game is None:
            return None
        if game.status != GameStatus.PENDING.value:
            return None
        if game.deleted_at:  # type: ignore
            return None
        return await game.to_data()

    async def pending_games(self) -> int:
        from spellbot.database import DatabaseSession  # allow_inline

        from . import Game, Queue  # allow_inline

        result = await DatabaseSession.execute(
            select(func.count())
            .select_from(Queue)
            .join(Game)
            .where(
                Queue.user_xid == self.xid,
                Game.deleted_at.is_(None),
            ),
        )
        return result.scalar() or 0

    def to_data(self) -> UserData:
        from spellbot.data import UserData  # allow_inline

        return UserData(
            xid=self.xid,  # type: ignore
            created_at=self.created_at,  # type: ignore
            updated_at=self.updated_at,  # type: ignore
            name=self.name,  # type: ignore
            banned=self.banned,  # type: ignore
            playgroup_user_id=self.playgroup_user_id,  # type: ignore
            locale=self.locale,  # type: ignore
        )
