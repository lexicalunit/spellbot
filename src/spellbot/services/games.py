from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

import discord
from asgiref.sync import sync_to_async
from ddtrace import tracer
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import and_, asc, column, or_, select
from sqlalchemy.sql.functions import count

from ..database import DatabaseSession
from ..models import Block, Game, GameStatus, Play, User, UserAward, Watch
from ..settings import Settings

MAX_SPELLTABLE_LINK_LEN = Game.spelltable_link.property.columns[0].type.length  # type: ignore
MAX_VOICE_INVITE_LINK_LEN = Game.voice_invite_link.property.columns[0].type.length  # type: ignore


class GamesService:
    def __init__(self):
        self.game: Optional[Game] = None

    @sync_to_async
    @tracer.wrap()
    def select(self, game_id: int) -> bool:
        self.game = DatabaseSession.query(Game).get(game_id)
        return bool(self.game)

    @sync_to_async
    @tracer.wrap()
    def select_by_voice_xid(self, voice_xid: int) -> bool:
        self.game = (
            DatabaseSession.query(Game)
            .filter(
                Game.voice_xid == voice_xid,
            )
            .one_or_none()
        )
        return bool(self.game)

    @sync_to_async
    @tracer.wrap()
    def select_by_message_xid(self, message_xid: int) -> Optional[dict[str, Any]]:
        self.game = (
            DatabaseSession.query(Game)
            .filter(
                Game.message_xid == message_xid,
            )
            .one_or_none()
        )
        return self.game.to_dict() if self.game else None

    @sync_to_async
    @tracer.wrap()
    def add_player(self, player_xid: int) -> None:
        assert self.game

        rows = DatabaseSession.query(User).filter(User.game_id == self.game.id).count()
        assert rows + 1 <= self.game.seats

        query = (
            update(User)
            .where(User.xid == player_xid)
            .values(game_id=self.game.id)
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

        # This operation should "dirty" the Game, so we need to update its updated_at.
        query = (
            update(Game)
            .where(Game.id == self.game.id)
            .values(updated_at=datetime.utcnow())
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async
    @tracer.wrap()
    def upsert(
        self,
        *,
        guild_xid: int,
        channel_xid: int,
        author_xid: int,
        friends: list[int],
        seats: int,
        format: int,
        create_new: bool = False,
    ) -> bool:
        existing: Optional[Game] = None
        if not create_new:
            existing = self._find_existing(
                guild_xid=guild_xid,
                channel_xid=channel_xid,
                author_xid=author_xid,
                friends=friends,
                seats=seats,
                format=format,
            )

        new: bool
        game: Game
        if existing:
            game = existing
            new = False
        else:
            game = Game(
                guild_xid=guild_xid,
                channel_xid=channel_xid,
                seats=seats,
                format=format,
            )
            DatabaseSession.add(game)
            DatabaseSession.commit()
            new = True

        DatabaseSession.execute(
            update(User)
            .where(User.xid.in_([*friends, author_xid]))
            .values(game_id=game.id)
            .execution_options(synchronize_session=False),
        )
        DatabaseSession.commit()
        self.game = game
        return new

    @tracer.wrap()
    def _find_existing(
        self,
        *,
        guild_xid: int,
        channel_xid: int,
        author_xid: int,
        friends: list[int],
        seats: int,
        format: int,
    ) -> Optional[Game]:
        required_seats = 1 + len(friends)
        inner = (
            select(
                [
                    Game,
                    User.xid.label("users_xid"),
                    count(User.xid).over(partition_by=Game.id).label("player_count"),
                ],
            )
            .join(User, isouter=True)
            .filter(  # type: ignore
                and_(
                    Game.guild_xid == guild_xid,
                    Game.channel_xid == channel_xid,
                    Game.seats == seats,
                    Game.format == format,
                    Game.status == GameStatus.PENDING.value,
                    Game.deleted_at.is_(None),
                ),
            )
            .group_by(Game, User.xid)
            .order_by(asc(Game.updated_at))
            .alias("inner")
        )
        outer = (
            DatabaseSession.query(Game)
            # Note: select_entity_from() is deprecated and may need to be replaced
            #       with an altenative method eventually. See: https://docs.sqlalchemy.org
            #       /en/latest/orm/query.html#sqlalchemy.orm.Query.select_entity_from
            .select_entity_from(inner).filter(
                or_(
                    column("player_count") == 0,
                    and_(
                        column("player_count") > 0,
                        column("player_count") <= seats - required_seats,
                    ),
                ),
            )
        )
        joiners = [author_xid, *friends]
        xids_blocked_by_joiners = [
            row.blocked_user_xid
            for row in DatabaseSession.query(Block).filter(Block.user_xid.in_(joiners))
        ]

        game: Game
        for game in outer.all():
            players = [player.xid for player in game.players]
            if any(xid in players for xid in xids_blocked_by_joiners):
                continue  # a joiner has blocked one of the players

            xids_blocked_by_players = [
                row.blocked_user_xid
                for row in DatabaseSession.query(Block).filter(
                    Block.user_xid.in_(players),
                )
            ]
            if any(xid in joiners for xid in xids_blocked_by_players):
                continue  # a player has blocked one of the joiners

            return game

        return None

    @sync_to_async
    @tracer.wrap()
    def to_embed(self, dm: bool = False) -> discord.Embed:
        assert self.game
        return self.game.to_embed(dm)

    @sync_to_async
    @tracer.wrap()
    def set_message_xid(self, message_xid: int) -> None:
        assert self.game
        self.game.message_xid = message_xid  # type: ignore
        DatabaseSession.commit()

    @sync_to_async
    @tracer.wrap()
    def fully_seated(self) -> bool:
        assert self.game
        rows = DatabaseSession.query(User).filter(User.game_id == self.game.id).count()
        return rows == self.game.seats

    @sync_to_async
    @tracer.wrap()
    def make_ready(self, spelltable_link: Optional[str]) -> None:
        assert self.game
        assert len(spelltable_link or "") <= MAX_SPELLTABLE_LINK_LEN
        self.game.spelltable_link = spelltable_link  # type: ignore
        self.game.status = GameStatus.STARTED.value  # type: ignore
        self.game.started_at = datetime.utcnow()  # type: ignore
        DatabaseSession.commit()

    @sync_to_async
    @tracer.wrap()
    def player_xids(self) -> list[int]:
        assert self.game
        rows = DatabaseSession.query(User.xid).filter(User.game_id == self.game.id)
        return [int(row[0]) for row in rows]

    @sync_to_async
    @tracer.wrap()
    def watch_notes(self, player_xids: list[int]) -> dict[int, Optional[str]]:
        assert self.game
        watched = (
            DatabaseSession.query(Watch)
            .filter(
                and_(
                    Watch.guild_xid == self.game.guild_xid,
                    Watch.user_xid.in_(player_xids),
                ),
            )
            .all()
        )
        return {watch.user_xid: watch.note for watch in watched}

    @sync_to_async
    @tracer.wrap()
    def record_plays(self) -> None:
        assert self.game
        assert self.game.status == GameStatus.STARTED.value

        rows = DatabaseSession.query(User.xid).filter(User.game_id == self.game.id)
        player_xids = [int(row[0]) for row in rows]

        game_id = self.game.id
        guild_xid = self.game.guild_xid

        # upsert into plays
        DatabaseSession.execute(
            insert(Play)
            .values(
                [dict(user_xid=player_xid, game_id=game_id) for player_xid in player_xids],
            )
            .on_conflict_do_nothing(),
        )

        # upsert into user_awards
        DatabaseSession.execute(
            insert(UserAward)
            .values(
                [dict(guild_xid=guild_xid, user_xid=player_xid) for player_xid in player_xids],
            )
            .on_conflict_do_nothing(),
        )

        DatabaseSession.commit()

    @sync_to_async
    @tracer.wrap()
    def set_voice(self, voice_xid: int, voice_invite_link: str) -> None:
        assert self.game
        assert len(voice_invite_link or "") <= MAX_VOICE_INVITE_LINK_LEN
        self.game.voice_xid = voice_xid  # type: ignore
        self.game.voice_invite_link = voice_invite_link  # type: ignore
        DatabaseSession.commit()

    @sync_to_async
    @tracer.wrap()
    def filter_blocked_list(self, author_xid: int, other_xids: list[int]) -> list[int]:
        """Given an author, filters out any blocked players from a list of others."""
        users_author_has_blocked = [
            row.blocked_user_xid
            for row in DatabaseSession.query(Block).filter(Block.user_xid == author_xid)
        ]
        users_who_blocked_author_or_other = [
            row.user_xid
            for row in DatabaseSession.query(Block).filter(
                Block.blocked_user_xid.in_([author_xid, *other_xids]),
            )
        ]
        return list(
            set(other_xids)
            - set(users_author_has_blocked)
            - set(users_who_blocked_author_or_other),
        )

    @sync_to_async
    @tracer.wrap()
    def blocked(self, author_xid: int) -> bool:
        assert self.game
        users_author_has_blocked = [
            row.blocked_user_xid
            for row in DatabaseSession.query(Block).filter(Block.user_xid == author_xid)
        ]
        users_who_blocked_author = [
            row.user_xid
            for row in DatabaseSession.query(Block).filter(
                Block.blocked_user_xid == author_xid,
            )
        ]
        player_xids = [
            row.xid for row in DatabaseSession.query(User).filter(User.game_id == self.game.id)
        ]
        if any(xid in player_xids for xid in users_author_has_blocked):
            return True
        if any(xid in player_xids for xid in users_who_blocked_author):
            return True
        return False

    @sync_to_async
    @tracer.wrap()
    def players_included(self, player_xid: int) -> bool:
        """
        Players that played this game.

        For current players and pending games, use the players relationship instead.
        """
        assert self.game
        record = (
            DatabaseSession.query(Play)
            .filter(
                and_(
                    Play.user_xid == player_xid,
                    Play.game_id == self.game.id,
                ),
            )
            .one_or_none()
        )
        return bool(record)

    @sync_to_async
    @tracer.wrap()
    def add_points(self, player_xid: int, points: int):
        assert self.game
        values = {
            "user_xid": player_xid,
            "game_id": self.game.id,
            "points": points,
        }
        upsert = insert(Play).values(**values)
        upsert = upsert.on_conflict_do_update(
            constraint="plays_pkey",
            index_where=and_(
                Play.user_xid == values["user_xid"],
                Play.game_id == values["game_id"],
            ),
            set_=dict(points=upsert.excluded.points),
        )
        DatabaseSession.execute(upsert, values)
        DatabaseSession.commit()

    @sync_to_async
    @tracer.wrap()
    def to_dict(self) -> dict[str, Any]:
        assert self.game
        return self.game.to_dict()

    @sync_to_async
    @tracer.wrap()
    def inactive_games(self) -> list[dict[str, Any]]:
        settings = Settings()
        limit = datetime.utcnow() - timedelta(minutes=settings.EXPIRE_TIME_M)
        records = DatabaseSession.query(Game).filter(
            and_(
                Game.status == GameStatus.PENDING.value,
                Game.updated_at <= limit,
                Game.deleted_at.is_(None),
            ),
        )
        return [record.to_dict() for record in records]

    @sync_to_async
    @tracer.wrap()
    def delete_games(self, game_ids: list[int]):
        DatabaseSession.execute(
            update(Game).where(Game.id.in_(game_ids)).values(deleted_at=datetime.utcnow()),
        )
        DatabaseSession.commit()
