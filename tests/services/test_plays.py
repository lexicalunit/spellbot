from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from spellbot.enums import GameFormat
from spellbot.models import GameStatus
from spellbot.services import PlaysService

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest_asyncio.fixture(params=[True, False])
async def all_time(request: pytest.FixtureRequest) -> bool:
    return request.param


@pytest.mark.asyncio
class TestPlaysServiceAnalyticsSummary:
    """Tests for the analytics_summary method."""

    async def test_guild_exists(self, factories: Factories) -> None:
        guild = factories.guild.create(xid=5001, name="test-guild")
        plays = PlaysService()
        assert await plays.guild_exists(guild.xid) is True
        assert await plays.guild_exists(99999) is False

    async def test_empty_guild(self, factories: Factories) -> None:
        guild = factories.guild.create(xid=5002, name="empty-guild")
        plays = PlaysService()
        result = await plays.analytics_summary(guild.xid)
        assert result["total_games"] == 0
        assert result["fill_rate"] == 0.0
        assert result["active_players"] == 0
        assert result["repeat_player_rate"] == 0.0

    async def test_guild_with_games(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 6, 15, 12, 0, tzinfo=UTC))
        now = datetime.now(tz=UTC)

        guild = factories.guild.create(xid=5003, name="active-guild")
        channel = factories.channel.create(xid=6001, name="game-channel", guild=guild)
        user1 = factories.user.create(xid=7001, name="alice")
        user2 = factories.user.create(xid=7002, name="bob")

        game1 = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            format=GameFormat.COMMANDER.value,
            started_at=now,
            created_at=now - timedelta(minutes=5),
        )
        factories.play.create(game_id=game1.id, user_xid=user1.xid, og_guild_xid=guild.xid)
        factories.play.create(game_id=game1.id, user_xid=user2.xid, og_guild_xid=guild.xid)

        plays = PlaysService()
        result = await plays.analytics_summary(guild.xid)

        assert result["total_games"] == 1
        assert result["active_players"] == 2
        assert result["fill_rate"] == 100.0

    async def test_repeat_player_rate(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 6, 15, 12, 0, tzinfo=UTC))
        now = datetime.now(tz=UTC)

        guild = factories.guild.create(xid=5004, name="repeat-guild")
        channel = factories.channel.create(xid=6003, name="ch", guild=guild)
        user1 = factories.user.create(xid=7010, name="repeat-player")
        user2 = factories.user.create(xid=7011, name="one-timer")

        # Two games for user1, one game for user2
        game1 = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            started_at=now,
            created_at=now - timedelta(minutes=5),
        )
        factories.play.create(game_id=game1.id, user_xid=user1.xid, og_guild_xid=guild.xid)
        factories.play.create(game_id=game1.id, user_xid=user2.xid, og_guild_xid=guild.xid)

        game2 = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            started_at=now - timedelta(hours=1),
            created_at=now - timedelta(hours=1, minutes=5),
        )
        factories.play.create(game_id=game2.id, user_xid=user1.xid, og_guild_xid=guild.xid)

        plays = PlaysService()
        result = await plays.analytics_summary(guild.xid)

        assert result["active_players"] == 2
        # user1 played 2 games, user2 played 1 => 1 repeat out of 2 = 50%
        assert result["repeat_player_rate"] == 50.0

    async def test_all_analytics_branches(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
        all_time: bool,
    ) -> None:
        freezer.move_to(datetime(2020, 6, 15, 12, 0, tzinfo=UTC))
        now = datetime.now(tz=UTC)

        guild = factories.guild.create(xid=5007, name="branch-guild")
        channel = factories.channel.create(xid=6006, name="ch", guild=guild)
        user1 = factories.user.create(xid=7030, name="player1")
        user2 = factories.user.create(xid=7031, name="player2")

        game1 = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            format=GameFormat.COMMANDER.value,
            started_at=now,
            created_at=now - timedelta(minutes=5),
        )
        factories.play.create(game_id=game1.id, user_xid=user1.xid, og_guild_xid=guild.xid)
        factories.play.create(game_id=game1.id, user_xid=user2.xid, og_guild_xid=guild.xid)

        factories.block.create(user_xid=user1.xid, blocked_user_xid=user2.xid)

        plays = PlaysService()

        summary = await plays.analytics_summary(guild.xid, all_time=all_time)
        assert "total_games" in summary

        activity = await plays.analytics_activity(guild.xid, all_time=all_time)
        assert "games_per_day" in activity

        histogram = await plays.analytics_histogram(guild.xid, all_time=all_time)
        assert "games_histogram" in histogram

        channels = await plays.analytics_channels(guild.xid, all_time=all_time)
        assert "busiest_channels" in channels

        wt = await plays.analytics_wait_time(guild.xid, all_time=all_time)
        assert "avg_wait_per_day" in wt

        br = await plays.analytics_brackets(guild.xid, all_time=all_time)
        assert "games_by_bracket_per_day" in br

        ret = await plays.analytics_retention(guild.xid, all_time=all_time)
        assert "player_retention" in ret

        gr = await plays.analytics_growth(guild.xid, all_time=all_time)
        assert "cumulative_players" in gr

        fmt = await plays.analytics_formats(guild.xid, all_time=all_time)
        assert "popular_formats" in fmt

        svc = await plays.analytics_services(guild.xid, all_time=all_time)
        assert "popular_services" in svc

        blk = await plays.analytics_blocked(guild.xid, all_time=all_time)
        assert "top_blocked" in blk

    async def test_histogram_empty_guild(self, factories: Factories) -> None:
        guild = factories.guild.create(xid=5008, name="empty-histogram-guild")
        plays = PlaysService()
        result = await plays.analytics_histogram(guild.xid)
        assert result["median_games"] == 0
        assert result["games_histogram"] == []

    async def test_retention_returning_player(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 6, 15, 12, 0, tzinfo=UTC))
        now = datetime.now(tz=UTC)

        guild = factories.guild.create(xid=5009, name="retention-guild")
        channel = factories.channel.create(xid=6007, name="ch", guild=guild)
        user = factories.user.create(xid=7040, name="returning-player")

        # First game two weeks ago (user's first game)
        game1 = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            format=GameFormat.COMMANDER.value,
            started_at=now - timedelta(weeks=2),
            created_at=now - timedelta(weeks=2, minutes=5),
        )
        factories.play.create(game_id=game1.id, user_xid=user.xid, og_guild_xid=guild.xid)

        # Second game this week (user is returning, not new)
        game2 = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            format=GameFormat.COMMANDER.value,
            started_at=now,
            created_at=now - timedelta(minutes=5),
        )
        factories.play.create(game_id=game2.id, user_xid=user.xid, og_guild_xid=guild.xid)

        plays = PlaysService()
        result = await plays.analytics_retention(guild.xid, all_time=True)
        assert "player_retention" in result
        weeks_with_returning = [w for w in result["player_retention"] if w["returning"] > 0]
        assert len(weeks_with_returning) > 0

    async def test_histogram_overflow_bucket(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """Test histogram overflow bucket for players with >20 games."""
        freezer.move_to(datetime(2020, 6, 15, 12, 0, tzinfo=UTC))
        now = datetime.now(tz=UTC)

        guild = factories.guild.create(xid=5010, name="overflow-histogram-guild")
        channel = factories.channel.create(xid=6008, name="ch", guild=guild)
        user = factories.user.create(xid=7041, name="power-player")

        # Create 25 games for the same user to trigger the overflow bucket
        for i in range(25):
            game = factories.game.create(
                guild=guild,
                channel=channel,
                status=GameStatus.STARTED.value,
                format=GameFormat.COMMANDER.value,
                started_at=now - timedelta(days=i % 29),
                created_at=now - timedelta(days=i % 29, minutes=5),
            )
            factories.play.create(game_id=game.id, user_xid=user.xid, og_guild_xid=guild.xid)

        plays = PlaysService()
        result = await plays.analytics_histogram(guild.xid)

        # Should have overflow bucket "21+"
        buckets = [b["bucket"] for b in result["games_histogram"]]
        assert "21+" in buckets

        # The overflow bucket should have 1 player (the power player)
        overflow_bucket = next(b for b in result["games_histogram"] if b["bucket"] == "21+")
        assert overflow_bucket["players"] == 1

    async def test_analytics_players_all_time(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """Test analytics_players with all_time=True parameter."""
        freezer.move_to(datetime(2020, 6, 15, 12, 0, tzinfo=UTC))
        now = datetime.now(tz=UTC)

        guild = factories.guild.create(xid=5011, name="all-time-players-guild")
        channel = factories.channel.create(xid=6009, name="ch", guild=guild)
        user = factories.user.create(xid=7042, name="all-time-player")

        # Create GuildMember record for the user
        factories.guild_member.create(user_xid=user.xid, guild_xid=guild.xid)

        # Create a game from 60 days ago (outside 30-day window)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            format=GameFormat.COMMANDER.value,
            started_at=now - timedelta(days=60),
            created_at=now - timedelta(days=60, minutes=5),
        )
        factories.play.create(game_id=game.id, user_xid=user.xid, og_guild_xid=guild.xid)

        plays = PlaysService()

        # Without all_time, the old game should not appear
        result_30_days = await plays.analytics_players(guild.xid, all_time=False)
        assert result_30_days["top_players"] == []

        # With all_time=True, the old game should appear
        result_all_time = await plays.analytics_players(guild.xid, all_time=True)
        assert len(result_all_time["top_players"]) == 1
        assert result_all_time["top_players"][0]["user_xid"] == str(user.xid)
