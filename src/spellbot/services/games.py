from datetime import datetime
from typing import Optional

import discord
from asgiref.sync import sync_to_async
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import and_, asc, column, or_, select
from sqlalchemy.sql.functions import count

from spellbot.database import DatabaseSession
from spellbot.models.award import UserAward
from spellbot.models.block import Block
from spellbot.models.game import Game, GameStatus
from spellbot.models.play import Play
from spellbot.models.user import User
from spellbot.models.watch import Watch
from spellbot.services import BaseService

MAX_SPELLTABLE_LINK_LEN = Game.spelltable_link.property.columns[  # type: ignore
    0
].type.length
MAX_VOICE_INVITE_LINK_LEN = Game.voice_invite_link.property.columns[  # type: ignore
    0
].type.length


class GamesService(BaseService):
    game: Optional[Game] = None

    @sync_to_async
    def select(self, game_id: int) -> bool:
        self.game = DatabaseSession.query(Game).get(game_id)
        return bool(self.game)

    @sync_to_async
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
    def select_by_message_xid(self, message_xid: int) -> bool:
        self.game = (
            DatabaseSession.query(Game)
            .filter(
                Game.message_xid == message_xid,
            )
            .one_or_none()
        )
        return bool(self.game)

    @sync_to_async
    def add_player(self, player_xid: int) -> None:
        assert self.game
        assert len(self.game.players) + 1 <= self.game.seats
        query = update(User).where(User.xid == player_xid).values(game_id=self.game.id)
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async
    def upsert(
        self,
        *,
        guild_xid: int,
        channel_xid: int,
        author_xid: int,
        friends: list[int],
        seats: int,
        format: int,
    ) -> bool:
        required_seats = 1 + len(friends)
        inner = (
            select(
                [
                    Game,
                    User.xid.label("users_xid"),
                    count(User.xid).over(partition_by=Game.id).label("player_count"),
                ]
            )
            .join(User, isouter=True)
            .filter(  # type: ignore
                and_(
                    Game.guild_xid == guild_xid,
                    Game.channel_xid == channel_xid,
                    Game.seats == seats,
                    Game.format == format,
                    Game.status == GameStatus.PENDING.value,
                )
            )
            .group_by(Game, User.xid)
            .order_by(asc(Game.updated_at))
            .alias("inner")
        )
        user_blocks = DatabaseSession.query(Block.blocked_user_xid).filter_by(
            user_xid=author_xid
        )
        blocks_user = DatabaseSession.query(Block.user_xid).filter_by(
            blocked_user_xid=author_xid
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
                        ~inner.c.users_xid.in_(user_blocks),
                        ~inner.c.users_xid.in_(blocks_user),
                    ),
                )
            )
        )
        existing = outer.first()

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
        )
        DatabaseSession.commit()
        self.game = game
        return new

    @sync_to_async
    def to_embed(self, dm: bool = False) -> discord.Embed:
        assert self.game
        return self.game.to_embed(dm)

    @sync_to_async
    def set_message_xid(self, message_xid: int) -> None:
        assert self.game
        self.game.message_xid = message_xid  # type: ignore
        DatabaseSession.commit()

    @sync_to_async
    def current_guild_xid(self) -> int:
        assert self.game
        assert self.game.guild_xid
        return self.game.guild_xid

    @sync_to_async
    def current_channel_xid(self) -> int:
        assert self.game
        assert self.game.channel_xid
        return self.game.channel_xid

    @sync_to_async
    def current_message_xid(self) -> int:
        assert self.game
        assert self.game.message_xid
        return self.game.message_xid

    @sync_to_async
    def fully_seated(self) -> bool:
        assert self.game
        return self.game.seats == len(self.game.players)

    @sync_to_async
    def make_ready(self, spelltable_link: Optional[str]) -> None:
        assert self.game
        assert len(spelltable_link or "") <= MAX_SPELLTABLE_LINK_LEN
        self.game.spelltable_link = spelltable_link  # type: ignore
        self.game.status = GameStatus.STARTED.value  # type: ignore
        self.game.started_at = datetime.utcnow()  # type: ignore
        DatabaseSession.commit()

    @sync_to_async
    def current_player_xids(self) -> list[int]:
        assert self.game
        return [player.xid for player in self.game.players]

    @sync_to_async
    def watch_notes(self, player_xids: list[int]) -> dict[int, Optional[str]]:
        assert self.game
        watched = (
            DatabaseSession.query(Watch)
            .filter(
                and_(
                    Watch.guild_xid == self.game.guild_xid,
                    Watch.user_xid.in_(player_xids),
                )
            )
            .all()
        )
        return {watch.user_xid: watch.note for watch in watched}

    @sync_to_async
    def record_plays(self) -> None:
        assert self.game
        assert self.game.status == GameStatus.STARTED.value

        player_xids = [player.xid for player in self.game.players]
        game_id = self.game.id
        guild_xid = self.game.guild_xid

        # upsert into plays
        DatabaseSession.execute(
            insert(Play)
            .values(
                [dict(user_xid=player_xid, game_id=game_id) for player_xid in player_xids]
            )
            .on_conflict_do_nothing()
        )

        # upsert into user_awards
        DatabaseSession.execute(
            insert(UserAward)
            .values(
                [
                    dict(guild_xid=guild_xid, user_xid=player_xid)
                    for player_xid in player_xids
                ]
            )
            .on_conflict_do_nothing()
        )

        DatabaseSession.commit()

    @sync_to_async
    def current_id(self) -> int:
        assert self.game
        return self.game.id

    @sync_to_async
    def set_voice(self, voice_xid: int, voice_invite_link: str) -> None:
        assert self.game
        assert len(voice_invite_link or "") <= MAX_VOICE_INVITE_LINK_LEN
        self.game.voice_xid = voice_xid  # type: ignore
        self.game.voice_invite_link = voice_invite_link  # type: ignore
        DatabaseSession.commit()

    @sync_to_async
    def filter_blocked(self, author_xid: int, other_xids: list[int]) -> list[int]:
        blockers = (
            DatabaseSession.query(Block)
            .filter(
                or_(
                    and_(
                        Block.user_xid == author_xid,
                        Block.blocked_user_xid.in_(other_xids),
                    ),
                    and_(
                        Block.blocked_user_xid == author_xid,
                        Block.user_xid.in_(other_xids),
                    ),
                )
            )
            .all()
        )
        return list(
            set(other_xids)
            - set(blocker.user_xid for blocker in blockers)
            - set(blocker.blocked_user_xid for blocker in blockers)
        )

    @sync_to_async
    def blocked(self, author_xid: int) -> bool:
        assert self.game
        other_player_xids = [player.xid for player in self.game.players]
        query = DatabaseSession.query(Block).filter(
            or_(
                and_(
                    Block.user_xid == author_xid,
                    Block.blocked_user_xid.in_(other_player_xids),
                ),
                and_(
                    Block.blocked_user_xid == author_xid,
                    Block.user_xid.in_(other_player_xids),
                ),
            )
        )
        return bool(DatabaseSession.query(query.exists()).scalar())

    @sync_to_async
    def jump_link(self) -> str:
        assert self.game
        return self.game.jump_link

    @sync_to_async
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
                )
            )
            .one_or_none()
        )
        return bool(record)

    @sync_to_async
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
