from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.sql.expression import and_

from spellbot.database import DatabaseSession
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.models import Channel, Game, GameStatus, Guild, Play, Post, Queue, User
from spellbot.services import GamesService
from tests.factories import (
    BlockFactory,
    ChannelFactory,
    GameFactory,
    GuildFactory,
    PostFactory,
    UserFactory,
    WatchFactory,
)

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestServiceGames:
    async def test_games_get(self, game: Game) -> None:
        games = GamesService()
        game_data = await games.get(game.id)
        assert game_data is not None
        assert game_data.id == game.id
        assert await games.get(404) is None

    async def test_games_get_by_voice_xid(self, guild: Guild, channel: Channel) -> None:
        game = GameFactory.create(guild=guild, channel=channel, voice_xid=12345)

        games = GamesService()
        game_data = await games.get_by_voice_xid(game.voice_xid)
        assert game_data is not None
        assert game_data.id == game.id
        assert await games.get_by_voice_xid(404) is None

    async def test_games_get_by_message_xid(self, guild: Guild, channel: Channel) -> None:
        game = GameFactory.create(guild=guild, channel=channel)
        PostFactory.create(guild=guild, channel=channel, game=game)

        games = GamesService()
        game_data = await games.get_by_message_xid(game.posts[0].message_xid)
        assert game_data is not None
        assert game_data.id == game.id
        assert await games.get_by_message_xid(404) is None

    async def test_games_add_player(self, game: Game) -> None:
        PostFactory.create(guild=game.guild, channel=game.channel, game=game)
        user = UserFactory.create()

        games = GamesService()
        game_data = await games.get(game.id)
        assert game_data is not None
        updated_game_data = await games.add_player(game_data, user.xid)

        # Verify the returned GameData has the updated player
        assert any(p.xid == user.xid for p in updated_game_data.players)

        # Verify in database
        DatabaseSession.expire_all()
        found = DatabaseSession.get(User, user.xid)
        assert found
        found_game = found.game(game.channel_xid)
        assert found_game is not None
        assert found_game.id == game.id

    async def test_games_to_embed(self, game: Game) -> None:
        # The to_embed method is now on GameData, not GamesService
        game_data = game.to_data()
        public_embed = game_data.to_embed(guild=None).to_dict()
        private_embed = game_data.to_embed(guild=None, dm=True).to_dict()

        # Verify both embeds are created correctly
        assert public_embed is not None
        assert private_embed is not None

    async def test_games_add_post(self, game: Game) -> None:
        games = GamesService()
        game_data = await games.get(game.id)
        assert game_data is not None
        updated_data = await games.add_post(game_data, game.guild_xid, game.channel_xid, 12345)

        # Verify the post was added to game_data
        assert any(p.message_xid == 12345 for p in updated_data.posts)

        # Verify in database
        posts = DatabaseSession.query(Post).filter().all()
        for post in posts:
            assert post.game_id == game.id

    async def test_games_fully_seated(self, guild: Guild, channel: Channel) -> None:
        # fully_seated is now a property on GameData
        started_game = GameFactory.create(guild=guild, channel=channel)
        pending_game = GameFactory.create(guild=guild, channel=channel)
        for _ in range(started_game.seats):
            UserFactory.create(game=started_game)
        UserFactory.create(game=pending_game)

        games = GamesService()
        started_game_data = await games.get(started_game.id)
        pending_game_data = await games.get(pending_game.id)

        assert started_game_data is not None
        assert started_game_data.fully_seated
        assert pending_game_data is not None
        assert not pending_game_data.fully_seated

    async def test_games_make_ready(self, game: Game) -> None:
        games = GamesService()
        game_data = await games.get(game.id)
        assert game_data is not None
        await games.make_ready(game_data, "http://link", "whatever", pins=[])

        DatabaseSession.expire_all()
        found = DatabaseSession.get(Game, game.id)
        assert found
        assert found.game_link == "http://link"
        assert found.password == "whatever"
        assert found.status == GameStatus.STARTED.value

    async def test_games_shrink_game(self, game: Game) -> None:
        UserFactory.create(game=game)
        UserFactory.create(game=game)
        assert game.seats == 4

        games = GamesService()
        game_data = await games.get(game.id)
        assert game_data is not None
        await games.shrink_game(game_data)

        DatabaseSession.expire_all()
        updated = DatabaseSession.query(Game).one()
        assert updated.seats == 2

    async def test_game_data_players(self, game: Game) -> None:
        # player_xids is now accessed via GameData.players
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create(game=game)

        games = GamesService()
        game_data = await games.get(game.id)
        assert game_data is not None
        player_xids = {p.xid for p in game_data.players}
        assert player_xids == {user1.xid, user2.xid}

    async def test_games_watch_notes(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create(game=game)
        user3 = UserFactory.create()
        watch = WatchFactory.create(guild_xid=game.guild.xid, user_xid=user1.xid)

        DatabaseSession.expire_all()
        games = GamesService()
        game_data = await games.get(game.id)
        assert game_data is not None
        assert await games.watch_notes(game_data, [user1.xid, user2.xid, user3.xid]) == {
            user1.xid: watch.note,
        }

    async def test_games_set_voice(self, game: Game) -> None:
        games = GamesService()
        game_data = await games.get(game.id)
        assert game_data is not None
        await games.set_voice(game_data, voice_xid=12345)

        DatabaseSession.expire_all()
        found = DatabaseSession.get(Game, game.id)
        assert found
        assert found.voice_xid == 12345

    async def test_games_set_voice_with_link(self, game: Game) -> None:
        games = GamesService()
        game_data = await games.get(game.id)
        assert game_data is not None
        await games.set_voice(game_data, voice_xid=12345, voice_invite_link="http://link")

        DatabaseSession.expire_all()
        found = DatabaseSession.get(Game, game.id)
        assert found
        assert found.voice_xid == 12345
        assert found.voice_invite_link == "http://link"

    async def test_message_xids(self, game: Game) -> None:
        games = GamesService()
        assert await games.message_xids([game.id]) == [game.posts[0].message_xid]

    async def test_dequeue_players(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create(game=game)
        games = GamesService()

        await games.dequeue_players([user1.xid, user2.xid])

        DatabaseSession.expire_all()
        assert user1.game(game.channel_xid) is None
        assert user2.game(game.channel_xid) is None

    async def test_player_convoke_data(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create(game=game)
        games = GamesService()
        result = await games.player_convoke_data(game.id)
        expected = [
            {"xid": user1.xid, "name": user1.name},
            {"xid": user2.xid, "name": user2.name},
        ]
        assert result == expected

    async def test_player_convoke_data_with_pins(self) -> None:
        # Create a guild with mythic track enabled
        guild = GuildFactory.create(enable_mythic_track=True)
        channel = ChannelFactory.create(guild=guild)

        # Create a started game with plays (which have pins)
        game = GameFactory.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            started_at=datetime.now(UTC),
        )
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create(game=game)

        # UserFactory.create(game=game) automatically creates Play records for started games
        # Query for the Play records that were automatically created
        _play1 = (
            DatabaseSession.query(Play)
            .filter(
                Play.user_xid == user1.xid,
                Play.game_id == game.id,
            )
            .first()
        )
        _play2 = (
            DatabaseSession.query(Play)
            .filter(
                Play.user_xid == user2.xid,
                Play.game_id == game.id,
            )
            .first()
        )

        games = GamesService()
        result = await games.player_convoke_data(game.id)
        expected = [
            {"xid": user1.xid, "name": user1.name},
            {"xid": user2.xid, "name": user2.name},
        ]
        assert result == expected

    async def test_player_convoke_data_when_game_not_found(self) -> None:
        games = GamesService()
        assert await games.player_convoke_data(404) == []


@pytest.mark.asyncio
class TestServiceGamesBlocked:
    async def test_when_blocker_in_game(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()

        BlockFactory.create(user_xid=user1.xid, blocked_user_xid=user2.xid)

        games = GamesService()
        game_data = await games.get(game.id)
        assert game_data is not None
        assert await games.blocked(game_data, user2.xid)

    async def test_when_blocker_outside_game(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()

        BlockFactory.create(user_xid=user2.xid, blocked_user_xid=user1.xid)

        games = GamesService()
        game_data = await games.get(game.id)
        assert game_data is not None
        assert await games.blocked(game_data, user2.xid)

    async def test_when_no_blockers(self, game: Game) -> None:
        UserFactory.create(game=game)
        user3 = UserFactory.create()

        games = GamesService()
        game_data = await games.get(game.id)
        assert game_data is not None
        assert not await games.blocked(game_data, user3.xid)


@pytest.mark.asyncio
class TestServiceGamesUpsert:
    async def test_lfg_alone_when_existing_game(self, game: Game, user: User) -> None:
        games = GamesService()
        new, game_data = await games.upsert(
            guild_xid=game.guild.xid,
            channel_xid=game.channel.xid,
            author_xid=user.xid,
            friends=[],
            seats=4,
            rules=None,
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
            service=GameService.CONVOKE.value,
        )
        assert not new
        assert game_data.id == game.id

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
        new, game_data = await games.upsert(
            guild_xid=game.guild.xid,
            channel_xid=game.channel.xid,
            author_xid=user1.xid,
            friends=[user2.xid],
            seats=4,
            rules=None,
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
            service=GameService.CONVOKE.value,
        )
        assert not new
        assert game_data.id == game.id

        DatabaseSession.expire_all()
        rows = DatabaseSession.query(Queue.user_xid).filter(Queue.game_id == game.id).all()
        assert {row[0] for row in rows} == {101, 102}

    async def test_lfg_alone_when_no_game(self, guild: Guild, channel: Channel, user: User) -> None:
        games = GamesService()
        new, game_data = await games.upsert(
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            author_xid=user.xid,
            friends=[],
            seats=4,
            rules=None,
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
            service=GameService.CONVOKE.value,
        )
        assert new
        assert game_data is not None

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
        new, game_data = await games.upsert(
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            author_xid=user1.xid,
            friends=[user2.xid],
            seats=4,
            rules="some additional rules",
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
            service=GameService.CONVOKE.value,
        )
        assert new
        assert game_data is not None

        DatabaseSession.expire_all()
        db_game = DatabaseSession.query(Game).one()
        assert db_game.guild_xid == guild.xid
        assert db_game.channel_xid == channel.xid
        rows = DatabaseSession.query(Queue.user_xid).filter(Queue.game_id == db_game.id).all()
        assert {row[0] for row in rows} == {101, 102}
        assert db_game.rules == "some additional rules"

    async def test_lfg_with_friend_when_full_game(self, guild: Guild, channel: Channel) -> None:
        user1 = UserFactory.create(xid=101)
        user2 = UserFactory.create(xid=102)
        user3 = UserFactory.create(xid=103)
        bad_game = GameFactory.create(seats=2, channel=channel, guild=guild)

        games = GamesService()
        new, game_data = await games.upsert(
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            author_xid=user1.xid,
            friends=[user2.xid, user3.xid],
            seats=4,
            rules=None,
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
            service=GameService.CONVOKE.value,
        )
        assert new
        assert game_data is not None

        DatabaseSession.expire_all()
        db_game = DatabaseSession.query(Game).filter(Game.id != bad_game.id).one()
        assert db_game.guild_xid == guild.xid
        assert db_game.channel_xid == channel.xid
        rows = DatabaseSession.query(Queue.user_xid).filter(Queue.game_id == db_game.id).all()
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
        new, game_data = await games.upsert(
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            author_xid=user1.xid,
            friends=[user2.xid, user3.xid],
            seats=4,
            rules=None,
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
            service=GameService.CONVOKE.value,
        )
        assert new
        assert game_data is not None

        DatabaseSession.expire_all()
        db_game = DatabaseSession.query(Game).filter(Game.id != bad_game.id).one()
        assert db_game.guild_xid == guild.xid
        assert db_game.channel_xid == channel.xid
        rows = DatabaseSession.query(Queue.user_xid).filter(Queue.game_id == db_game.id).all()
        assert {row[0] for row in rows} == {101, 102, 103}

    async def test_lfg_when_existing_game_and_blocked(self, game: Game) -> None:
        games = GamesService()
        user1 = UserFactory.create(xid=101, game=game)
        user2 = UserFactory.create(xid=102)
        BlockFactory.create(user_xid=user1.xid, blocked_user_xid=user2.xid)

        new, _ = await games.upsert(
            guild_xid=game.guild.xid,
            channel_xid=game.channel.xid,
            author_xid=user2.xid,
            friends=[],
            seats=game.seats,
            rules=None,
            format=game.format,
            bracket=game.bracket,
            service=GameService.CONVOKE.value,
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

        new, _ = await games.upsert(
            guild_xid=game.guild.xid,
            channel_xid=game.channel.xid,
            author_xid=user2.xid,
            friends=[],
            seats=game.seats,
            rules=None,
            format=game.format,
            bracket=game.bracket,
            service=GameService.CONVOKE.value,
        )

        DatabaseSession.expire_all()
        other_game = DatabaseSession.query(Game).filter(Game.id != game.id).one()
        assert new
        assert game.players == [user1]
        assert other_game.players == [user2]
