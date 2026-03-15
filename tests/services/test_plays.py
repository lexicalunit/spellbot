from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from spellbot.enums import GameFormat
from spellbot.models import GameStatus
from spellbot.services import PlaysService

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


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
        assert result["unique_players"] == 0
        assert result["monthly_active_users"] == 0
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
        assert result["unique_players"] == 2
        assert result["monthly_active_users"] == 2
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

        assert result["monthly_active_users"] == 2
        # user1 played 2 games, user2 played 1 => 1 repeat out of 2 = 50%
        assert result["repeat_player_rate"] == 50.0
