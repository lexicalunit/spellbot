from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from spellbot.shard_status import (
    SHARD_STATUS_PREFIX,
    ShardStatus,
    get_all_shard_statuses,
    update_shard_status,
)


class TestShardStatus:
    def test_shard_status_to_dict(self) -> None:
        status = ShardStatus(
            shard_id=0,
            latency_ms=45.5,
            guild_count=100,
            is_ready=True,
            last_updated="2026-01-13T12:00:00+00:00",
            version="1.0.0",
        )
        data = status.to_dict()
        assert data["shard_id"] == 0
        assert data["latency_ms"] == 45.5
        assert data["guild_count"] == 100
        assert data["is_ready"] is True
        assert data["last_updated"] == "2026-01-13T12:00:00+00:00"

    def test_shard_status_from_dict(self) -> None:
        data = {
            "shard_id": 1,
            "latency_ms": 62.3,
            "guild_count": 150,
            "is_ready": True,
            "last_updated": "2026-01-13T12:00:00+00:00",
        }
        status = ShardStatus.from_dict(data)
        assert status.shard_id == 1
        assert status.latency_ms == 62.3
        assert status.guild_count == 150
        assert status.is_ready is True
        assert status.last_updated == "2026-01-13T12:00:00+00:00"

    def test_shard_status_from_dict_null_latency(self) -> None:
        data = {
            "shard_id": 0,
            "latency_ms": None,
            "guild_count": 0,
            "is_ready": False,
            "last_updated": "2026-01-13T12:00:00+00:00",
        }
        status = ShardStatus.from_dict(data)
        assert status.latency_ms is None
        assert status.is_ready is False


@pytest.mark.asyncio
class TestUpdateShardStatus:
    async def test_update_shard_status_no_redis(self) -> None:
        """Test that update_shard_status does nothing when Redis is not configured."""
        with patch("spellbot.shard_status.settings") as mock_settings:
            mock_settings.REDIS_URL = None
            bot = MagicMock()

            await update_shard_status(bot)  # Should not raise

    async def test_update_shard_status_with_redis(self) -> None:
        """Test that update_shard_status writes to Redis."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # No existing metadata
        mock_redis.aclose = AsyncMock()

        # Mock shard info
        mock_shard = MagicMock()
        mock_shard.latency = 0.045
        mock_shard.is_closed.return_value = False

        # Mock guild with shard_id
        mock_guild = MagicMock()
        mock_guild.shard_id = 0

        bot = MagicMock()
        bot.shard_count = 1
        bot.shards = {0: mock_shard}
        bot.ready_shards = {0}
        bot.get_shard.return_value = mock_shard
        bot.guilds = [mock_guild]

        with (
            patch("spellbot.shard_status.settings") as mock_settings,
            patch(
                "spellbot.shard_status.aioredis.from_url",
                new_callable=AsyncMock,
            ) as mock_from_url,
        ):
            mock_settings.REDIS_URL = "redis://localhost"
            mock_from_url.return_value = mock_redis

            await update_shard_status(bot)

            # Verify Redis was called
            assert mock_redis.set.call_count == 2  # One for shard, one for metadata
            mock_redis.aclose.assert_called_once()


@pytest.mark.asyncio
class TestGetAllShardStatuses:
    async def test_get_all_shard_statuses_no_redis(self) -> None:
        """Test that get_all_shard_statuses returns empty when Redis is not configured."""
        with patch("spellbot.shard_status.settings") as mock_settings:
            mock_settings.REDIS_URL = None
            statuses, metadata = await get_all_shard_statuses()
            assert statuses == []
            assert metadata is None

    async def test_get_all_shard_statuses_with_data(self) -> None:
        """Test that get_all_shard_statuses returns data from Redis."""
        shard_data = {
            "shard_id": 0,
            "latency_ms": 45.5,
            "guild_count": 100,
            "is_ready": True,
            "last_updated": "2026-01-13T12:00:00+00:00",
        }
        metadata = {
            "shard_count": 1,
            "total_guilds": 100,
            "last_updated": "2026-01-13T12:00:00+00:00",
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(
            side_effect=[
                json.dumps(metadata),  # First call for metadata
                json.dumps(shard_data),  # Second call for shard data
            ],
        )
        mock_redis.scan_iter = MagicMock(
            return_value=AsyncIterator([f"{SHARD_STATUS_PREFIX}0"]),
        )
        mock_redis.aclose = AsyncMock()

        with (
            patch("spellbot.shard_status.settings") as mock_settings,
            patch(
                "spellbot.shard_status.aioredis.from_url",
                new_callable=AsyncMock,
            ) as mock_from_url,
        ):
            mock_settings.REDIS_URL = "redis://localhost"
            mock_from_url.return_value = mock_redis

            statuses, meta = await get_all_shard_statuses()

            assert len(statuses) == 1
            assert statuses[0].shard_id == 0
            assert meta is not None
            assert meta["shard_count"] == 1


class AsyncIterator:
    """Helper class to create an async iterator from a list."""

    def __init__(self, items: list[str]) -> None:
        self.items = items
        self.index = 0

    def __aiter__(self) -> AsyncIterator:
        return self

    async def __anext__(self) -> str:
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item
