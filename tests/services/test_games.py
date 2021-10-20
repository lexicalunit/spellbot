import pytest

from spellbot.database import DatabaseSession
from spellbot.models.game import Game, GameFormat, GameStatus
from spellbot.models.play import Play
from spellbot.models.user import User
from spellbot.services.games import GamesService
from tests.factories.block import BlockFactory
from tests.factories.game import GameFactory
from tests.factories.play import PlayFactory
from tests.factories.user import UserFactory
from tests.factories.watch import WatchFactory


@pytest.mark.asyncio
class TestServiceGames:
    async def test_games_select(self, game):
        games = GamesService()
        assert await games.select(game.id)
        assert not await games.select(404)

    async def test_games_select_by_voice_xid(self, guild, channel):
        game = GameFactory.create(guild=guild, channel=channel, voice_xid=12345)
        DatabaseSession.commit()

        games = GamesService()
        assert await games.select_by_voice_xid(game.voice_xid)
        assert not await games.select_by_voice_xid(404)

    async def test_games_select_by_message_xid(self, guild, channel):
        game = GameFactory.create(guild=guild, channel=channel)
        DatabaseSession.commit()

        games = GamesService()
        assert await games.select_by_message_xid(game.message_xid)
        assert not await games.select_by_message_xid(404)

    async def test_games_add_player(self, game):
        user = UserFactory.create()
        DatabaseSession.commit()

        games = GamesService()
        await games.select(game.id)
        await games.add_player(user.xid)

        DatabaseSession.expire_all()
        found = DatabaseSession.query(User).get(user.xid)
        assert found and found.game.id == game.id

    async def test_games_to_embed(self, game):
        public_embed = game.to_embed().to_dict()
        private_embed = game.to_embed(True).to_dict()

        games = GamesService()
        await games.select(game.id)
        assert (await games.to_embed()).to_dict() == public_embed
        assert (await games.to_embed()).to_dict() == private_embed

    async def test_games_set_message_xid(self, game):
        games = GamesService()
        await games.select(game.id)
        await games.set_message_xid(12345)

        DatabaseSession.expire_all()
        found = DatabaseSession.query(Game).filter_by(message_xid=12345).one_or_none()
        assert found and found.id == game.id

    async def test_games_current_guild_xid(self, game):
        games = GamesService()
        await games.select(game.id)
        assert await games.current_guild_xid() == game.guild.xid

    async def test_games_current_channel_xid(self, guild, channel):
        game = GameFactory.create(guild=guild, channel=channel)
        DatabaseSession.commit()

        games = GamesService()
        await games.select(game.id)
        assert await games.current_channel_xid() == channel.xid

    async def test_games_current_message_xid(self, guild, channel):
        game = GameFactory.create(guild=guild, channel=channel, message_xid=5)
        DatabaseSession.commit()

        games = GamesService()
        await games.select(game.id)
        assert await games.current_message_xid() == 5

    async def test_games_current_id(self, game):
        games = GamesService()
        await games.select(game.id)
        assert await games.current_id() == game.id

    async def test_games_fully_seated(self, guild, channel):
        started_game = GameFactory.create(guild=guild, channel=channel)
        pending_game = GameFactory.create(guild=guild, channel=channel)
        for _ in range(started_game.seats):
            UserFactory.create(game=started_game)
        UserFactory.create(game=pending_game)
        DatabaseSession.commit()

        games = GamesService()
        await games.select(started_game.id)
        assert await games.fully_seated()
        await games.select(pending_game.id)
        assert not await games.fully_seated()

    async def test_games_make_ready(self, game):
        games = GamesService()
        await games.select(game.id)
        await games.make_ready("http://link")

        DatabaseSession.expire_all()
        found = DatabaseSession.query(Game).get(game.id)
        assert found and found.spelltable_link == "http://link"
        assert found.status == GameStatus.STARTED.value

    async def test_games_current_player_xids(self, game):
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create(game=game)
        DatabaseSession.commit()

        games = GamesService()
        await games.select(game.id)
        assert set(await games.current_player_xids()) == {user1.xid, user2.xid}

    async def test_games_watch_notes(self, game):
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create(game=game)
        user3 = UserFactory.create()
        watch = WatchFactory.create(guild_xid=game.guild.xid, user_xid=user1.xid)
        DatabaseSession.commit()

        DatabaseSession.expire_all()
        games = GamesService()
        await games.select(game.id)
        assert await games.watch_notes([user1.xid, user2.xid, user3.xid]) == {
            user1.xid: watch.note,
        }

    async def test_games_set_voice(self, game):
        games = GamesService()
        await games.select(game.id)
        await games.set_voice(12345, "http://link")

        DatabaseSession.expire_all()
        found = DatabaseSession.query(Game).get(game.id)
        assert found and found.voice_xid == 12345
        assert found.voice_invite_link == "http://link"

    async def test_games_jump_link(self, game):
        games = GamesService()
        await games.select(game.id)
        assert await games.jump_link() == (
            "https://discordapp.com/channels/"
            f"{game.guild.xid}/{game.channel.xid}/{game.message_xid}"
        )

    async def test_games_players_included(self, game):
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()
        PlayFactory.create(user_xid=user1.xid, game_id=game.id)
        DatabaseSession.commit()

        games = GamesService()
        await games.select(game.id)
        assert await games.players_included(user1.xid)
        assert not await games.players_included(user2.xid)

    async def test_games_add_points(self, game):
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create(game=game)
        PlayFactory.create(user_xid=user1.xid, game_id=game.id, points=5)
        PlayFactory.create(user_xid=user2.xid, game_id=game.id, points=None)
        DatabaseSession.commit()

        games = GamesService()
        await games.select(game.id)
        await games.add_points(user1.xid, 5)

        DatabaseSession.expire_all()
        found = DatabaseSession.query(Play).filter(Play.user_xid == user1.xid).one()
        assert found.points == 5
        found = DatabaseSession.query(Play).filter(Play.user_xid == user2.xid).one()
        assert found.points is None

    async def test_games_record_plays(self, guild, channel):
        game = GameFactory.create(
            guild=guild,
            channel=channel,
            seats=2,
            status=GameStatus.STARTED.value,
        )
        user1 = UserFactory.create(xid=101, game=game)
        user2 = UserFactory.create(xid=102, game=game)
        DatabaseSession.commit()

        games = GamesService()
        await games.select(game.id)
        await games.record_plays()

        DatabaseSession.expire_all()
        found = DatabaseSession.query(Play).filter(Play.user_xid == user1.xid).one()
        assert found.user_xid == user1.xid and found.game_id == game.id
        found = DatabaseSession.query(Play).filter(Play.user_xid == user2.xid).one()
        assert found.user_xid == user2.xid and found.game_id == game.id
        found = DatabaseSession.query(Play).filter(Play.user_xid == 103).one_or_none()
        assert not found


@pytest.mark.asyncio
class TestServiceGamesBlocked:
    async def test_when_blocker_in_game(self, game):
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()
        DatabaseSession.commit()

        BlockFactory.create(user_xid=user1.xid, blocked_user_xid=user2.xid)
        DatabaseSession.commit()

        games = GamesService()
        await games.select(game.id)
        assert await games.blocked(user2.xid)

    async def test_when_blocker_outside_game(self, game):
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()
        DatabaseSession.commit()

        BlockFactory.create(user_xid=user2.xid, blocked_user_xid=user1.xid)
        DatabaseSession.commit()

        games = GamesService()
        await games.select(game.id)
        assert await games.blocked(user2.xid)

    async def test_when_no_blockers(self, game):
        UserFactory.create(game=game)
        user3 = UserFactory.create()
        DatabaseSession.commit()

        games = GamesService()
        await games.select(game.id)
        assert not await games.blocked(user3.xid)


@pytest.mark.asyncio
class TestServiceGamesFilterBlocked:
    async def test_when_blocker_in_game(self, game):
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()
        DatabaseSession.commit()

        BlockFactory.create(user_xid=user1.xid, blocked_user_xid=user2.xid)
        DatabaseSession.commit()

        games = GamesService()
        await games.select(game.id)
        assert await games.filter_blocked(user2.xid, [user1.xid]) == []

    async def test_when_blocker_outside_game(self, game):
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()
        DatabaseSession.commit()

        BlockFactory.create(user_xid=user2.xid, blocked_user_xid=user1.xid)
        DatabaseSession.commit()

        games = GamesService()
        await games.select(game.id)
        assert await games.filter_blocked(user2.xid, [user1.xid]) == []

    async def test_when_no_blockers(self, game):
        UserFactory.create(game=game)
        user3 = UserFactory.create()
        DatabaseSession.commit()

        games = GamesService()
        await games.select(game.id)
        assert await games.filter_blocked(user3.xid, [1, 2, 3]) == [1, 2, 3]


@pytest.mark.asyncio
class TestServiceGamesUpsert:
    async def test_lfg_alone_when_existing_game(self, game, user):
        games = GamesService()
        new = await games.upsert(
            guild_xid=game.guild.xid,
            channel_xid=game.channel.xid,
            author_xid=user.xid,
            friends=[],
            seats=4,
            format=GameFormat.COMMANDER.value,
        )
        assert not new

        DatabaseSession.expire_all()
        found = DatabaseSession.query(User).one()
        assert found.game_id == game.id

    async def test_lfg_with_friend_when_existing_game(self, game):
        user1 = UserFactory.create(xid=101)
        user2 = UserFactory.create(xid=102)
        DatabaseSession.commit()

        games = GamesService()
        new = await games.upsert(
            guild_xid=game.guild.xid,
            channel_xid=game.channel.xid,
            author_xid=user1.xid,
            friends=[user2.xid],
            seats=4,
            format=GameFormat.COMMANDER.value,
        )
        assert not new

        DatabaseSession.expire_all()
        rows = DatabaseSession.query(User.xid).filter(User.game_id == game.id).all()
        assert set(row[0] for row in rows) == {101, 102}

    async def test_lfg_alone_when_no_game(self, guild, channel, user):
        games = GamesService()
        new = await games.upsert(
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            author_xid=user.xid,
            friends=[],
            seats=4,
            format=GameFormat.COMMANDER.value,
        )
        assert new

        DatabaseSession.expire_all()
        found_user = DatabaseSession.query(User).one()
        found_game = DatabaseSession.query(Game).one()
        assert found_game.guild_xid == guild.xid
        assert found_game.channel_xid == channel.xid
        assert found_user.game_id == found_game.id

    async def test_lfg_with_friend_when_no_game(self, guild, channel):
        user1 = UserFactory.create(xid=101)
        user2 = UserFactory.create(xid=102)
        DatabaseSession.commit()

        games = GamesService()
        new = await games.upsert(
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            author_xid=user1.xid,
            friends=[user2.xid],
            seats=4,
            format=GameFormat.COMMANDER.value,
        )
        assert new

        DatabaseSession.expire_all()
        game = DatabaseSession.query(Game).one()
        assert game.guild_xid == guild.xid
        assert game.channel_xid == channel.xid
        rows = DatabaseSession.query(User.xid).filter(User.game_id == game.id).all()
        assert set(row[0] for row in rows) == {101, 102}

    async def test_lfg_with_friend_when_full_game(self, guild, channel):
        user1 = UserFactory.create(xid=101)
        user2 = UserFactory.create(xid=102)
        user3 = UserFactory.create(xid=103)
        bad_game = GameFactory.create(seats=2, channel=channel, guild=guild)
        DatabaseSession.commit()

        games = GamesService()
        new = await games.upsert(
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            author_xid=user1.xid,
            friends=[user2.xid, user3.xid],
            seats=4,
            format=GameFormat.COMMANDER.value,
        )
        assert new

        DatabaseSession.expire_all()
        game = DatabaseSession.query(Game).filter(Game.id != bad_game.id).one()
        assert game.guild_xid == guild.xid
        assert game.channel_xid == channel.xid
        rows = DatabaseSession.query(User.xid).filter(User.game_id == game.id).all()
        assert set(row[0] for row in rows) == {101, 102, 103}

    async def test_lfg_with_friend_when_game_wrong_format(self, guild, channel):
        user1 = UserFactory.create(xid=101)
        user2 = UserFactory.create(xid=102)
        user3 = UserFactory.create(xid=103)
        bad_game = GameFactory.create(
            seats=4,
            channel=channel,
            guild=guild,
            format=GameFormat.TWO_HEADED_GIANT.value,
        )
        DatabaseSession.commit()

        games = GamesService()
        new = await games.upsert(
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            author_xid=user1.xid,
            friends=[user2.xid, user3.xid],
            seats=4,
            format=GameFormat.COMMANDER.value,
        )
        assert new

        DatabaseSession.expire_all()
        game = DatabaseSession.query(Game).filter(Game.id != bad_game.id).one()
        assert game.guild_xid == guild.xid
        assert game.channel_xid == channel.xid
        rows = DatabaseSession.query(User.xid).filter(User.game_id == game.id).all()
        assert set(row[0] for row in rows) == {101, 102, 103}
