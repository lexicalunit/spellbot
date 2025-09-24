from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy.sql.expression import and_

from spellbot.database import DatabaseSession
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.models import (
    Channel,
    Game,
    GameStatus,
    Guild,
    Post,
    Queue,
    User,
)
from spellbot.services import GamesService
from tests.factories import (
    BlockFactory,
    ChannelFactory,
    GameFactory,
    GuildFactory,
    PlayFactory,
    PostFactory,
    QueueFactory,
    UserFactory,
    WatchFactory,
)

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestServiceGames:
    async def test_games_select(self, game: Game) -> None:
        games = GamesService()
        assert await games.select(game.id)
        assert not await games.select(404)

    async def test_games_select_by_voice_xid(self, guild: Guild, channel: Channel) -> None:
        game = GameFactory.create(guild=guild, channel=channel, voice_xid=12345)

        games = GamesService()
        assert await games.select_by_voice_xid(game.voice_xid)
        assert not await games.select_by_voice_xid(404)

    async def test_games_select_by_message_xid(self, guild: Guild, channel: Channel) -> None:
        game = GameFactory.create(guild=guild, channel=channel)
        PostFactory.create(guild=guild, channel=channel, game=game)

        games = GamesService()
        assert await games.select_by_message_xid(game.posts[0].message_xid)
        assert not await games.select_by_message_xid(404)

    async def test_games_add_player(self, game: Game) -> None:
        PostFactory.create(guild=game.guild, channel=game.channel, game=game)
        user = UserFactory.create()

        games = GamesService()
        await games.select(game.id)
        await games.add_player(user.xid)

        DatabaseSession.expire_all()
        found = DatabaseSession.get(User, user.xid)
        assert found
        found_game = found.game(game.channel_xid)
        assert found_game is not None
        assert found_game.id == game.id

    async def test_games_to_embed(self, game: Game) -> None:
        public_embed = game.to_embed().to_dict()
        private_embed = game.to_embed(guild=None, dm=True).to_dict()

        games = GamesService()
        await games.select(game.id)
        assert (await games.to_embed(guild=None)).to_dict() == public_embed
        assert (await games.to_embed(guild=None)).to_dict() == private_embed

    async def test_games_add_post(self, game: Game) -> None:
        games = GamesService()
        await games.select(game.id)
        await games.add_post(game.guild_xid, game.channel_xid, 12345)

        post = DatabaseSession.query(Post).one()
        assert post.game_id == game.id

    async def test_games_fully_seated(self, guild: Guild, channel: Channel) -> None:
        started_game = GameFactory.create(guild=guild, channel=channel)
        pending_game = GameFactory.create(guild=guild, channel=channel)
        for _ in range(started_game.seats):
            UserFactory.create(game=started_game)
        UserFactory.create(game=pending_game)

        games = GamesService()
        await games.select(started_game.id)
        assert await games.fully_seated()
        await games.select(pending_game.id)
        assert not await games.fully_seated()

    async def test_games_make_ready(self, game: Game) -> None:
        games = GamesService()
        await games.select(game.id)
        await games.make_ready("http://link", "whatever")

        DatabaseSession.expire_all()
        found = DatabaseSession.get(Game, game.id)
        assert found
        assert found.game_link == "http://link"
        assert found.password == "whatever"
        assert found.status == GameStatus.STARTED.value

    async def test_games_player_xids(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create(game=game)

        games = GamesService()
        await games.select(game.id)
        assert set(await games.player_xids()) == {user1.xid, user2.xid}

    async def test_games_watch_notes(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create(game=game)
        user3 = UserFactory.create()
        watch = WatchFactory.create(guild_xid=game.guild.xid, user_xid=user1.xid)

        DatabaseSession.expire_all()
        games = GamesService()
        await games.select(game.id)
        assert await games.watch_notes([user1.xid, user2.xid, user3.xid]) == {
            user1.xid: watch.note,
        }

    async def test_games_set_voice(self, game: Game) -> None:
        games = GamesService()
        await games.select(game.id)
        await games.set_voice(voice_xid=12345)

        DatabaseSession.expire_all()
        found = DatabaseSession.get(Game, game.id)
        assert found
        assert found.voice_xid == 12345

    async def test_games_set_voice_with_link(self, game: Game) -> None:
        games = GamesService()
        await games.select(game.id)
        await games.set_voice(voice_xid=12345, voice_invite_link="http://link")

        DatabaseSession.expire_all()
        found = DatabaseSession.get(Game, game.id)
        assert found
        assert found.voice_xid == 12345
        assert found.voice_invite_link == "http://link"

    async def test_games_to_dict(self, game: Game) -> None:
        games = GamesService()
        await games.select(game.id)
        assert await games.to_dict() == game.to_dict()

    async def test_message_xids(self, game: Game) -> None:
        games = GamesService()
        await games.select(game.id)
        PostFactory.create(guild=game.guild, channel=game.channel, game=game)
        assert await games.message_xids([game.id]) == [game.posts[0].message_xid]

    async def test_dequeue_players(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create(game=game)
        games = GamesService()

        await games.select(game.id)
        await games.dequeue_players([user1.xid, user2.xid])

        DatabaseSession.expire_all()
        assert user1.game(game.channel_xid) is None
        assert user2.game(game.channel_xid) is None


@pytest.mark.asyncio
class TestServiceGamesPlays:
    async def test_games_players_included(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()
        PlayFactory.create(user_xid=user1.xid, game_id=game.id)

        games = GamesService()
        await games.select(game.id)
        assert await games.players_included(user1.xid)
        assert not await games.players_included(user2.xid)


@pytest.mark.asyncio
class TestServiceGamesFilterPendingGames:
    async def test_happy_path(self) -> None:
        guild = GuildFactory.create()
        channel = ChannelFactory.create(guild=guild)
        user1 = UserFactory.create()
        game1 = GameFactory.create(status=GameStatus.PENDING.value, guild=guild, channel=channel)
        game2 = GameFactory.create(status=GameStatus.PENDING.value, guild=guild, channel=channel)
        QueueFactory.create(game_id=game1.id, user_xid=user1.xid)
        QueueFactory.create(game_id=game2.id, user_xid=user1.xid)

        user2 = UserFactory.create()
        QueueFactory.create(game_id=game1.id, user_xid=user2.xid)

        with patch("spellbot.services.games.settings.MAX_PENDING_GAMES", 3):
            games = GamesService()
            assert await games.filter_pending_games([user1.xid, user2.xid]) == [user2.xid]


@pytest.mark.asyncio
class TestServiceGamesBlocked:
    async def test_when_blocker_in_game(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()

        BlockFactory.create(user_xid=user1.xid, blocked_user_xid=user2.xid)

        games = GamesService()
        await games.select(game.id)
        assert await games.blocked(user2.xid)

    async def test_when_blocker_outside_game(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()

        BlockFactory.create(user_xid=user2.xid, blocked_user_xid=user1.xid)

        games = GamesService()
        await games.select(game.id)
        assert await games.blocked(user2.xid)

    async def test_when_no_blockers(self, game: Game) -> None:
        UserFactory.create(game=game)
        user3 = UserFactory.create()

        games = GamesService()
        await games.select(game.id)
        assert not await games.blocked(user3.xid)


@pytest.mark.asyncio
class TestServiceGamesFilterBlocked:
    async def test_when_blocker_in_game(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()

        BlockFactory.create(user_xid=user1.xid, blocked_user_xid=user2.xid)

        games = GamesService()
        await games.select(game.id)
        assert await games.filter_blocked_list(user2.xid, [user1.xid]) == []

    async def test_when_blocker_outside_game(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()

        BlockFactory.create(user_xid=user2.xid, blocked_user_xid=user1.xid)

        games = GamesService()
        await games.select(game.id)
        assert await games.filter_blocked_list(user2.xid, [user1.xid]) == []

    async def test_when_no_blockers(self, game: Game) -> None:
        UserFactory.create(game=game)
        user3 = UserFactory.create()

        games = GamesService()
        await games.select(game.id)
        assert await games.filter_blocked_list(user3.xid, [1, 2, 3]) == [1, 2, 3]


@pytest.mark.asyncio
class TestServiceGamesUpsert:
    async def test_lfg_alone_when_existing_game(self, game: Game, user: User) -> None:
        games = GamesService()
        new = await games.upsert(
            guild_xid=game.guild.xid,
            channel_xid=game.channel.xid,
            author_xid=user.xid,
            friends=[],
            seats=4,
            rules=None,
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
            service=GameService.SPELLTABLE.value,
        )
        assert not new

        DatabaseSession.expire_all()
        found_user = DatabaseSession.query(User).one()
        found_queue = (
            DatabaseSession.query(Queue)
            .filter(
                and_(
                    Queue.game_id == game.id,
                    Queue.user_xid == found_user.xid,
                ),
            )
            .one_or_none()
        )
        assert found_queue is not None

    async def test_lfg_with_friend_when_existing_game(self, game: Game) -> None:
        user1 = UserFactory.create(xid=101)
        user2 = UserFactory.create(xid=102)

        games = GamesService()
        new = await games.upsert(
            guild_xid=game.guild.xid,
            channel_xid=game.channel.xid,
            author_xid=user1.xid,
            friends=[user2.xid],
            seats=4,
            rules=None,
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
            service=GameService.SPELLTABLE.value,
        )
        assert not new

        DatabaseSession.expire_all()
        rows = DatabaseSession.query(Queue.user_xid).filter(Queue.game_id == game.id).all()
        assert {row[0] for row in rows} == {101, 102}

    async def test_lfg_alone_when_no_game(self, guild: Guild, channel: Channel, user: User) -> None:
        games = GamesService()
        new = await games.upsert(
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            author_xid=user.xid,
            friends=[],
            seats=4,
            rules=None,
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
            service=GameService.SPELLTABLE.value,
        )
        assert new

        DatabaseSession.expire_all()
        found_user = DatabaseSession.query(User).one()
        found_game = DatabaseSession.query(Game).one()
        found_queue = DatabaseSession.query(Queue).one()
        assert found_game.guild_xid == guild.xid
        assert found_game.channel_xid == channel.xid
        assert found_queue.game_id == found_game.id
        assert found_queue.user_xid == found_user.xid

    async def test_lfg_with_friend_when_no_game(self, guild: Guild, channel: Channel) -> None:
        user1 = UserFactory.create(xid=101)
        user2 = UserFactory.create(xid=102)

        games = GamesService()
        new = await games.upsert(
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            author_xid=user1.xid,
            friends=[user2.xid],
            seats=4,
            rules="some additional rules",
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
            service=GameService.SPELLTABLE.value,
        )
        assert new

        DatabaseSession.expire_all()
        game = DatabaseSession.query(Game).one()
        assert game.guild_xid == guild.xid
        assert game.channel_xid == channel.xid
        rows = DatabaseSession.query(Queue.user_xid).filter(Queue.game_id == game.id).all()
        assert {row[0] for row in rows} == {101, 102}
        assert game.rules == "some additional rules"

    async def test_lfg_with_friend_when_full_game(self, guild: Guild, channel: Channel) -> None:
        user1 = UserFactory.create(xid=101)
        user2 = UserFactory.create(xid=102)
        user3 = UserFactory.create(xid=103)
        bad_game = GameFactory.create(seats=2, channel=channel, guild=guild)

        games = GamesService()
        new = await games.upsert(
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            author_xid=user1.xid,
            friends=[user2.xid, user3.xid],
            seats=4,
            rules=None,
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
            service=GameService.SPELLTABLE.value,
        )
        assert new

        DatabaseSession.expire_all()
        game = DatabaseSession.query(Game).filter(Game.id != bad_game.id).one()
        assert game.guild_xid == guild.xid
        assert game.channel_xid == channel.xid
        rows = DatabaseSession.query(Queue.user_xid).filter(Queue.game_id == game.id).all()
        assert {row[0] for row in rows} == {101, 102, 103}

    async def test_lfg_with_friend_when_game_wrong_format(
        self,
        guild: Guild,
        channel: Channel,
    ) -> None:
        user1 = UserFactory.create(xid=101)
        user2 = UserFactory.create(xid=102)
        user3 = UserFactory.create(xid=103)
        bad_game = GameFactory.create(
            seats=4,
            channel=channel,
            guild=guild,
            format=GameFormat.TWO_HEADED_GIANT.value,
        )

        games = GamesService()
        new = await games.upsert(
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            author_xid=user1.xid,
            friends=[user2.xid, user3.xid],
            seats=4,
            rules=None,
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
            service=GameService.SPELLTABLE.value,
        )
        assert new

        DatabaseSession.expire_all()
        game = DatabaseSession.query(Game).filter(Game.id != bad_game.id).one()
        assert game.guild_xid == guild.xid
        assert game.channel_xid == channel.xid
        rows = DatabaseSession.query(Queue.user_xid).filter(Queue.game_id == game.id).all()
        assert {row[0] for row in rows} == {101, 102, 103}

    async def test_lfg_when_existing_game_and_blocked(self, game: Game) -> None:
        games = GamesService()
        user1 = UserFactory.create(xid=101, game=game)
        user2 = UserFactory.create(xid=102)
        BlockFactory.create(user_xid=user1.xid, blocked_user_xid=user2.xid)

        new = await games.upsert(
            guild_xid=game.guild.xid,
            channel_xid=game.channel.xid,
            author_xid=user2.xid,
            friends=[],
            seats=game.seats,
            rules=None,
            format=game.format,
            bracket=game.bracket,
            service=GameService.SPELLTABLE.value,
        )

        DatabaseSession.expire_all()
        other_game = DatabaseSession.query(Game).filter(Game.id != game.id).one()
        assert new
        assert game.players == [user1]
        assert other_game.players == [user2]

    async def test_lfg_when_existing_game_and_blocker(self, game: Game) -> None:
        games = GamesService()
        user1 = UserFactory.create(xid=101, game=game)
        user2 = UserFactory.create(xid=102)
        BlockFactory.create(user_xid=user2.xid, blocked_user_xid=user1.xid)

        new = await games.upsert(
            guild_xid=game.guild.xid,
            channel_xid=game.channel.xid,
            author_xid=user2.xid,
            friends=[],
            seats=game.seats,
            rules=None,
            format=game.format,
            bracket=game.bracket,
            service=GameService.SPELLTABLE.value,
        )

        DatabaseSession.expire_all()
        other_game = DatabaseSession.query(Game).filter(Game.id != game.id).one()
        assert new
        assert game.players == [user1]
        assert other_game.players == [user2]
