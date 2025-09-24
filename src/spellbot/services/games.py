from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast

from asgiref.sync import sync_to_async
from ddtrace.trace import tracer
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import and_, asc, column, or_
from sqlalchemy.sql.functions import count

from spellbot.database import DatabaseSession
from spellbot.models import (
    Block,
    Game,
    GameDict,
    GameStatus,
    Play,
    Post,
    Queue,
    QueueDict,
    UserAward,
    Watch,
)
from spellbot.settings import settings

if TYPE_CHECKING:
    import discord

    from spellbot.operations import VoiceChannelSuggestion


logger = logging.getLogger(__name__)

MAX_GAME_LINK_LEN = Game.game_link.property.columns[0].type.length  # type: ignore


class GamesService:
    game: Game | None = None

    @sync_to_async()
    @tracer.wrap()
    def select(self, game_id: int) -> GameDict | None:
        self.game = DatabaseSession.get(Game, game_id)
        return self.game.to_dict() if self.game else None

    @sync_to_async()
    @tracer.wrap()
    def select_by_voice_xid(self, voice_xid: int) -> bool:
        self.game = DatabaseSession.query(Game).filter(Game.voice_xid == voice_xid).one_or_none()
        return bool(self.game)

    @sync_to_async()
    @tracer.wrap()
    def select_by_message_xid(self, message_xid: int) -> GameDict | None:
        self.game = (
            DatabaseSession.query(Game)
            .join(Post)
            .filter(Post.message_xid == message_xid)
            .one_or_none()
        )
        return self.game.to_dict() if self.game else None

    @sync_to_async()
    @tracer.wrap()
    def add_player(self, player_xid: int) -> None:
        assert self.game

        rows = DatabaseSession.query(Queue).filter(Queue.game_id == self.game.id).count()
        assert rows + 1 <= self.game.seats

        # upsert into queues
        DatabaseSession.execute(
            insert(Queue)
            .values(
                [
                    {
                        "user_xid": player_xid,
                        "game_id": self.game.id,
                        "og_guild_xid": self.game.guild_xid,
                    },
                ],
            )
            .on_conflict_do_nothing(),
        )
        DatabaseSession.commit()

        # This operation should "dirty" the Game, so we need to update its updated_at.
        query = (
            update(Game)  # type: ignore
            .where(Game.id == self.game.id)
            .values(updated_at=datetime.now(tz=UTC))
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async()
    @tracer.wrap()
    def upsert(
        self,
        *,
        guild_xid: int,
        channel_xid: int,
        author_xid: int,
        friends: list[int],
        seats: int,
        rules: str | None,
        format: int,
        bracket: int,
        service: int,
        create_new: bool = False,
        blind: bool = False,
    ) -> bool:
        existing: Game | None = None
        if not create_new:
            existing = self._find_existing(
                guild_xid=guild_xid,
                channel_xid=channel_xid,
                author_xid=author_xid,
                friends=friends,
                seats=seats,
                rules=rules,
                format=format,
                bracket=bracket,
                service=service,
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
                rules=rules,
                format=format,
                bracket=bracket,
                service=service,
                blind=blind,
            )
            DatabaseSession.add(game)
            DatabaseSession.commit()
            new = True

        # upsert into queues
        user_xids = [*friends, author_xid]
        DatabaseSession.execute(
            insert(Queue)
            .values(
                [
                    {
                        "user_xid": xid,
                        "game_id": game.id,
                        "og_guild_xid": guild_xid,
                    }
                    for xid in user_xids
                ],
            )
            .on_conflict_do_nothing(),
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
        rules: str | None,
        format: int,
        bracket: int,
        service: int,
    ) -> Game | None:
        required_seats = 1 + len(friends)

        player_count = count(Queue.user_xid).over(partition_by=Game.id)
        inner = (
            select(
                Game,  # type: ignore
                Queue.user_xid,
                player_count.label("player_count"),  # type: ignore
            )
            .join(Queue, isouter=True)  # type: ignore
            .filter(  # type: ignore
                and_(
                    Game.guild_xid == guild_xid,
                    Game.channel_xid == channel_xid,
                    Game.seats == seats,
                    Game.rules == rules,
                    Game.format == format,
                    Game.bracket == bracket,
                    Game.service == service,
                    Game.status == GameStatus.PENDING.value,
                    Game.deleted_at.is_(None),
                ),
            )
            .group_by(Game, Queue.user_xid)
            .order_by(asc(Game.updated_at))
            .alias("inner")
        )
        outer = aliased(Game, inner)
        found = DatabaseSession.query(outer).filter(
            or_(
                column("player_count") == 0,
                and_(
                    column("player_count") > 0,
                    column("player_count") <= seats - required_seats,
                ),
            ),
        )

        joiners = [author_xid, *friends]
        xids_blocked_by_joiners = [
            row.blocked_user_xid
            for row in DatabaseSession.query(Block).filter(Block.user_xid.in_(joiners))
        ]

        game: Game
        for game in found.all():
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

    @sync_to_async()
    @tracer.wrap()
    def to_embed(
        self,
        *,
        guild: discord.Guild | None,
        dm: bool = False,
        suggested_vc: VoiceChannelSuggestion | None = None,
        rematch: bool = False,
    ) -> discord.Embed:
        assert self.game
        return self.game.to_embed(guild=guild, dm=dm, suggested_vc=suggested_vc, rematch=rematch)

    @sync_to_async()
    @tracer.wrap()
    def add_post(self, guild_xid: int, channel_xid: int, message_xid: int) -> None:
        assert self.game
        DatabaseSession.execute(
            insert(Post)
            .values(
                [
                    {
                        "game_id": self.game.id,
                        "guild_xid": guild_xid,
                        "channel_xid": channel_xid,
                        "message_xid": message_xid,
                    },
                ],
            )
            .on_conflict_do_nothing(),
        )
        DatabaseSession.commit()

    @sync_to_async()
    @tracer.wrap()
    def fully_seated(self) -> bool:
        assert self.game
        rows = DatabaseSession.query(Queue).filter(Queue.game_id == self.game.id).count()
        return rows == self.game.seats

    @sync_to_async
    @tracer.wrap()
    def other_game_ids(self) -> list[int]:
        """Use the currently selected game, return any other games with overlapping players."""
        assert self.game
        player_xids = self.game.player_xids
        rows = DatabaseSession.query(Queue.game_id).filter(
            Queue.user_xid.in_(player_xids),
            Queue.game_id != self.game.id,
        )
        return [int(row[0]) for row in rows if row[0]]

    @sync_to_async()
    @tracer.wrap()
    def make_ready(self, game_link: str | None, password: str | None) -> int:
        assert self.game
        assert len(game_link or "") <= MAX_GAME_LINK_LEN
        queues: list[QueueDict] = [
            queue.to_dict()
            for queue in DatabaseSession.query(Queue).filter(Queue.game_id == self.game.id).all()
        ]

        # update game's state
        self.game.game_link = game_link  # column is "game_link" for legacy reasons
        self.game.password = password
        self.game.status = GameStatus.STARTED.value
        self.game.started_at = datetime.now(tz=UTC)

        if not queues:  # Not sure this is possible, but just in case.
            DatabaseSession.commit()
            return cast("int", self.game.id)

        # upsert into plays
        DatabaseSession.execute(
            insert(Play)
            .values(
                [
                    {
                        "user_xid": queue["user_xid"],
                        "game_id": self.game.id,
                        "og_guild_xid": queue["og_guild_xid"],
                    }
                    for queue in queues
                ],
            )
            .on_conflict_do_nothing(),
        )

        # upsert into user_awards
        DatabaseSession.execute(
            insert(UserAward)
            .values(
                [
                    {
                        "guild_xid": self.game.guild_xid,
                        "user_xid": queue["user_xid"],
                    }
                    for queue in queues
                ],
            )
            .on_conflict_do_nothing(),
        )

        # drop the players from any other queues
        player_xids = [queue["user_xid"] for queue in queues]
        DatabaseSession.query(Queue).filter(Queue.user_xid.in_(player_xids)).delete(
            synchronize_session=False,
        )

        DatabaseSession.commit()
        return cast("int", self.game.id)

    @sync_to_async()
    @tracer.wrap()
    def player_xids(self) -> list[int]:
        assert self.game
        return self.game.player_xids

    @sync_to_async()
    @tracer.wrap()
    def player_pins(self) -> dict[int, str | None]:
        assert self.game
        return self.game.player_pins

    @sync_to_async()
    @tracer.wrap()
    def player_names(self) -> dict[int, str | None]:
        assert self.game
        return self.game.player_names

    @sync_to_async()
    @tracer.wrap()
    def watch_notes(self, player_xids: list[int]) -> dict[int, str | None]:
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
        return {cast("int", watch.user_xid): cast("str | None", watch.note) for watch in watched}

    @sync_to_async()
    @tracer.wrap()
    def set_voice(self, *, voice_xid: int, voice_invite_link: str | None = None) -> None:
        assert self.game
        self.game.voice_xid = voice_xid
        self.game.voice_invite_link = voice_invite_link
        DatabaseSession.commit()

    @sync_to_async()
    @tracer.wrap()
    def filter_blocked_list(self, author_xid: int, other_xids: list[int]) -> list[int]:
        """Given an author, filters out any blocked players from a list of others."""
        users_author_has_blocked = [
            cast("int", row.blocked_user_xid)
            for row in DatabaseSession.query(Block).filter(Block.user_xid == author_xid)
            if row
        ]
        users_who_blocked_author_or_other = [
            cast("int", row.user_xid)
            for row in DatabaseSession.query(Block).filter(
                Block.blocked_user_xid.in_([author_xid, *other_xids]),
            )
        ]
        return list(
            set(other_xids)
            - set(users_author_has_blocked)
            - set(users_who_blocked_author_or_other),
        )

    @sync_to_async()
    @tracer.wrap()
    def filter_pending_games(self, user_xids: list[int]) -> list[int]:
        rows = DatabaseSession.query(
            Queue.user_xid,
            func.count(Queue.user_xid).label("pending"),
        ).group_by(Queue.user_xid)
        counts = {row[0]: row[1] for row in rows if row[0]}

        return [
            user_xid
            for user_xid in user_xids
            if counts.get(user_xid, 0) + 1 < settings.MAX_PENDING_GAMES
        ]

    @sync_to_async()
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
        player_xids = self.game.player_xids
        if any(xid in player_xids for xid in users_author_has_blocked):
            return True
        return any(xid in player_xids for xid in users_who_blocked_author)

    @sync_to_async()
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

    @sync_to_async()
    @tracer.wrap()
    def to_dict(self) -> GameDict:
        assert self.game
        return self.game.to_dict()

    @sync_to_async()
    @tracer.wrap()
    def inactive_games(self) -> list[GameDict]:
        limit = datetime.now(tz=UTC) - timedelta(minutes=settings.EXPIRE_TIME_M)
        records = (
            DatabaseSession.query(Game)
            .join(Queue, isouter=True)
            .filter(
                Game.status == GameStatus.PENDING.value,
                Game.deleted_at.is_(None),
            )
            .group_by(Game)
            .having(
                or_(
                    Game.updated_at <= limit,
                    func.count(Queue.game_id) == 0,
                ),
            )
        )
        return [record.to_dict() for record in records]

    @sync_to_async()
    @tracer.wrap()
    def delete_games(self, game_ids: list[int]) -> int:
        query = (
            update(Game)  # type: ignore
            .where(Game.id.in_(game_ids))
            .values(deleted_at=datetime.now(tz=UTC))
        )
        DatabaseSession.execute(query)
        dequeued = (
            DatabaseSession.query(Queue)
            .filter(Queue.game_id.in_(game_ids))
            .delete(synchronize_session=False)
        )
        logger.info("dequeued %s players from games %s", dequeued, game_ids)
        DatabaseSession.commit()
        return dequeued

    @sync_to_async()
    @tracer.wrap()
    def message_xids(self, game_ids: list[int]) -> list[int]:
        query = select(
            Post.message_xid,  # type: ignore
        ).where(Post.game_id.in_(game_ids))
        return [int(row[0]) for row in DatabaseSession.execute(query) if row[0]]

    @sync_to_async()
    @tracer.wrap()
    def dequeue_players(self, player_xids: list[int]) -> list[int]:
        """Remove the given players from any queues that they're in; returns changed game ids."""
        queues = DatabaseSession.query(Queue).filter(Queue.user_xid.in_(player_xids)).all()
        game_ids = {cast("int", queue.game_id) for queue in queues}
        for queue in queues:
            DatabaseSession.delete(queue)
        DatabaseSession.commit()
        return list(game_ids)

    @sync_to_async()
    @tracer.wrap()
    def select_last_game(self, user_xid: int, guild_xid: int) -> GameDict | None:
        self.game = (
            DatabaseSession.query(Game)
            .filter(
                Game.guild_xid == guild_xid,
                Game.status == GameStatus.STARTED.value,
                Game.deleted_at.is_(None),
                Play.user_xid == user_xid,
            )
            .join(Play)
            .order_by(Game.created_at.desc())
            .first()
        )
        return self.game.to_dict() if self.game else None
