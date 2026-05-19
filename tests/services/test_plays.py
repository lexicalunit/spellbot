from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from spellbot.enums import GameFormat
from spellbot.models import GameStatus
from spellbot.services import plays

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
        assert await plays.guild_exists(guild.xid) is True
        assert await plays.guild_exists(99999) is False

    async def test_empty_guild(self, factories: Factories) -> None:
        guild = factories.guild.create(xid=5002, name="empty-guild")
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
            rules="no proxies allowed!",  # Test punctuation stripping
        )
        factories.play.create(game_id=game1.id, user_xid=user1.xid, og_guild_xid=guild.xid)
        factories.play.create(game_id=game1.id, user_xid=user2.xid, og_guild_xid=guild.xid)

        # Create game with rules that normalize to empty string (edge case)
        game2 = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            format=GameFormat.COMMANDER.value,
            started_at=now,
            created_at=now - timedelta(minutes=3),
            rules="...",  # Becomes empty after normalization
        )
        factories.play.create(game_id=game2.id, user_xid=user1.xid, og_guild_xid=guild.xid)

        factories.block.create(user_xid=user1.xid, blocked_user_xid=user2.xid)

        summary = await plays.analytics_summary(guild.xid, all_time=all_time)
        assert "total_games" in summary

        activity = await plays.analytics_activity(guild.xid, all_time=all_time)
        assert "games_per_day" in activity

        histogram = await plays.analytics_histogram(guild.xid, all_time=all_time)
        assert "games_histogram" in histogram

        channels = await plays.analytics_channels(guild.xid, all_time=all_time)
        assert "busiest_channels" in channels

        channel_players = await plays.analytics_channel_players(guild.xid, all_time=all_time)
        assert "channel_players" in channel_players

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

        hour = await plays.analytics_hour_of_day(guild.xid, all_time=all_time)
        assert "games_by_hour" in hour
        assert len(hour["games_by_hour"]) == 24

        dow = await plays.analytics_day_of_week(guild.xid, all_time=all_time)
        assert "games_by_day" in dow
        assert len(dow["games_by_day"]) == 7

        rules = await plays.analytics_rules(guild.xid, all_time=all_time)
        assert "top_rules" in rules
        assert "rule_ngrams" in rules

    async def test_histogram_empty_guild(self, factories: Factories) -> None:
        guild = factories.guild.create(xid=5008, name="empty-histogram-guild")
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

        # Without all_time, the old game should not appear
        result_30_days = await plays.analytics_players(guild.xid, all_time=False)
        assert result_30_days["top_players"] == []

        # With all_time=True, the old game should appear
        result_all_time = await plays.analytics_players(guild.xid, all_time=True)
        assert len(result_all_time["top_players"]) == 1
        assert result_all_time["top_players"][0]["user_xid"] == str(user.xid)


@pytest.mark.asyncio
class TestPlaysServiceRecords:
    """Tests for user_records and channel_records (direct invocation for coverage)."""

    async def test_user_records_missing_guild(self) -> None:
        assert await plays.user_records(guild_xid=99999, user_xid=1) is None

    async def test_user_records_returns_rows(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 6, 15, 12, 0, tzinfo=UTC))
        now = datetime.now(tz=UTC)

        guild = factories.guild.create(xid=8101, name="ur-guild")
        channel = factories.channel.create(xid=8201, name="ur-channel", guild=guild)
        user = factories.user.create(xid=8301, name="ur-user")
        game = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            format=GameFormat.COMMANDER.value,
            started_at=now,
            created_at=now - timedelta(minutes=5),
        )
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=9101)
        factories.play.create(game_id=game.id, user_xid=user.xid, og_guild_xid=guild.xid)

        rows = await plays.user_records(guild_xid=guild.xid, user_xid=user.xid)
        assert rows is not None
        assert len(rows) == 1
        assert rows[0]["channel"] == channel.xid

    async def test_channel_records_missing_guild(self) -> None:
        assert await plays.channel_records(guild_xid=99998, channel_xid=1) is None

    async def test_channel_records_missing_channel(self, factories: Factories) -> None:
        guild = factories.guild.create(xid=8102, name="cr-guild")
        assert await plays.channel_records(guild_xid=guild.xid, channel_xid=99997) is None

    async def test_channel_records_returns_rows(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 6, 15, 12, 0, tzinfo=UTC))
        now = datetime.now(tz=UTC)

        guild = factories.guild.create(xid=8103, name="cr-guild2")
        channel = factories.channel.create(xid=8203, name="cr-channel", guild=guild)
        user = factories.user.create(xid=8303, name="cr-user")
        game = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            format=GameFormat.COMMANDER.value,
            started_at=now,
            created_at=now - timedelta(minutes=5),
        )
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=9103)
        factories.play.create(game_id=game.id, user_xid=user.xid, og_guild_xid=guild.xid)

        rows = await plays.channel_records(guild_xid=guild.xid, channel_xid=channel.xid)
        assert rows is not None
        assert len(rows) == 1
        assert rows[0]["channel"] == channel.xid


class TestRulesHelpers:
    """Tests for normalize_rule and extract_ngrams helper functions."""

    def test_normalize_rule_strips_punctuation(self) -> None:
        assert plays.normalize_rule("no proxies!") == "no proxies"
        assert plays.normalize_rule("proxies ok...") == "proxies ok"
        assert plays.normalize_rule("rule?!") == "rule"

    def test_normalize_rule_empty_after_strip(self) -> None:
        # Edge case: rule becomes empty after stripping punctuation
        assert plays.normalize_rule("...") == ""
        assert plays.normalize_rule("!?") == ""

    def test_extract_ngrams_short_text(self) -> None:
        # Single word can't produce bigrams
        assert plays.extract_ngrams("proxies", 2) == []
        assert plays.extract_ngrams("no", 3) == []

    def test_extract_ngrams_produces_bigrams(self) -> None:
        result = plays.extract_ngrams("no proxies allowed", 2)
        assert "no proxies" in result
        assert "proxies allowed" in result

    def test_extract_ngrams_produces_trigrams(self) -> None:
        result = plays.extract_ngrams("no proxies allowed here", 3)
        assert "no proxies allowed" in result
        assert "proxies allowed here" in result
