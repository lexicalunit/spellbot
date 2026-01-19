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

    async def test_update_shard_status_with_null_latency(self) -> None:
        """Test that update_shard_status handles null latency."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.aclose = AsyncMock()

        mock_shard = MagicMock()
        mock_shard.latency = None  # Null latency
        mock_shard.is_closed.return_value = False

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
            assert mock_redis.set.call_count == 2
            shard_call = mock_redis.set.call_args_list[0]
            shard_json = json.loads(shard_call[0][1])
            assert shard_json["latency_ms"] is None

    async def test_update_shard_status_with_existing_newer_version(self) -> None:
        """Test version comparison when existing version is newer."""
        existing_metadata = json.dumps({"version": "99.99.99", "shard_count": 1})
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.get = AsyncMock(return_value=existing_metadata)
        mock_redis.aclose = AsyncMock()

        mock_shard = MagicMock()
        mock_shard.latency = 0.045
        mock_shard.is_closed.return_value = False

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

            # Verify the metadata was set with the newer version preserved
            assert mock_redis.set.call_count == 2
            metadata_call = mock_redis.set.call_args_list[1]
            metadata_json = json.loads(metadata_call[0][1])
            assert metadata_json["version"] == "99.99.99"

    async def test_update_shard_status_with_invalid_existing_version(self) -> None:
        """Test version comparison when existing version is invalid."""
        existing_metadata = json.dumps({"version": "invalid-version", "shard_count": 1})
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.get = AsyncMock(return_value=existing_metadata)
        mock_redis.aclose = AsyncMock()

        mock_shard = MagicMock()
        mock_shard.latency = 0.045
        mock_shard.is_closed.return_value = False

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

            # Should not raise and should write current version
            assert mock_redis.set.call_count == 2

    async def test_update_shard_status_with_existing_older_version(self) -> None:
        """Test version comparison when existing version is older."""
        existing_metadata = json.dumps({"version": "0.0.1", "shard_count": 1})
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.get = AsyncMock(return_value=existing_metadata)
        mock_redis.aclose = AsyncMock()

        mock_shard = MagicMock()
        mock_shard.latency = 0.045
        mock_shard.is_closed.return_value = False

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
            patch("spellbot.shard_status.__version__", "1.0.0"),
        ):
            mock_settings.REDIS_URL = "redis://localhost"
            mock_from_url.return_value = mock_redis

            await update_shard_status(bot)

            # Verify the metadata was set with the current version (not the older one)
            assert mock_redis.set.call_count == 2
            metadata_call = mock_redis.set.call_args_list[1]
            metadata_json = json.loads(metadata_call[0][1])
            assert metadata_json["version"] == "1.0.0"

    async def test_update_shard_status_redis_error(self) -> None:
        """Test that Redis errors are handled gracefully."""
        bot = MagicMock()
        bot.shard_count = 1
        bot.shards = {0: MagicMock()}
        bot.ready_shards = {0}

        with (
            patch("spellbot.shard_status.settings") as mock_settings,
            patch(
                "spellbot.shard_status.aioredis.from_url",
                new_callable=AsyncMock,
            ) as mock_from_url,
        ):
            mock_settings.REDIS_URL = "redis://localhost"
            mock_from_url.side_effect = Exception("Redis connection failed")

            # Should not raise
            await update_shard_status(bot)


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

    async def test_get_all_shard_statuses_with_empty_data(self) -> None:
        """Test that empty shard data is handled."""
        metadata = {
            "shard_count": 1,
            "total_guilds": 0,
            "last_updated": "2026-01-13T12:00:00+00:00",
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(
            side_effect=[
                json.dumps(metadata),  # First call for metadata
                None,  # Second call for shard data returns None
            ],
        )
        mock_redis.scan_iter = MagicMock(
            return_value=AsyncIterator([f"{SHARD_STATUS_PREFIX}0:1.0.0"]),
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

            # No statuses because the get call returned None
            assert len(statuses) == 0
            assert meta is not None

    async def test_get_all_shard_statuses_redis_error(self) -> None:
        """Test that Redis errors are handled gracefully."""
        with (
            patch("spellbot.shard_status.settings") as mock_settings,
            patch(
                "spellbot.shard_status.aioredis.from_url",
                new_callable=AsyncMock,
            ) as mock_from_url,
        ):
            mock_settings.REDIS_URL = "redis://localhost"
            mock_from_url.side_effect = Exception("Redis connection failed")

            statuses, meta = await get_all_shard_statuses()

            assert statuses == []
            assert meta is None


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
