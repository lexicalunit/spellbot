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

from spellbot.data import PlayerDataDict
from spellbot.database import DatabaseSession
from spellbot.models import (
    Block,
    Game,
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
    from spellbot.data import GameData


logger = logging.getLogger(__name__)

MAX_GAME_LINK_LEN = Game.game_link.property.columns[0].type.length  # type: ignore


class GamesService:
    @sync_to_async()
    @tracer.wrap()
    def get(self, game_id: int) -> GameData | None:
        """Fetch the game data by game id."""
        game: Game | None = DatabaseSession.get(Game, game_id)
        return game.to_dict() if game else None

    @sync_to_async()
    @tracer.wrap()
    def get_by_voice_xid(self, voice_xid: int) -> GameData | None:
        """Fetch the game data by associated discord voice channel id."""
        game: Game | None = (
            DatabaseSession.query(Game).filter(Game.voice_xid == voice_xid).one_or_none()
        )
        return game.to_dict() if game else None

    @sync_to_async()
    @tracer.wrap()
    def get_by_message_xid(self, message_xid: int) -> GameData | None:
        """Fetch the game data by associated discord message id."""
        game: Game | None = (
            DatabaseSession.query(Game)
            .join(Post)
            .filter(Post.message_xid == message_xid)
            .one_or_none()
        )
        return game.to_dict() if game else None

    @sync_to_async()
    @tracer.wrap()
    def add_player(self, game_data: GameData, player_xid: int) -> GameData:
        """Add the player with the given id to the given game."""
        # Double check that the number of players + 1 doesn't go over the seat limit,
        # this should in theory never happen. If we see this assertion failing, investigate.
        players: int = DatabaseSession.query(Queue).filter(Queue.game_id == game_data.id).count()
        assert players + 1 <= game_data.seats

        # upsert into queues
        DatabaseSession.execute(
            insert(Queue)
            .values(
                [
                    {
                        "user_xid": player_xid,
                        "game_id": game_data.id,
                        "og_guild_xid": game_data.guild_xid,
                    },
                ],
            )
            .on_conflict_do_nothing(),
        )
        DatabaseSession.commit()

        # This operation should "dirty" the Game, so we need to update its updated_at.
        query = (
            update(Game)  # type: ignore
            .where(Game.id == game_data.id)
            .values(updated_at=datetime.now(tz=UTC))
            .returning(Game)  # type: ignore
            .execution_options(synchronize_session="fetch")
        )
        result = DatabaseSession.scalars(query)
        updated_game: Game = result.one()
        DatabaseSession.commit()
        return updated_game.to_dict()

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
    ) -> tuple[bool, GameData]:
        """Create or update a new game matching the given criteria."""
        existing_game: Game | None = None
        if not create_new:
            existing_game = self._find_existing(
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
        if existing_game:
            game = existing_game
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

        return new, game.to_dict()

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
        """Find a suitable existing game with the given criteria if one exists."""
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
        found_game = DatabaseSession.query(outer).filter(
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

        # Return the first game that doesn't match up players who have blocked each other
        game: Game
        for game in found_game.all():
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
    def add_post(
        self,
        game_data: GameData,
        guild_xid: int,
        channel_xid: int,
        message_xid: int,
    ) -> GameData:
        """Associate the given game with the given Discord post metadata."""
        query = (
            insert(Post)
            .values(
                [
                    {
                        "game_id": game_data.id,
                        "guild_xid": guild_xid,
                        "channel_xid": channel_xid,
                        "message_xid": message_xid,
                    },
                ],
            )
            .on_conflict_do_nothing()
            .returning(Post)
        )
        result = DatabaseSession.scalars(query)
        new_post: Post | None = result.one_or_none()
        DatabaseSession.commit()
        if new_post is not None:
            game_data.posts.append(new_post.to_dict())
        return game_data

    @sync_to_async
    @tracer.wrap()
    def other_game_ids(self, game_data: GameData) -> list[int]:
        """Return the id of any other games with overlapping players."""
        player_xids = [player.xid for player in game_data.players]
        rows = DatabaseSession.query(Queue.game_id).filter(
            Queue.user_xid.in_(player_xids),
            Queue.game_id != game_data.id,
        )
        return [int(row[0]) for row in rows if row[0]]

    @sync_to_async()
    @tracer.wrap()
    def shrink_game(self, game_data: GameData) -> GameData:
        """Shrink the number of seats in a game to the current number of players."""
        query = (
            update(Game)  # type: ignore
            .where(Game.id == game_data.id)
            .values(seats=len(game_data.players))
            .returning(Game)  # type: ignore
        )
        result = DatabaseSession.scalars(query)
        updated_game: Game = result.one()
        DatabaseSession.commit()
        return updated_game.to_dict()

    @sync_to_async()
    @tracer.wrap()
    def make_ready(
        self,
        game_data: GameData,
        game_link: str | None,
        password: str | None,
        pins: list[str],
    ) -> GameData:
        """Start the pending game."""
        game: Game = DatabaseSession.get(Game, game_data.id)  # TODO: Refactor to avoid fetch?
        assert len(game_link or "") <= MAX_GAME_LINK_LEN
        queues: list[QueueDict] = [
            queue.to_dict()
            for queue in DatabaseSession.query(Queue).filter(Queue.game_id == game.id).all()
        ]

        # update game's state
        game.game_link = game_link  # column is "game_link" for legacy reasons  # type: ignore
        game.password = password  # type: ignore
        game.status = GameStatus.STARTED.value
        game.started_at = datetime.now(tz=UTC)  # type: ignore

        if not queues:  # Not sure this is possible, but just in case.
            DatabaseSession.commit()
            return game.to_dict()

        # upsert into plays
        DatabaseSession.execute(
            insert(Play)
            .values(
                [
                    {
                        "user_xid": queue["user_xid"],
                        "game_id": game.id,
                        "og_guild_xid": queue["og_guild_xid"],
                        "pin": pins[i],
                    }
                    for i, queue in enumerate(queues)
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
                        "guild_xid": game.guild_xid,
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
        return game.to_dict()

    @sync_to_async()
    @tracer.wrap()
    def watch_notes(self, game_data: GameData, player_xids: list[int]) -> dict[int, str | None]:
        """Return any moderator watch notes for the given game."""
        watched = (
            DatabaseSession.query(Watch)
            .filter(
                and_(
                    Watch.guild_xid == game_data.guild_xid,
                    Watch.user_xid.in_(player_xids),
                ),
            )
            .all()
        )
        return {cast("int", watch.user_xid): cast("str | None", watch.note) for watch in watched}

    @sync_to_async()
    @tracer.wrap()
    def set_voice(
        self,
        game_data: GameData,
        *,
        voice_xid: int,
        voice_invite_link: str | None = None,
    ) -> GameData:
        """Assign the given voice channel information to the given game."""
        query = (
            update(Game)  # type: ignore
            .where(Game.id == game_data.id)
            .values(voice_xid=voice_xid, voice_invite_link=voice_invite_link)
            .returning(Game)  # type: ignore
        )
        result = DatabaseSession.scalars(query)
        updated_game: Game = result.one()
        DatabaseSession.commit()
        return updated_game.to_dict()

    @sync_to_async()
    @tracer.wrap()
    def blocked(self, game_data: GameData, user_xid: int) -> bool:
        """Return True iff the given user should not be allowed in the given game."""
        users_author_has_blocked = [
            row.blocked_user_xid
            for row in DatabaseSession.query(Block).filter(Block.user_xid == user_xid)
        ]
        users_who_blocked_author = [
            row.user_xid
            for row in DatabaseSession.query(Block).filter(
                Block.blocked_user_xid == user_xid,
            )
        ]
        player_xids = [player.xid for player in game_data.players]
        if any(xid in player_xids for xid in users_author_has_blocked):
            return True
        return any(xid in player_xids for xid in users_who_blocked_author)

    @sync_to_async()
    @tracer.wrap()
    def inactive_games(self, guild_xid: int | None = None) -> list[GameData]:
        """Return any games that should be considered abandoned for inactivity."""
        limit = datetime.now(tz=UTC) - timedelta(minutes=settings.EXPIRE_TIME_M)
        filters = [
            Game.status == GameStatus.PENDING.value,
            Game.deleted_at.is_(None),
        ]
        if guild_xid:
            filters.append(Game.guild_xid == guild_xid)
        records = (
            DatabaseSession.query(Game)
            .join(Queue, isouter=True)
            .filter(*filters)
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
        """Delete the games with the given ids."""
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
        """Return the discord post message ids for the given game ids."""
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
    def get_last_game(self, user_xid: int, guild_xid: int) -> GameData | None:
        """Get the last game played by the given user in the given guild."""
        last_game = (
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
        return last_game.to_dict() if last_game else None

    # A helper function for Convoke game creation. Would be nice to refactor to remove!
    @sync_to_async()
    @tracer.wrap()
    def player_convoke_data(self, game_id: int) -> list[PlayerDataDict]:
        """Return the player data for the given game id."""
        game = DatabaseSession.query(Game).filter(Game.id == game_id).first()
        if not game:
            return []
        return [PlayerDataDict(xid=p.xid, name=p.name) for p in game.players]
