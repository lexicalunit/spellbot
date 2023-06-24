from __future__ import annotations

import pytest
from spellbot.database import DatabaseSession
from spellbot.models import (
    Block,
    Channel,
    Game,
    GameFormat,
    GameStatus,
    Guild,
    Play,
    User,
    UserAward,
    Verify,
)
from spellbot.services import GamesService
from sqlalchemy.sql.expression import and_

from tests.factories import (
    BlockFactory,
    ChannelFactory,
    GameFactory,
    GuildAwardFactory,
    GuildFactory,
    PlayFactory,
    UserAwardFactory,
    UserFactory,
    VerifyFactory,
    WatchFactory,
)


@pytest.mark.asyncio()
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

        games = GamesService()
        assert await games.select_by_message_xid(game.message_xid)
        assert not await games.select_by_message_xid(404)

    async def test_games_add_player(self, game: Game) -> None:
        user = UserFactory.create()

        games = GamesService()
        await games.select(game.id)
        await games.add_player(user.xid)

        DatabaseSession.expire_all()
        found = DatabaseSession.query(User).get(user.xid)
        assert found
        assert found.game.id == game.id

    async def test_games_to_embed(self, game: Game) -> None:
        public_embed = game.to_embed().to_dict()
        private_embed = game.to_embed(True).to_dict()

        games = GamesService()
        await games.select(game.id)
        assert (await games.to_embed()).to_dict() == public_embed
        assert (await games.to_embed()).to_dict() == private_embed

    async def test_games_set_message_xid(self, game: Game) -> None:
        games = GamesService()
        await games.select(game.id)
        await games.set_message_xid(12345)

        DatabaseSession.expire_all()
        found = DatabaseSession.query(Game).filter_by(message_xid=12345).one_or_none()
        assert found
        assert found.id == game.id

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
        await games.make_ready("http://link")

        DatabaseSession.expire_all()
        found = DatabaseSession.query(Game).get(game.id)
        assert found
        assert found.spelltable_link == "http://link"
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
        await games.set_voice(12345)

        DatabaseSession.expire_all()
        found = DatabaseSession.query(Game).get(game.id)
        assert found
        assert found.voice_xid == 12345

    async def test_games_to_dict(self, game: Game) -> None:
        games = GamesService()
        await games.select(game.id)
        assert await games.to_dict() == game.to_dict()


@pytest.mark.asyncio()
class TestServiceGamesPlays:
    async def test_games_players_included(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()
        PlayFactory.create(user_xid=user1.xid, game_id=game.id)

        games = GamesService()
        await games.select(game.id)
        assert await games.players_included(user1.xid)
        assert not await games.players_included(user2.xid)

    async def test_games_add_points(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create(game=game)
        PlayFactory.create(user_xid=user1.xid, game_id=game.id, points=5)
        PlayFactory.create(user_xid=user2.xid, game_id=game.id, points=None)

        games = GamesService()
        await games.select(game.id)
        await games.add_points(user1.xid, 5)

        DatabaseSession.expire_all()
        found = DatabaseSession.query(Play).filter(Play.user_xid == user1.xid).one()
        assert found.points == 5
        found = DatabaseSession.query(Play).filter(Play.user_xid == user2.xid).one()
        assert found.points is None

    async def test_games_record_plays(self, guild: Guild, channel: Channel) -> None:
        game = GameFactory.create(
            guild=guild,
            channel=channel,
            seats=2,
            status=GameStatus.STARTED.value,
        )
        user1 = UserFactory.create(xid=101, game=game)
        user2 = UserFactory.create(xid=102, game=game)

        games = GamesService()
        await games.select(game.id)
        await games.record_plays()

        DatabaseSession.expire_all()
        found = DatabaseSession.query(Play).filter(Play.user_xid == user1.xid).one()
        assert found.user_xid == user1.xid
        assert found.game_id == game.id
        found = DatabaseSession.query(Play).filter(Play.user_xid == user2.xid).one()
        assert found.user_xid == user2.xid
        assert found.game_id == game.id
        found = DatabaseSession.query(Play).filter(Play.user_xid == 103).one_or_none()
        assert not found


@pytest.mark.asyncio()
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


@pytest.mark.asyncio()
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


@pytest.mark.asyncio()
class TestServiceGamesUpsert:
    async def test_lfg_alone_when_existing_game(self, game: Game, user: User) -> None:
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
            format=GameFormat.COMMANDER.value,
        )
        assert not new

        DatabaseSession.expire_all()
        rows = DatabaseSession.query(User.xid).filter(User.game_id == game.id).all()
        assert {row[0] for row in rows} == {101, 102}

    async def test_lfg_alone_when_no_game(self, guild: Guild, channel: Channel, user: User) -> None:
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
            format=GameFormat.COMMANDER.value,
        )
        assert new

        DatabaseSession.expire_all()
        game = DatabaseSession.query(Game).one()
        assert game.guild_xid == guild.xid
        assert game.channel_xid == channel.xid
        rows = DatabaseSession.query(User.xid).filter(User.game_id == game.id).all()
        assert {row[0] for row in rows} == {101, 102}

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
            format=GameFormat.COMMANDER.value,
        )
        assert new

        DatabaseSession.expire_all()
        game = DatabaseSession.query(Game).filter(Game.id != bad_game.id).one()
        assert game.guild_xid == guild.xid
        assert game.channel_xid == channel.xid
        rows = DatabaseSession.query(User.xid).filter(User.game_id == game.id).all()
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
            format=GameFormat.COMMANDER.value,
        )
        assert new

        DatabaseSession.expire_all()
        game = DatabaseSession.query(Game).filter(Game.id != bad_game.id).one()
        assert game.guild_xid == guild.xid
        assert game.channel_xid == channel.xid
        rows = DatabaseSession.query(User.xid).filter(User.game_id == game.id).all()
        assert {row[0] for row in rows} == {101, 102, 103}

    async def test_transfer(self) -> None:
        games = GamesService()

        guild1 = GuildFactory.create()
        channel11 = ChannelFactory.create(guild_xid=guild1.xid)
        channel12 = ChannelFactory.create(guild_xid=guild1.xid)

        guild2 = GuildFactory.create()
        channel21 = ChannelFactory.create(guild_xid=guild2.xid)
        channel22 = ChannelFactory.create(guild_xid=guild2.xid)

        user1 = UserFactory.create(xid=101)
        user2 = UserFactory.create(xid=102)
        user3 = UserFactory.create(xid=103)

        game11 = GameFactory.create(guild=guild1, channel=channel11)
        game12 = GameFactory.create(guild=guild1, channel=channel12)
        game21 = GameFactory.create(guild=guild2, channel=channel21)
        game22 = GameFactory.create(guild=guild2, channel=channel22)

        user1_play11 = PlayFactory.create(user_xid=user1.xid, game_id=game11.id)
        user1_play12 = PlayFactory.create(user_xid=user1.xid, game_id=game12.id)
        user1_play21 = PlayFactory.create(user_xid=user1.xid, game_id=game21.id)
        user1_play22 = PlayFactory.create(user_xid=user1.xid, game_id=game22.id)

        guild_award = GuildAwardFactory.create(guild_xid=guild1.xid)
        UserAwardFactory.create(
            guild_xid=guild1.xid,
            user_xid=user1.xid,
            guild_award_id=guild_award.id,
        )
        user2_guild1_award = UserAwardFactory.create(
            guild_xid=guild1.xid,
            user_xid=user2.xid,
            guild_award_id=guild_award.id,
        )

        VerifyFactory.create(
            guild_xid=guild1.xid,
            user_xid=user1.xid,
            verified=True,
        )
        verify12 = VerifyFactory.create(
            guild_xid=guild1.xid,
            user_xid=user2.xid,
            verified=True,
        )

        user1_blocks_user3 = BlockFactory.create(user_xid=user1.xid, blocked_user_xid=user3.xid)
        user3_blocks_user1 = BlockFactory.create(user_xid=user3.xid, blocked_user_xid=user1.xid)

        await games.transfer(guild1.xid, user1.xid, user2.xid)

        DatabaseSession.expire_all()

        assert DatabaseSession.query(UserAward).filter(UserAward.user_xid == user1.xid).count() == 0
        assert DatabaseSession.query(UserAward).filter(UserAward.user_xid == user2.xid).count() == 1
        assert user2_guild1_award.user_xid == user2.xid

        assert DatabaseSession.query(Verify).filter(Verify.user_xid == user1.xid).count() == 0
        assert DatabaseSession.query(Verify).filter(Verify.user_xid == user2.xid).count() == 1
        assert verify12.user_xid == user2.xid

        assert DatabaseSession.query(Play).filter(Play.user_xid == user1.xid).count() == 2
        assert DatabaseSession.query(Play).filter(Play.user_xid == user2.xid).count() == 2
        assert user1_play11.user_xid == user2.xid
        assert user1_play12.user_xid == user2.xid
        assert user1_play21.user_xid == user1.xid
        assert user1_play22.user_xid == user1.xid

        assert user1_blocks_user3.user_xid == user1.xid
        assert user1_blocks_user3.blocked_user_xid == user3.xid
        assert user3_blocks_user1.user_xid == user3.xid
        assert user3_blocks_user1.blocked_user_xid == user1.xid
        assert (
            DatabaseSession.query(Block)
            .filter(
                and_(
                    Block.user_xid == user2.xid,
                    Block.blocked_user_xid == user3.xid,
                ),
            )
            .count()
            == 1
        )
        assert (
            DatabaseSession.query(Block)
            .filter(
                and_(
                    Block.user_xid == user3.xid,
                    Block.blocked_user_xid == user2.xid,
                ),
            )
            .count()
            == 1
        )
