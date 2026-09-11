# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from spellbot.public_stats import (
    PUBLIC_STATS_KEY,
    PUBLIC_STATS_TTL,
    PublicStats,
    compute_public_stats,
    get_public_stats,
    update_public_stats,
)
from spellbot.settings import settings

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from tests.fixtures import Factories

NOW = datetime(2024, 6, 15, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
@pytest.mark.use_db
class TestComputePublicStats:
    async def test_counts_are_zero_when_nothing_is_active(self) -> None:
        stats = await compute_public_stats()

        assert stats.active_servers == 0
        assert stats.active_players == 0
        assert stats.active_games == 0

    async def test_counts_players_and_servers_across_queues(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=990001, name="Guild One")
        ch = factories.channel.create(xid=990101, name="lfg", guild=guild)
        game = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=None,
            created_at=NOW - timedelta(minutes=5),
            seats=4,
        )
        factories.post.create(guild=guild, channel=ch, game=game, message_xid=990201)
        for xid in (881001, 881002, 881003):
            user = factories.user.create(xid=xid, name=f"u{xid}")
            factories.queue.create(user_xid=user.xid, game_id=game.id, og_guild_xid=guild.xid)

        stats = await compute_public_stats()

        assert stats.active_servers == 1
        assert stats.active_players == 3
        assert stats.active_games == 1

    async def test_started_games_count_their_seats_as_players(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=990002, name="Guild Two")
        ch = factories.channel.create(xid=990102, name="lfg", guild=guild)
        game = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=NOW - timedelta(minutes=10),
            created_at=NOW - timedelta(minutes=20),
            seats=4,
        )
        factories.post.create(guild=guild, channel=ch, game=game, message_xid=990202)

        stats = await compute_public_stats()

        # A started game is full, so its seat count is its player count.
        assert stats.active_servers == 1
        assert stats.active_players == 4
        assert stats.active_games == 1

    async def test_a_server_with_both_a_queue_and_a_game_counts_once(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(NOW)
        guild = factories.guild.create(xid=990003, name="Guild Three")
        ch = factories.channel.create(xid=990103, name="lfg", guild=guild)

        pending = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=None,
            created_at=NOW - timedelta(minutes=3),
            seats=4,
        )
        factories.post.create(guild=guild, channel=ch, game=pending, message_xid=990203)
        user = factories.user.create(xid=881004, name="u881004")
        factories.queue.create(user_xid=user.xid, game_id=pending.id, og_guild_xid=guild.xid)

        started = factories.game.create(
            guild=guild,
            channel=ch,
            started_at=NOW - timedelta(minutes=10),
            created_at=NOW - timedelta(minutes=20),
            seats=4,
        )
        factories.post.create(guild=guild, channel=ch, game=started, message_xid=990204)

        stats = await compute_public_stats()

        assert stats.active_servers == 1  # deduplicated
        assert stats.active_players == 5  # 1 queued + 4 seated
        assert stats.active_games == 2


class TestPublicStatsSerialization:
    def test_round_trips_through_a_dict(self) -> None:
        stats = PublicStats(
            active_servers=3,
            active_players=12,
            active_games=5,
            last_updated="2024-06-15T12:00:00+00:00",
        )

        assert PublicStats.from_dict(stats.to_dict()) == stats


@pytest.mark.asyncio
class TestUpdatePublicStats:
    async def test_does_nothing_without_redis_configured(self) -> None:
        with (
            patch.object(settings, "REDIS_URL", None),
            patch("spellbot.public_stats.get_redis", AsyncMock()) as get_redis,
        ):
            await update_public_stats()

        get_redis.assert_not_called()

    async def test_writes_computed_stats_with_a_ttl(self) -> None:
        stats = PublicStats(
            active_servers=2,
            active_players=7,
            active_games=4,
            last_updated="2024-06-15T12:00:00+00:00",
        )
        redis = AsyncMock()

        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch("spellbot.public_stats.compute_public_stats", AsyncMock(return_value=stats)),
            patch("spellbot.public_stats.get_redis", AsyncMock(return_value=redis)),
        ):
            await update_public_stats()

        redis.set.assert_awaited_once_with(
            PUBLIC_STATS_KEY,
            json.dumps(stats.to_dict()),
            ex=PUBLIC_STATS_TTL,
        )

    async def test_swallows_errors_so_the_task_loop_survives(self) -> None:
        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch(
                "spellbot.public_stats.compute_public_stats",
                AsyncMock(side_effect=RuntimeError("boom")),
            ),
        ):
            await update_public_stats()  # must not raise


@pytest.mark.asyncio
class TestGetPublicStats:
    async def test_returns_none_without_redis_configured(self) -> None:
        with patch.object(settings, "REDIS_URL", None):
            assert await get_public_stats() is None

    async def test_returns_none_when_nothing_is_cached(self) -> None:
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)

        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch("spellbot.public_stats.get_redis", AsyncMock(return_value=redis)),
        ):
            assert await get_public_stats() is None

    async def test_returns_the_cached_stats(self) -> None:
        stats = PublicStats(
            active_servers=2,
            active_players=7,
            active_games=4,
            last_updated="2024-06-15T12:00:00+00:00",
        )
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=json.dumps(stats.to_dict()))

        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch("spellbot.public_stats.get_redis", AsyncMock(return_value=redis)),
        ):
            assert await get_public_stats() == stats

    async def test_returns_none_when_redis_errors(self) -> None:
        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch(
                "spellbot.public_stats.get_redis",
                AsyncMock(side_effect=RuntimeError("boom")),
            ),
        ):
            assert await get_public_stats() is None
