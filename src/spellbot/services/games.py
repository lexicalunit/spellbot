from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import permutations
from typing import TYPE_CHECKING, cast

import pytz
from asgiref.sync import sync_to_async
from ddtrace import tracer
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import and_, asc, column, or_
from sqlalchemy.sql.functions import count

from spellbot.database import DatabaseSession
from spellbot.models import (
    Block,
    Channel,
    Game,
    GameDict,
    GameStatus,
    MirrorDict,
    Play,
    PlayDict,
    Post,
    Queue,
    QueueDict,
    Record,
    RecordDict,
    UserAward,
    Watch,
)
from spellbot.settings import settings

if TYPE_CHECKING:
    import discord

logger = logging.getLogger(__name__)

MAX_SPELLTABLE_LINK_LEN = Game.spelltable_link.property.columns[0].type.length  # type: ignore


class GamesService:
    game: Game | None = None

    @sync_to_async()
    @tracer.wrap()
    def select(self, game_id: int) -> GameDict | None:
        self.game = DatabaseSession.query(Game).get(game_id)
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
    def select_last_ranked_game(self, user_xid: int) -> GameDict | None:
        self.game = (
            DatabaseSession.query(Game)
            .join(Play)
            .join(Channel)
            .filter(
                Play.user_xid == user_xid,
                Play.confirmed_at.is_(None),
                Game.status == GameStatus.STARTED.value,
                Game.requires_confirmation.is_(True),
                Channel.require_confirmation.is_(True),
            )
            .order_by(Game.started_at.desc())
            .first()
        )
        return self.game.to_dict() if self.game else None

    @sync_to_async()
    @tracer.wrap()
    def get_plays(self) -> dict[int, PlayDict]:
        assert self.game
        plays = DatabaseSession.query(Play).filter(Play.game_id == self.game.id).all()
        return {play.user_xid: play.to_dict() for play in plays}

    @sync_to_async()
    @tracer.wrap()
    def get_record(self, guild_xid: int, channel_xid: int, user_xid: int) -> RecordDict:
        record = (
            DatabaseSession.query(Record)
            .filter(
                Record.guild_xid == guild_xid,
                Record.channel_xid == channel_xid,
                Record.user_xid == user_xid,
            )
            .one_or_none()
        )
        if not record:
            record = Record(
                guild_xid=guild_xid,
                channel_xid=channel_xid,
                user_xid=user_xid,
                elo=1500,
            )
            DatabaseSession.add(record)
            DatabaseSession.commit()
        return record.to_dict()

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
                    }
                ]
            )
            .on_conflict_do_nothing(),
        )
        DatabaseSession.commit()

        # This operation should "dirty" the Game, so we need to update its updated_at.
        query = (
            update(Game)
            .where(Game.id == self.game.id)
            .values(updated_at=datetime.now(tz=pytz.utc))
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
        format: int,
        service: int,
        create_new: bool = False,
        mirrors: list[MirrorDict] | None = None,
    ) -> bool:
        mirrors = mirrors or []
        existing: Game | None = None
        if not create_new:
            existing = self._find_existing(
                guild_xid=guild_xid,
                channel_xid=channel_xid,
                author_xid=author_xid,
                friends=friends,
                seats=seats,
                format=format,
                service=service,
                mirrors=mirrors,
            )

        new: bool
        game: Game
        if existing:
            game = existing
            new = False
        else:
            channel = DatabaseSession.query(Channel).get(channel_xid)
            game = Game(
                guild_xid=guild_xid,
                channel_xid=channel_xid,
                seats=seats,
                format=format,
                service=service,
                requires_confirmation=channel.require_confirmation,
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
                ]
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
        format: int,
        service: int,
        mirrors: list[MirrorDict] | None = None,
    ) -> Game | None:
        mirrors = mirrors or []
        required_seats = 1 + len(friends)

        guild_channel_filter = or_(
            *[
                and_(
                    Game.guild_xid == gid,
                    Game.channel_xid == cid,
                )
                for gid, cid in [
                    (guild_xid, channel_xid),
                    *[(m["to_guild_xid"], m["to_channel_xid"]) for m in mirrors],
                ]
            ]
        )

        player_count = count(Queue.user_xid).over(partition_by=Game.id)
        inner = (
            select(
                Game,
                Queue.user_xid,
                player_count.label("player_count"),  # type: ignore
            )
            .join(Queue, isouter=True)
            .filter(  # type: ignore
                and_(
                    guild_channel_filter,
                    Game.seats == seats,
                    Game.format == format,
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
    def to_embed(self, dm: bool = False) -> discord.Embed:
        assert self.game
        return self.game.to_embed(dm)

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
                    }
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
    def make_ready(self, spelltable_link: str | None) -> int:
        assert self.game
        assert len(spelltable_link or "") <= MAX_SPELLTABLE_LINK_LEN
        queues: list[QueueDict] = [
            queue.to_dict()
            for queue in DatabaseSession.query(Queue).filter(Queue.game_id == self.game.id).all()
        ]

        # update game's state
        self.game.spelltable_link = spelltable_link
        self.game.status = GameStatus.STARTED.value
        self.game.started_at = datetime.now(tz=pytz.utc)

        if not queues:  # Not sure this is possible, but just in case.
            DatabaseSession.commit()
            return cast(int, self.game.id)

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
        return cast(int, self.game.id)

    @sync_to_async()
    @tracer.wrap()
    def player_xids(self) -> list[int]:
        assert self.game
        return self.game.player_xids

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
        return {cast(int, watch.user_xid): cast(str | None, watch.note) for watch in watched}

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
            cast(int, row.blocked_user_xid)
            for row in DatabaseSession.query(Block).filter(Block.user_xid == author_xid)
            if row
        ]
        users_who_blocked_author_or_other = [
            cast(int, row.user_xid)
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
        if any(xid in player_xids for xid in users_who_blocked_author):
            return True
        return False

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
    def add_points(self, player_xid: int, points: int) -> None:
        assert self.game
        values = {
            "user_xid": player_xid,
            "game_id": self.game.id,
            "points": points,
            "og_guild_xid": self.game.guild_xid,
        }
        upsert = insert(Play).values(**values)
        upsert = upsert.on_conflict_do_update(
            constraint="plays_pkey",
            index_where=and_(
                Play.user_xid == values["user_xid"],
                Play.game_id == values["game_id"],
            ),
            set_={
                "points": upsert.excluded.points,
                "og_guild_xid": upsert.excluded.og_guild_xid,
            },
        )
        DatabaseSession.execute(upsert, values)
        DatabaseSession.commit()

    @sync_to_async()
    @tracer.wrap()
    def confirm_points(self, player_xid: int) -> datetime:
        assert self.game
        confirmed_at = datetime.now(tz=pytz.utc)
        query = (
            update(Play)
            .where(
                and_(
                    Play.game_id == self.game.id,
                    Play.user_xid == player_xid,
                ),
            )
            .values(confirmed_at=confirmed_at)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()
        return confirmed_at

    @sync_to_async()
    @tracer.wrap()
    def update_records(self, plays: dict[int, PlayDict]) -> None:  # noqa: C901
        assert self.game
        guild_xid = self.game.guild_xid
        channel_xid = self.game.channel_xid
        records: dict[int, Record] = {
            r.user_xid: r
            for r in DatabaseSession.query(Record).filter(
                Record.guild_xid == guild_xid,
                Record.channel_xid == channel_xid,
            )
        }
        if len(records) != len(plays):
            # some players may not have Record objects for this guild/channel yet, so
            # we must create them now (giving each player their default ELO scores).
            for user_xid in plays:
                if user_xid not in records:
                    record = Record(
                        guild_xid=guild_xid,
                        channel_xid=channel_xid,
                        user_xid=user_xid,
                        elo=1500,
                    )
                    DatabaseSession.add(record)
                    records[user_xid] = record

        assert len(records) == len(plays)

        def place(play: PlayDict) -> int:
            points = play["points"] or 0
            if points >= 3:  # first place
                return 1
            if points > 0:  # second place
                return 2
            return 3  # last place

        def calc_s(play1: PlayDict, play2: PlayDict):
            if place(play1) < place(play2):
                return 1.0
            if place(play1) == place(play2):
                return 0.5
            return 0.0

        def calc_ea(rec1: Record, rec2: Record):
            return 1 / (1.0 + pow(10.0, (rec2.elo - rec1.elo) / 400.0))

        def calc_elo_change(play1: PlayDict, rec1: Record, play2: PlayDict, rec2: Record, k: int):
            s = calc_s(play1, play2)
            ea = calc_ea(rec1, rec2)
            return round(k * (s - ea))

        n = len(records)
        k = 32  # growth rate
        player_to_player = list(permutations(range(n), 2))

        elo_changes = defaultdict(int)
        plays_list = sorted(plays.values(), key=lambda p: p["user_xid"])
        records_list = sorted(records.values(), key=lambda r: r.user_xid)
        for i, j in player_to_player:
            elo_changes[i] += calc_elo_change(
                plays_list[i], records_list[i], plays_list[j], records_list[j], k
            )
        for i in range(n):
            before = records_list[i].elo
            after = before + elo_changes[i]
            print(f"ELO {records_list[i].user_xid}, {before} -> {after} ...")  # noqa: T201
            records_list[i].elo = after  # type: ignore
        DatabaseSession.commit()

    @sync_to_async()
    @tracer.wrap()
    def to_dict(self) -> GameDict:
        assert self.game
        return self.game.to_dict()

    @sync_to_async()
    @tracer.wrap()
    def inactive_games(self) -> list[GameDict]:
        limit = datetime.now(tz=pytz.utc) - timedelta(minutes=settings.EXPIRE_TIME_M)
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
            update(Game).where(Game.id.in_(game_ids)).values(deleted_at=datetime.now(tz=pytz.utc))
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
        game_ids = {cast(int, queue.game_id) for queue in queues}
        for queue in queues:
            DatabaseSession.delete(queue)
        DatabaseSession.commit()
        return list(game_ids)
