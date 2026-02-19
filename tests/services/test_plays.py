from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.models import GameStatus
from spellbot.services import PlaysService

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestPlaysServiceGuildAnalytics:
    async def test_guild_not_found(self) -> None:
        plays = PlaysService()
        result = await plays.guild_analytics(99999)
        assert result is None

    async def test_empty_guild(self, factories: Factories) -> None:
        guild = factories.guild.create(xid=5001, name="empty-guild")
        plays = PlaysService()
        result = await plays.guild_analytics(guild.xid)
        assert result is not None
        assert result["guild_name"] == "empty-guild"
        assert result["total_games"] == 0
        assert result["fill_rate"] == 0.0
        assert result["unique_players"] == 0
        assert result["monthly_active_users"] == 0
        assert result["repeat_player_rate"] == 0.0
        assert result["games_per_day"] == []
        assert result["avg_wait_per_day"] == []
        assert result["expired_per_day"] == []
        assert result["daily_new_users"] == []
        assert result["games_by_hour"] == []
        assert result["expired_by_hour"] == []
        assert result["new_users_by_hour"] == []
        assert result["games_by_bracket_per_day"] == []
        assert result["player_retention"] == []
        assert result["cumulative_players"] == []
        assert result["median_games"] == 0
        assert result["games_histogram"] == []
        assert result["popular_formats"] == []
        assert result["busiest_channels"] == []
        assert result["popular_services"] == []
        assert result["top_players"] == []

    async def test_guild_with_started_games(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 6, 15, 12, 0, tzinfo=UTC))
        now = datetime.now(tz=UTC)

        guild = factories.guild.create(xid=5002, name="active-guild")
        channel = factories.channel.create(xid=6001, name="game-channel", guild=guild)
        user1 = factories.user.create(xid=7001, name="alice")
        user2 = factories.user.create(xid=7002, name="bob")

        game1 = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            format=GameFormat.COMMANDER.value,
            service=GameService.CONVOKE.value,
            bracket=GameBracket.BRACKET_2.value,
            started_at=now,
            created_at=now - timedelta(minutes=5),
        )
        factories.play.create(game_id=game1.id, user_xid=user1.xid, og_guild_xid=guild.xid)
        factories.play.create(game_id=game1.id, user_xid=user2.xid, og_guild_xid=guild.xid)

        game2 = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            format=GameFormat.COMMANDER.value,
            service=GameService.CONVOKE.value,
            bracket=GameBracket.BRACKET_3.value,
            started_at=now - timedelta(days=1),
            created_at=now - timedelta(days=1, minutes=10),
        )
        factories.play.create(game_id=game2.id, user_xid=user1.xid, og_guild_xid=guild.xid)

        plays = PlaysService()
        result = await plays.guild_analytics(guild.xid)

        assert result is not None
        assert result["guild_name"] == "active-guild"
        assert result["total_games"] == 2
        assert result["unique_players"] == 2
        assert result["monthly_active_users"] == 2
        assert result["fill_rate"] == 100.0
        assert len(result["games_per_day"]) == 2
        assert len(result["avg_wait_per_day"]) == 2
        assert len(result["popular_formats"]) == 1
        assert result["popular_formats"][0]["count"] == 2
        assert len(result["busiest_channels"]) == 1
        assert result["busiest_channels"][0]["name"] == "game-channel"
        assert len(result["popular_services"]) == 1
        assert len(result["top_players"]) == 2
        assert len(result["games_by_bracket_per_day"]) >= 1
        assert len(result["games_by_hour"]) >= 1
        assert result["median_games"] > 0
        assert len(result["games_histogram"]) > 0
        assert len(result["cumulative_players"]) > 0

    async def test_expired_games(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 6, 15, 14, 0, tzinfo=UTC))
        now = datetime.now(tz=UTC)

        guild = factories.guild.create(xid=5003, name="expire-guild")
        channel = factories.channel.create(xid=6002, name="ch", guild=guild)

        # One started game
        game1 = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            started_at=now,
            created_at=now - timedelta(minutes=3),
        )
        user1 = factories.user.create(xid=7003, name="u1")
        factories.play.create(game_id=game1.id, user_xid=user1.xid, og_guild_xid=guild.xid)

        # One expired game (deleted before starting)
        factories.game.create(
            guild=guild,
            channel=channel,
            started_at=None,
            deleted_at=now,
            created_at=now - timedelta(minutes=20),
        )

        plays = PlaysService()
        result = await plays.guild_analytics(guild.xid)

        assert result is not None
        assert result["total_games"] == 1
        assert result["fill_rate"] == 50.0
        assert len(result["expired_per_day"]) == 1
        assert len(result["expired_by_hour"]) == 1

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
        result = await plays.guild_analytics(guild.xid)

        assert result is not None
        assert result["monthly_active_users"] == 2
        # user1 played 2 games, user2 played 1 => 1 repeat out of 2 = 50%
        assert result["repeat_player_rate"] == 50.0

    async def test_player_retention(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 6, 15, 12, 0, tzinfo=UTC))
        now = datetime.now(tz=UTC)

        guild = factories.guild.create(xid=5005, name="retention-guild")
        channel = factories.channel.create(xid=6004, name="ch", guild=guild)
        user1 = factories.user.create(xid=7020, name="veteran")

        # Game in previous week
        game_old = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            started_at=now - timedelta(days=8),
            created_at=now - timedelta(days=8, minutes=5),
        )
        factories.play.create(game_id=game_old.id, user_xid=user1.xid, og_guild_xid=guild.xid)

        # Game in current week
        game_new = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            started_at=now,
            created_at=now - timedelta(minutes=5),
        )
        factories.play.create(game_id=game_new.id, user_xid=user1.xid, og_guild_xid=guild.xid)

        plays = PlaysService()
        result = await plays.guild_analytics(guild.xid)

        assert result is not None
        assert len(result["player_retention"]) >= 1
        # user1 is returning (played in a previous week)
        total_returning = sum(w["returning"] for w in result["player_retention"])
        assert total_returning >= 1

    async def test_median_games_even_count(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """Test median calculation with even number of players."""
        freezer.move_to(datetime(2020, 6, 15, 12, 0, tzinfo=UTC))
        now = datetime.now(tz=UTC)

        guild = factories.guild.create(xid=5006, name="median-guild")
        channel = factories.channel.create(xid=6005, name="ch", guild=guild)
        user1 = factories.user.create(xid=7030, name="u1")
        user2 = factories.user.create(xid=7031, name="u2")

        # user1 plays 2 games, user2 plays 1 game
        for i in range(2):
            g = factories.game.create(
                guild=guild,
                channel=channel,
                status=GameStatus.STARTED.value,
                started_at=now - timedelta(hours=i),
                created_at=now - timedelta(hours=i, minutes=5),
            )
            factories.play.create(game_id=g.id, user_xid=user1.xid, og_guild_xid=guild.xid)

        g2 = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            started_at=now - timedelta(hours=3),
            created_at=now - timedelta(hours=3, minutes=5),
        )
        factories.play.create(game_id=g2.id, user_xid=user2.xid, og_guild_xid=guild.xid)

        plays = PlaysService()
        result = await plays.guild_analytics(guild.xid)

        assert result is not None
        # counts = [1, 2], even length => median = (1 + 2) / 2 = 1.5
        assert result["median_games"] == 1.5
        assert len(result["games_histogram"]) == 2

    async def test_histogram_overflow(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """Test histogram overflow bucket (>20 games)."""
        freezer.move_to(datetime(2020, 6, 15, 12, 0, tzinfo=UTC))
        now = datetime.now(tz=UTC)

        guild = factories.guild.create(xid=5007, name="overflow-guild")
        channel = factories.channel.create(xid=6006, name="ch", guild=guild)
        user = factories.user.create(xid=7040, name="power-user")

        # Create 22 games for one user
        for i in range(22):
            g = factories.game.create(
                guild=guild,
                channel=channel,
                status=GameStatus.STARTED.value,
                started_at=now - timedelta(hours=i),
                created_at=now - timedelta(hours=i, minutes=5),
            )
            factories.play.create(game_id=g.id, user_xid=user.xid, og_guild_xid=guild.xid)

        plays = PlaysService()
        result = await plays.guild_analytics(guild.xid)

        assert result is not None
        assert result["median_games"] == 22
        # Should have buckets 1-20 plus a "21+" overflow bucket
        assert any("+" in h["bucket"] for h in result["games_histogram"])
