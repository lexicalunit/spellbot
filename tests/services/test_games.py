# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import event, select
from sqlalchemy.sql.expression import and_

from spellbot.data import ChannelModes, GameCriteria, GameLinkDetails
from spellbot.database import DatabaseSession, engine
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.models import Channel, Game, GameStatus, Guild, Play, Post, Queue, User
from spellbot.services import games
from spellbot.services.games import game_players, game_to_data
from spellbot.services.users import current_game
from spellbot.settings import settings
from tests.factories import (
    BlockFactory,
    ChannelFactory,
    GameFactory,
    GuildFactory,
    PlayFactory,
    PostFactory,
    UserFactory,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestServiceGames:
    async def test_games_get(self, game: Game) -> None:
        game_data = await games.get(game.id)
        assert game_data is not None
        assert game_data.id == game.id
        assert await games.get(404) is None

    async def test_games_get_many(self, guild: Guild, channel: Channel) -> None:
        first = GameFactory.create(guild=guild, channel=channel)
        second = GameFactory.create(guild=guild, channel=channel)
        found = await games.get_many([second.id, 404, first.id])
        assert [game.id for game in found] == [first.id, second.id]
        assert await games.get_many([]) == []

    async def test_games_get_by_voice_xid(self, guild: Guild, channel: Channel) -> None:
        game = GameFactory.create(guild=guild, channel=channel, voice_xid=12345)

        game_data = await games.get_by_voice_xid(game.voice_xid)
        assert game_data is not None
        assert game_data.id == game.id
        assert await games.get_by_voice_xid(404) is None

    async def test_games_get_by_message_xid(self, guild: Guild, channel: Channel) -> None:
        game = GameFactory.create(guild=guild, channel=channel)
        PostFactory.create(guild=guild, channel=channel, game=game)

        game_data = await games.get_by_message_xid(game.posts[0].message_xid)
        assert game_data is not None
        assert game_data.id == game.id
        assert await games.get_by_message_xid(404) is None

    async def test_games_add_player(self, game: Game) -> None:
        PostFactory.create(guild=game.guild, channel=game.channel, game=game)
        user = UserFactory.create()

        game_data = await games.get(game.id)
        assert game_data is not None
        updated_game_data = await games.add_player(game_data, user.xid)

        # Verify the returned GameData has the updated player
        assert updated_game_data is not None
        assert any(p.xid == user.xid for p in updated_game_data.players)

        # Verify in database
        DatabaseSession.expire_all()
        found = await DatabaseSession.get(User, user.xid)
        assert found
        found_game = await current_game(found.xid, game.channel_xid)
        assert found_game is not None
        assert found_game.id == game.id

    async def test_games_add_player_when_full(self, game: Game) -> None:
        # A game can be fully seated while still PENDING if the start step bailed
        # after a prior join took the last seat. Joining such a game must not crash;
        # add_player should return None instead of asserting.
        PostFactory.create(guild=game.guild, channel=game.channel, game=game)
        for _ in range(game.seats):
            UserFactory.create(game=game)

        game_data = await games.get(game.id)
        assert game_data is not None
        latecomer = UserFactory.create()
        assert await games.add_player(game_data, latecomer.xid) is None

        # The latecomer was not added to the full game.
        DatabaseSession.expire_all()
        found = await DatabaseSession.get(User, latecomer.xid)
        assert found
        assert await current_game(found.xid, game.channel_xid) is None

    async def test_games_to_embed(self, game: Game) -> None:
        # The to_embed method is now on GameData, not GamesService
        game_data = await game_to_data(game)
        public_embed = game_data.to_embed().to_dict()
        private_embed = game_data.to_embed(dm=True).to_dict()

        # Verify both embeds are created correctly
        assert public_embed is not None
        assert private_embed is not None

    async def test_games_add_post(self, game: Game) -> None:
        game_data = await games.get(game.id)
        assert game_data is not None
        updated_data = await games.add_post(game_data, game.guild_xid, game.channel_xid, 12345)

        # Verify the post was added to game_data
        assert any(p.message_xid == 12345 for p in updated_data.posts)

        # Verify in database
        posts = (await DatabaseSession.execute(select(Post))).scalars().all()
        for post in posts:
            assert post.game_id == game.id

    async def test_games_add_post_conflict(self, game: Game) -> None:
        PostFactory.create(guild=game.guild, channel=game.channel, game=game, message_xid=22345)
        game_data = await games.get(game.id)
        assert game_data is not None
        existing_count = len(game_data.posts)

        # Re-adding the same post should be a no-op (on_conflict_do_nothing returns None)
        result = await games.add_post(game_data, game.guild_xid, game.channel_xid, 22345)
        assert len(result.posts) == existing_count

    async def test_games_fully_seated(self, guild: Guild, channel: Channel) -> None:
        # fully_seated is now a property on GameData
        started_game = GameFactory.create(guild=guild, channel=channel)
        pending_game = GameFactory.create(guild=guild, channel=channel)
        for _ in range(started_game.seats):
            UserFactory.create(game=started_game)
        UserFactory.create(game=pending_game)

        started_game_data = await games.get(started_game.id)
        pending_game_data = await games.get(pending_game.id)

        assert started_game_data is not None
        assert started_game_data.fully_seated
        assert pending_game_data is not None
        assert not pending_game_data.fully_seated

    async def test_games_attach_game_link_does_not_start(self, game: Game) -> None:
        game_data = await games.get(game.id)
        assert game_data is not None
        attached = await games.attach_game_link(
            game_data,
            GameLinkDetails("http://link", "secret", "Cool Guild", "https://convoke.games/g/cool"),
        )

        assert attached.game_link == "http://link"
        assert attached.password == "secret"
        assert attached.convoke_guild_name == "Cool Guild"
        assert attached.convoke_guild_url == "https://convoke.games/g/cool"
        assert attached.status == GameStatus.PENDING.value

        DatabaseSession.expire_all()
        found = await DatabaseSession.get(Game, game.id)
        assert found
        assert found.game_link == "http://link"
        assert found.password == "secret"
        assert found.convoke_guild_name == "Cool Guild"
        assert found.convoke_guild_url == "https://convoke.games/g/cool"
        assert found.status == GameStatus.PENDING.value

    async def test_games_make_ready(self, game: Game) -> None:
        game_data = await games.get(game.id)
        assert game_data is not None
        await games.make_ready(
            game_data,
            GameLinkDetails(
                "http://link",
                "whatever",
                "Cool Guild",
                "https://convoke.games/g/cool",
            ),
            pins={},
        )

        DatabaseSession.expire_all()
        found = await DatabaseSession.get(Game, game.id)
        assert found
        assert found.game_link == "http://link"
        assert found.password == "whatever"
        assert found.convoke_guild_name == "Cool Guild"
        assert found.convoke_guild_url == "https://convoke.games/g/cool"
        assert found.status == GameStatus.STARTED.value

    async def test_games_make_ready_assigns_pins_by_player(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create(game=game)
        game_data = await games.get(game.id)
        assert game_data is not None
        pins = {user2.xid: "222222", user1.xid: "111111"}

        await games.make_ready(game_data, GameLinkDetails("http://link"), pins)

        DatabaseSession.expire_all()
        plays = (
            (await DatabaseSession.execute(select(Play).where(Play.game_id == game.id)))
            .scalars()
            .all()
        )
        assert {play.user_xid: play.pin for play in plays} == pins

    async def test_games_shrink_game(self, game: Game) -> None:
        UserFactory.create(game=game)
        UserFactory.create(game=game)
        assert game.seats == 4

        game_data = await games.get(game.id)
        assert game_data is not None
        await games.shrink_game(game_data)

        DatabaseSession.expire_all()
        updated = (await DatabaseSession.execute(select(Game))).scalar_one()
        assert updated.seats == 2

    async def test_game_data_players(self, game: Game) -> None:
        # player_xids is now accessed via GameData.players
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create(game=game)

        game_data = await games.get(game.id)
        assert game_data is not None
        player_xids = {p.xid for p in game_data.players}
        assert player_xids == {user1.xid, user2.xid}

    async def test_games_set_voice(self, game: Game) -> None:
        game_data = await games.get(game.id)
        assert game_data is not None
        await games.set_voice(game_data, voice_xid=12345)

        DatabaseSession.expire_all()
        found = await DatabaseSession.get(Game, game.id)
        assert found
        assert found.voice_xid == 12345

    async def test_games_set_voice_with_link(self, game: Game) -> None:
        game_data = await games.get(game.id)
        assert game_data is not None
        await games.set_voice(game_data, voice_xid=12345, voice_invite_link="http://link")

        DatabaseSession.expire_all()
        found = await DatabaseSession.get(Game, game.id)
        assert found
        assert found.voice_xid == 12345
        assert found.voice_invite_link == "http://link"

    async def test_message_xids(self, game: Game) -> None:
        assert await games.message_xids([game.id]) == [game.posts[0].message_xid]

    async def test_dequeue_players(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create(game=game)

        await games.dequeue_players([user1.xid, user2.xid])

        DatabaseSession.expire_all()
        assert await current_game(user1.xid, game.channel_xid) is None
        assert await current_game(user2.xid, game.channel_xid) is None

    async def test_player_convoke_data(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create(game=game)
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
            (
                await DatabaseSession.execute(
                    select(Play).where(
                        Play.user_xid == user1.xid,
                        Play.game_id == game.id,
                    ),
                )
            )
            .scalars()
            .first()
        )
        _play2 = (
            (
                await DatabaseSession.execute(
                    select(Play).where(
                        Play.user_xid == user2.xid,
                        Play.game_id == game.id,
                    ),
                )
            )
            .scalars()
            .first()
        )

        result = await games.player_convoke_data(game.id)
        expected = [
            {"xid": user1.xid, "name": user1.name},
            {"xid": user2.xid, "name": user2.name},
        ]
        assert result == expected

    async def test_player_convoke_data_when_game_not_found(self) -> None:
        assert await games.player_convoke_data(404) == []


class TestReportTimestamp:
    def test_none_metadata(self) -> None:
        assert games.report_timestamp(None) is None

    def test_empty_metadata(self) -> None:
        assert games.report_timestamp({}) is None

    def test_missing_reported_at(self) -> None:
        assert games.report_timestamp({"source": "convoke"}) is None

    def test_non_string_value(self) -> None:
        assert games.report_timestamp({"reported_at": 123}) is None

    def test_unparseable_value(self) -> None:
        assert games.report_timestamp({"reported_at": "not-a-timestamp"}) is None

    def test_aware_value(self) -> None:
        result = games.report_timestamp({"reported_at": "2026-07-11T18:00:00+00:00"})
        assert result == datetime(2026, 7, 11, 18, 0, tzinfo=UTC)

    def test_naive_value_normalized_to_utc(self) -> None:
        result = games.report_timestamp({"reported_at": "2026-07-11T18:00:00"})
        assert result is not None
        assert result == datetime(2026, 7, 11, 18, 0, tzinfo=UTC)
        assert result.tzinfo is not None


class TestReportedPlayerXids:
    def test_parses_string_and_numeric_ids(self) -> None:
        players = [{"xid": "1471341302359785685"}, {"xid": 42}, {"xid": "42"}]
        assert games.reported_player_xids({"players": players}) == {1471341302359785685, 42}

    @pytest.mark.parametrize(
        "xid",
        [None, "", "abc", "-5", "0", "012", "²", True, 0, -5, 2**63, "9" * 20, 1.5],
    )
    def test_ignores_invalid_ids(self, xid: object) -> None:
        assert games.reported_player_xids({"players": [{"xid": xid}]}) == set()

    def test_ignores_malformed_players(self) -> None:
        assert games.reported_player_xids({"players": "nope"}) == set()
        assert games.reported_player_xids({"players": ["nope", 7]}) == set()
        assert games.reported_player_xids({}) == set()


@pytest.mark.asyncio
class TestServiceGamesStartFromReport:
    REPORT_STARTED_AT = datetime(2026, 9, 19, 19, 22, 22, tzinfo=UTC)

    def report(self, *xids: object) -> dict[str, object]:
        return {
            "started_at": "2026-09-19T19:22:22Z",
            "players": [{"xid": xid, "name": f"p{i}"} for i, xid in enumerate(xids)],
        }

    def make_game(self, **kwargs: object) -> Game:
        guild = GuildFactory.create()
        return GameFactory.create(guild=guild, channel=ChannelFactory.create(guild=guild), **kwargs)

    async def plays(self, game: Game) -> list[int]:
        rows = await DatabaseSession.scalars(select(Play.user_xid).where(Play.game_id == game.id))
        return sorted(rows)

    async def test_starts_expired_war_game(self) -> None:
        guild = GuildFactory.create()
        channel = ChannelFactory.create(guild=guild)
        known = UserFactory.create()
        queued = UserFactory.create()
        game = GameFactory.create(
            guild=guild,
            channel=channel,
            war_id="war-a",
            deleted_at=datetime.now(tz=UTC),
        )
        DatabaseSession.add(Queue(user_xid=queued.xid, game_id=game.id, og_guild_xid=guild.xid))
        await DatabaseSession.commit()

        # A duplicated ID is credited once; unknown and missing IDs are ignored.
        report = self.report(str(known.xid), str(known.xid), "123456789", None)
        await games.start_from_report(game.id, report)

        DatabaseSession.expire_all()
        started = await DatabaseSession.get(Game, game.id)
        assert started is not None
        assert started.status == GameStatus.STARTED.value
        assert started.started_at == self.REPORT_STARTED_AT.replace(tzinfo=None)
        assert started.deleted_at is None
        assert await self.plays(game) == [known.xid]
        play = await DatabaseSession.scalar(select(Play).where(Play.game_id == game.id))
        assert play is not None
        assert play.og_guild_xid == guild.xid
        assert await DatabaseSession.scalar(select(Queue).where(Queue.game_id == game.id)) is None

    async def test_falls_back_to_now_without_a_start_time(self) -> None:
        game = self.make_game()
        before = datetime.now(tz=UTC).replace(tzinfo=None)
        await games.start_from_report(game.id, {"players": []})
        DatabaseSession.expire_all()
        started = await DatabaseSession.get(Game, game.id)
        assert started is not None
        assert started.started_at is not None
        assert started.started_at >= before
        assert await self.plays(game) == []

    async def test_no_known_players(self) -> None:
        game = self.make_game()
        await games.start_from_report(game.id, self.report("123456789"))
        DatabaseSession.expire_all()
        started = await DatabaseSession.get(Game, game.id)
        assert started is not None
        assert started.status == GameStatus.STARTED.value
        assert await self.plays(game) == []

    async def test_leaves_started_game_alone(self) -> None:
        user = UserFactory.create()
        started_at = datetime(2026, 1, 1, tzinfo=UTC)
        game = self.make_game(status=GameStatus.STARTED.value, started_at=started_at)
        await games.start_from_report(game.id, self.report(str(user.xid)))
        DatabaseSession.expire_all()
        unchanged = await DatabaseSession.get(Game, game.id)
        assert unchanged is not None
        assert unchanged.started_at == started_at.replace(tzinfo=None)
        assert await self.plays(game) == []

    async def test_missing_game(self) -> None:
        await games.start_from_report(404, self.report("123456789"))


@pytest.mark.asyncio
class TestServiceGamesBlocked:
    async def test_when_blocker_in_game(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()

        BlockFactory.create(user_xid=user1.xid, blocked_user_xid=user2.xid)

        game_data = await games.get(game.id)
        assert game_data is not None
        assert await games.blocked(game_data, user2.xid)

    async def test_when_blocker_outside_game(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()

        BlockFactory.create(user_xid=user2.xid, blocked_user_xid=user1.xid)

        game_data = await games.get(game.id)
        assert game_data is not None
        assert await games.blocked(game_data, user2.xid)

    async def test_when_no_blockers(self, game: Game) -> None:
        UserFactory.create(game=game)
        user3 = UserFactory.create()

        game_data = await games.get(game.id)
        assert game_data is not None
        assert not await games.blocked(game_data, user3.xid)


@pytest.mark.asyncio
class TestServiceGamesUpsert:
    async def test_lfg_alone_when_existing_game(self, game: Game, user: User) -> None:
        new, game_data = await games.upsert(
            guild_xid=game.guild.xid,
            channel_xid=game.channel.xid,
            author_xid=user.xid,
            friends=[],
            criteria=GameCriteria(
                seats=4,
                rules=None,
                format=GameFormat.COMMANDER.value,
                bracket=GameBracket.NONE.value,
                service=GameService.CONVOKE.value,
            ),
            modes=ChannelModes(),
            locale="en",
        )
        assert not new
        assert game_data.id == game.id

        DatabaseSession.expire_all()
        found_user = (await DatabaseSession.execute(select(User))).scalar_one()
        found_queue = (
            await DatabaseSession.execute(
                select(Queue).where(
                    and_(
                        Queue.game_id == game.id,
                        Queue.user_xid == found_user.xid,
                    ),
                ),
            )
        ).scalar_one_or_none()
        assert found_queue is not None

    async def test_lfg_with_friend_when_existing_game(self, game: Game) -> None:
        user1 = UserFactory.create(xid=101)
        user2 = UserFactory.create(xid=102)

        new, game_data = await games.upsert(
            guild_xid=game.guild.xid,
            channel_xid=game.channel.xid,
            author_xid=user1.xid,
            friends=[user2.xid],
            criteria=GameCriteria(
                seats=4,
                rules=None,
                format=GameFormat.COMMANDER.value,
                bracket=GameBracket.NONE.value,
                service=GameService.CONVOKE.value,
            ),
            modes=ChannelModes(),
            locale="en",
        )
        assert not new
        assert game_data.id == game.id

        DatabaseSession.expire_all()
        rows = (
            await DatabaseSession.execute(select(Queue.user_xid).where(Queue.game_id == game.id))
        ).all()
        assert {row[0] for row in rows} == {101, 102}

    async def test_lfg_alone_when_no_game(self, guild: Guild, channel: Channel, user: User) -> None:
        new, game_data = await games.upsert(
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            author_xid=user.xid,
            friends=[],
            criteria=GameCriteria(
                seats=4,
                rules=None,
                format=GameFormat.COMMANDER.value,
                bracket=GameBracket.NONE.value,
                service=GameService.CONVOKE.value,
            ),
            modes=ChannelModes(),
            locale="en",
        )
        assert new
        assert game_data is not None

        DatabaseSession.expire_all()
        found_user = (await DatabaseSession.execute(select(User))).scalar_one()
        found_game = (await DatabaseSession.execute(select(Game))).scalar_one()
        found_queue = (await DatabaseSession.execute(select(Queue))).scalar_one()
        assert found_game.guild_xid == guild.xid
        assert found_game.channel_xid == channel.xid
        assert found_queue.game_id == found_game.id
        assert found_queue.user_xid == found_user.xid

    async def test_lfg_with_friend_when_no_game(self, guild: Guild, channel: Channel) -> None:
        user1 = UserFactory.create(xid=101)
        user2 = UserFactory.create(xid=102)

        new, game_data = await games.upsert(
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            author_xid=user1.xid,
            friends=[user2.xid],
            criteria=GameCriteria(
                seats=4,
                rules="some additional rules",
                format=GameFormat.COMMANDER.value,
                bracket=GameBracket.NONE.value,
                service=GameService.CONVOKE.value,
            ),
            modes=ChannelModes(),
            locale="en",
        )
        assert new
        assert game_data is not None

        DatabaseSession.expire_all()
        db_game = (await DatabaseSession.execute(select(Game))).scalar_one()
        assert db_game.guild_xid == guild.xid
        assert db_game.channel_xid == channel.xid
        rows = (
            await DatabaseSession.execute(select(Queue.user_xid).where(Queue.game_id == db_game.id))
        ).all()
        assert {row[0] for row in rows} == {101, 102}
        assert db_game.rules == "some additional rules"

    async def test_lfg_with_friend_when_full_game(self, guild: Guild, channel: Channel) -> None:
        user1 = UserFactory.create(xid=101)
        user2 = UserFactory.create(xid=102)
        user3 = UserFactory.create(xid=103)
        bad_game = GameFactory.create(seats=2, channel=channel, guild=guild)

        new, game_data = await games.upsert(
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            author_xid=user1.xid,
            friends=[user2.xid, user3.xid],
            criteria=GameCriteria(
                seats=4,
                rules=None,
                format=GameFormat.COMMANDER.value,
                bracket=GameBracket.NONE.value,
                service=GameService.CONVOKE.value,
            ),
            modes=ChannelModes(),
            locale="en",
        )
        assert new
        assert game_data is not None

        DatabaseSession.expire_all()
        db_game = (
            await DatabaseSession.execute(select(Game).where(Game.id != bad_game.id))
        ).scalar_one()
        assert db_game.guild_xid == guild.xid
        assert db_game.channel_xid == channel.xid
        rows = (
            await DatabaseSession.execute(select(Queue.user_xid).where(Queue.game_id == db_game.id))
        ).all()
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

        new, game_data = await games.upsert(
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            author_xid=user1.xid,
            friends=[user2.xid, user3.xid],
            criteria=GameCriteria(
                seats=4,
                rules=None,
                format=GameFormat.COMMANDER.value,
                bracket=GameBracket.NONE.value,
                service=GameService.CONVOKE.value,
            ),
            modes=ChannelModes(),
            locale="en",
        )
        assert new
        assert game_data is not None

        DatabaseSession.expire_all()
        db_game = (
            await DatabaseSession.execute(select(Game).where(Game.id != bad_game.id))
        ).scalar_one()
        assert db_game.guild_xid == guild.xid
        assert db_game.channel_xid == channel.xid
        rows = (
            await DatabaseSession.execute(select(Queue.user_xid).where(Queue.game_id == db_game.id))
        ).all()
        assert {row[0] for row in rows} == {101, 102, 103}

    async def test_lfg_when_existing_game_and_blocked(self, game: Game) -> None:
        user1 = UserFactory.create(xid=101, game=game)
        user2 = UserFactory.create(xid=102)
        BlockFactory.create(user_xid=user1.xid, blocked_user_xid=user2.xid)

        new, _ = await games.upsert(
            guild_xid=game.guild.xid,
            channel_xid=game.channel.xid,
            author_xid=user2.xid,
            friends=[],
            criteria=GameCriteria(
                seats=game.seats,
                rules=None,
                format=game.format,
                bracket=game.bracket,
                service=GameService.CONVOKE.value,
            ),
            modes=ChannelModes(),
            locale="en",
        )

        DatabaseSession.expire_all()
        other_game = (
            await DatabaseSession.execute(select(Game).where(Game.id != game.id))
        ).scalar_one()
        assert new
        assert [p.xid for p in await game_players(game)] == [user1.xid]
        assert [p.xid for p in await game_players(other_game)] == [user2.xid]

    async def test_lfg_when_existing_game_and_blocker(self, game: Game) -> None:
        user1 = UserFactory.create(xid=101, game=game)
        user2 = UserFactory.create(xid=102)
        BlockFactory.create(user_xid=user2.xid, blocked_user_xid=user1.xid)

        new, _ = await games.upsert(
            guild_xid=game.guild.xid,
            channel_xid=game.channel.xid,
            author_xid=user2.xid,
            friends=[],
            criteria=GameCriteria(
                seats=game.seats,
                rules=None,
                format=game.format,
                bracket=game.bracket,
                service=GameService.CONVOKE.value,
            ),
            modes=ChannelModes(),
            locale="en",
        )

        DatabaseSession.expire_all()
        other_game = (
            await DatabaseSession.execute(select(Game).where(Game.id != game.id))
        ).scalar_one()
        assert new
        assert [p.xid for p in await game_players(game)] == [user1.xid]
        assert [p.xid for p in await game_players(other_game)] == [user2.xid]

    async def test_lfg_when_existing_game_and_blocked_with_to_mode(self, game: Game) -> None:
        # In tournament organizer mode blocks are ignored, so the blocked user joins
        # the existing game rather than being split into a new one.
        user1 = UserFactory.create(xid=101, game=game)
        user2 = UserFactory.create(xid=102)
        BlockFactory.create(user_xid=user1.xid, blocked_user_xid=user2.xid)

        new, _ = await games.upsert(
            guild_xid=game.guild.xid,
            channel_xid=game.channel.xid,
            author_xid=user2.xid,
            friends=[],
            criteria=GameCriteria(
                seats=game.seats,
                rules=None,
                format=game.format,
                bracket=game.bracket,
                service=GameService.CONVOKE.value,
            ),
            modes=ChannelModes(to_mode=True),
            locale="en",
        )

        DatabaseSession.expire_all()
        all_games = (await DatabaseSession.execute(select(Game))).scalars().all()
        assert not new
        assert len(all_games) == 1
        assert sorted(p.xid for p in await game_players(game)) == [user1.xid, user2.xid]

    async def test_lfg_to_mode_with_no_matching_game(self, game: Game) -> None:
        # to_mode still creates a fresh game when no existing game matches the criteria
        # (exercises the empty-result path of the matchmaker's to_mode short-circuit).
        user = UserFactory.create(xid=201)
        unmatched_seats = game.seats + 2

        new, _ = await games.upsert(
            guild_xid=game.guild.xid,
            channel_xid=game.channel.xid,
            author_xid=user.xid,
            friends=[],
            criteria=GameCriteria(
                seats=unmatched_seats,
                rules=None,
                format=game.format,
                bracket=game.bracket,
                service=GameService.CONVOKE.value,
            ),
            modes=ChannelModes(to_mode=True),
            locale="en",
        )

        assert new

    async def test_new_game_snapshots_channel_modes(self, game: Game) -> None:
        user = UserFactory.create(xid=202)

        new, game_data = await games.upsert(
            guild_xid=game.guild.xid,
            channel_xid=game.channel.xid,
            author_xid=user.xid,
            friends=[],
            criteria=GameCriteria(
                seats=game.seats + 2,
                rules=None,
                format=game.format,
                bracket=game.bracket,
                service=GameService.CONVOKE.value,
            ),
            modes=ChannelModes(to_mode=True, competitive_mode=True),
            locale="en",
        )

        assert new
        created = await DatabaseSession.get(Game, game_data.id)
        assert created is not None
        assert created.to_mode is True
        assert created.competitive_mode is True


@pytest.mark.asyncio
class TestGamesPendingNotification:
    async def test_returns_old_pending_unnotified_game_with_open_seats(
        self,
        guild: Guild,
        channel: Channel,
    ) -> None:
        old = datetime.now(tz=UTC) - timedelta(minutes=settings.NOTIFY_GAMES_DELAY_M + 1)
        game = GameFactory.create(guild=guild, channel=channel, created_at=old)

        result = await games.games_pending_notification()

        assert [g.id for g in result] == [game.id]

    async def test_excludes_recently_created_games(
        self,
        guild: Guild,
        channel: Channel,
    ) -> None:
        recent = datetime.now(tz=UTC) - timedelta(minutes=settings.NOTIFY_GAMES_DELAY_M - 1)
        GameFactory.create(guild=guild, channel=channel, created_at=recent)

        result = await games.games_pending_notification()

        assert result == []

    async def test_excludes_already_notified_games(
        self,
        guild: Guild,
        channel: Channel,
    ) -> None:
        old = datetime.now(tz=UTC) - timedelta(minutes=settings.NOTIFY_GAMES_DELAY_M + 1)
        GameFactory.create(
            guild=guild,
            channel=channel,
            created_at=old,
            notified_at=datetime.now(tz=UTC),
        )

        result = await games.games_pending_notification()

        assert result == []

    async def test_excludes_started_and_deleted_games(
        self,
        guild: Guild,
        channel: Channel,
    ) -> None:
        old = datetime.now(tz=UTC) - timedelta(minutes=settings.NOTIFY_GAMES_DELAY_M + 1)
        GameFactory.create(
            guild=guild,
            channel=channel,
            created_at=old,
            started_at=datetime.now(tz=UTC),
            status=GameStatus.STARTED.value,
        )
        GameFactory.create(
            guild=guild,
            channel=channel,
            created_at=old,
            deleted_at=datetime.now(tz=UTC),
        )

        result = await games.games_pending_notification()

        assert result == []

    async def test_excludes_full_games(
        self,
        guild: Guild,
        channel: Channel,
    ) -> None:
        old = datetime.now(tz=UTC) - timedelta(minutes=settings.NOTIFY_GAMES_DELAY_M + 1)
        game = GameFactory.create(guild=guild, channel=channel, created_at=old, seats=2)
        u1 = UserFactory.create()
        u2 = UserFactory.create()
        DatabaseSession.add_all(
            [
                Queue(user_xid=u1.xid, game_id=game.id, og_guild_xid=guild.xid),
                Queue(user_xid=u2.xid, game_id=game.id, og_guild_xid=guild.xid),
            ],
        )
        await DatabaseSession.commit()

        result = await games.games_pending_notification()

        assert result == []


WAR_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER_WAR_ID = "11111111-2222-3333-4444-555555555555"


@pytest.mark.asyncio
class TestServiceGamesGuildWar:
    """Covers how Guild War games are stored and matched against each other."""

    async def upsert_war_game(
        self,
        guild: Guild,
        channel: Channel,
        author_xid: int,
        *,
        war_id: str | None,
        war_title: str | None = None,
    ) -> tuple[bool, int]:
        new, game_data = await games.upsert(
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            author_xid=author_xid,
            friends=[],
            criteria=GameCriteria(
                seats=4,
                rules=None,
                format=GameFormat.COMMANDER.value,
                bracket=GameBracket.NONE.value,
                service=GameService.CONVOKE.value,
                war_id=war_id,
                war_title=war_title,
            ),
            modes=ChannelModes(),
            locale="en",
        )
        return new, game_data.id

    async def test_war_fields_are_persisted(
        self,
        guild: Guild,
        channel: Channel,
        user: User,
    ) -> None:
        new, game_id = await self.upsert_war_game(
            guild,
            channel,
            user.xid,
            war_id=WAR_ID,
            war_title="Summer Clash",
        )
        assert new

        DatabaseSession.expire_all()
        game = await DatabaseSession.get(Game, game_id)
        assert game is not None
        assert game.war_id == WAR_ID
        assert game.war_title == "Summer Clash"

    async def test_a_war_game_joins_a_matching_war_game(
        self,
        guild: Guild,
        channel: Channel,
    ) -> None:
        first = UserFactory.create(xid=201)
        second = UserFactory.create(xid=202)
        _, first_id = await self.upsert_war_game(
            guild,
            channel,
            first.xid,
            war_id=WAR_ID,
            war_title="Summer Clash",
        )

        new, second_id = await self.upsert_war_game(guild, channel, second.xid, war_id=WAR_ID)

        assert not new
        assert second_id == first_id

    async def test_a_war_game_does_not_absorb_a_plain_game(
        self,
        guild: Guild,
        channel: Channel,
    ) -> None:
        # Someone who ran `/lfg` did not sign up for a Guild War match, so a `/war`
        # request must start its own game rather than joining theirs.
        plain = UserFactory.create(xid=203)
        warrior = UserFactory.create(xid=204)
        _, plain_id = await self.upsert_war_game(guild, channel, plain.xid, war_id=None)

        new, war_id_game = await self.upsert_war_game(
            guild,
            channel,
            warrior.xid,
            war_id=WAR_ID,
            war_title="Summer Clash",
        )

        assert new
        assert war_id_game != plain_id

    async def test_a_plain_game_does_not_absorb_a_war_game(
        self,
        guild: Guild,
        channel: Channel,
    ) -> None:
        # And the reverse: `/lfg` must not silently drop someone into a war match.
        warrior = UserFactory.create(xid=205)
        plain = UserFactory.create(xid=206)
        _, war_game_id = await self.upsert_war_game(
            guild,
            channel,
            warrior.xid,
            war_id=WAR_ID,
            war_title="Summer Clash",
        )

        new, plain_id = await self.upsert_war_game(guild, channel, plain.xid, war_id=None)

        assert new
        assert plain_id != war_game_id

    async def test_different_wars_do_not_share_a_game(
        self,
        guild: Guild,
        channel: Channel,
    ) -> None:
        first = UserFactory.create(xid=207)
        second = UserFactory.create(xid=208)
        _, first_id = await self.upsert_war_game(
            guild,
            channel,
            first.xid,
            war_id=WAR_ID,
            war_title="Summer Clash",
        )

        new, second_id = await self.upsert_war_game(
            guild,
            channel,
            second.xid,
            war_id=OTHER_WAR_ID,
            war_title="Winter Clash",
        )

        assert new
        assert second_id != first_id


@pytest.mark.asyncio
class TestGamesToData:
    def count_statements(self) -> list[str]:
        """Record every SQL statement the app's engine runs from now until the test ends."""
        statements: list[str] = []

        def record(*args: object) -> None:
            statements.append(str(args[2]))

        sync_engine = engine.get().sync_engine
        event.listen(sync_engine, "before_cursor_execute", record)
        self.listeners.append((sync_engine, record))
        return statements

    @pytest.fixture(autouse=True)
    def remove_listeners(self) -> Iterator[None]:
        self.listeners: list[tuple[Any, Callable[..., None]]] = []
        yield
        for target, listener in self.listeners:
            event.remove(target, "before_cursor_execute", listener)

    def make_games(self, guild: Guild, channel: Channel, count: int) -> list[Game]:
        """Half pending games with queued players, half started games with plays and pins."""
        made: list[Game] = []
        for i in range(count):
            if i % 2:
                game = GameFactory.create(
                    guild=guild,
                    channel=channel,
                    started_at=datetime.now(tz=UTC),
                    status=GameStatus.STARTED.value,
                )
                for _ in range(2):
                    user = UserFactory.create()
                    PlayFactory.create(game_id=game.id, user_xid=user.xid, pin="123456")
                PostFactory.create(game=game, guild=guild, channel=channel)
            else:
                game = GameFactory.create(guild=guild, channel=channel)
                UserFactory.create(game=game)  # also creates the game's post
                UserFactory.create(game=game)
            made.append(game)
        return made

    async def test_query_count_does_not_grow_with_games(self) -> None:
        guild = GuildFactory.create(enable_mythic_track=True)
        channel = ChannelFactory.create(guild=guild)
        one = self.make_games(guild, channel, 1)
        many = self.make_games(guild, channel, 6)

        statements = self.count_statements()
        await games.games_to_data(one)
        for_one = len(statements)
        statements.clear()
        built = await games.games_to_data(many)
        # guilds, channels, posts, plays, queues and users: one query each, however many games.
        assert for_one == len(statements) == 6

        assert [game.id for game in built] == [game.id for game in many]
        for game, data in zip(many, built, strict=True):
            assert len(data.players) == 2
            assert len(data.posts) == 1
            if game.started_at:
                assert set(data.player_pins.values()) == {"123456"}
            else:
                assert data.player_pins == {}

    async def test_no_games(self) -> None:
        statements = self.count_statements()
        assert await games.games_to_data([]) == []
        assert statements == []

    async def test_pins_hidden_without_mythic_track(self) -> None:
        guild = GuildFactory.create(enable_mythic_track=False)
        channel = ChannelFactory.create(guild=guild)
        started = self.make_games(guild, channel, 2)[1]
        data = await game_to_data(started)
        assert set(data.player_pins.values()) == {None}
