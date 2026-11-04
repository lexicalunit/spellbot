# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import discord
import pytest
import pytest_asyncio

from spellbot import SpellBot, redis_client, shard_status
from spellbot.redis_client import close_redis
from spellbot.settings import settings
from spellbot.shard_status import (
    SHARD_STATUS_PREFIX,
    ShardStatus,
    get_all_shard_statuses,
    update_shard_status,
)
from tests.mocks.redis import FakeRedis, serve_redis

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from decoy import Decoy

METADATA_KEY = f"{SHARD_STATUS_PREFIX}metadata"


def one_shard_bot(decoy: Decoy, *, latency: float | None = 0.045, guilds: int = 1) -> SpellBot:
    """Build a bot running a single, connected shard 0 that holds `guilds` guilds."""
    shard = decoy.mock(cls=discord.ShardInfo)
    # discord.py types `latency` as always set, but `update_shard_status` guards against `None`.
    decoy.when(shard.latency).then_return(latency)  # ty: ignore[invalid-argument-type]
    decoy.when(shard.is_closed()).then_return(False)
    guild = decoy.mock(cls=discord.Guild)
    decoy.when(guild.shard_id).then_return(0)
    bot = decoy.mock(cls=SpellBot)
    bot.shard_count = 1
    bot.ready_shards = {0}
    decoy.when(bot.shards).then_return({0: shard})
    decoy.when(bot.get_shard(0)).then_return(shard)
    decoy.when(bot.guilds).then_return([guild] * guilds)
    return bot


def shard_key(shard_id: int = 0) -> str:
    return f"{SHARD_STATUS_PREFIX}{shard_id}:{shard_status.__version__}"


@pytest_asyncio.fixture(autouse=True)
async def reset_redis_client() -> AsyncGenerator[None]:
    redis_client.shared.client = None
    yield
    await close_redis()


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
    async def test_update_shard_status_no_redis(
        self,
        decoy: Decoy,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that update_shard_status does nothing when Redis is not configured."""
        monkeypatch.setattr(settings, "REDIS_URL", None)
        await update_shard_status(decoy.mock(cls=SpellBot))  # Should not raise

    async def test_update_shard_status_with_redis(
        self,
        decoy: Decoy,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that update_shard_status writes the shard and the metadata to Redis."""
        redis = FakeRedis()
        serve_redis(monkeypatch, redis)

        await update_shard_status(one_shard_bot(decoy))

        assert set(redis.data) == {shard_key(), METADATA_KEY}
        shard = json.loads(redis.data[shard_key()])
        assert (shard["latency_ms"], shard["guild_count"], shard["is_ready"]) == (45.0, 1, True)
        metadata = json.loads(redis.data[METADATA_KEY])
        assert (metadata["shard_count"], metadata["total_guilds"]) == (1, 1)

    async def test_update_shard_status_with_null_latency(
        self,
        decoy: Decoy,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that update_shard_status handles null latency."""
        redis = FakeRedis()
        serve_redis(monkeypatch, redis)

        await update_shard_status(one_shard_bot(decoy, latency=None))

        assert json.loads(redis.data[shard_key()])["latency_ms"] is None

    async def test_update_shard_status_with_existing_newer_version(
        self,
        decoy: Decoy,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test version comparison when existing version is newer."""
        existing = json.dumps({"version": "99.99.99", "shard_count": 1})
        redis = FakeRedis(data={METADATA_KEY: existing})
        serve_redis(monkeypatch, redis)

        await update_shard_status(one_shard_bot(decoy))

        # The newer version is preserved
        assert json.loads(redis.data[METADATA_KEY])["version"] == "99.99.99"

    async def test_update_shard_status_with_invalid_existing_version(
        self,
        decoy: Decoy,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test version comparison when existing version is invalid."""
        existing = json.dumps({"version": "invalid-version", "shard_count": 1})
        redis = FakeRedis(data={METADATA_KEY: existing})
        serve_redis(monkeypatch, redis)

        await update_shard_status(one_shard_bot(decoy))

        # Should not raise and should write current version
        metadata = json.loads(redis.data[METADATA_KEY])
        assert metadata["version"] == shard_status.__version__

    async def test_update_shard_status_with_existing_older_version(
        self,
        decoy: Decoy,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test version comparison when existing version is older."""
        existing = json.dumps({"version": "0.0.1", "shard_count": 1})
        redis = FakeRedis(data={METADATA_KEY: existing})
        serve_redis(monkeypatch, redis)
        monkeypatch.setattr(shard_status, "__version__", "1.0.0")

        await update_shard_status(one_shard_bot(decoy))

        # The current version replaces the older one
        assert json.loads(redis.data[METADATA_KEY])["version"] == "1.0.0"

    async def test_update_shard_status_redis_error(
        self,
        decoy: Decoy,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that Redis errors are handled gracefully."""
        serve_redis(monkeypatch, Exception("Redis connection failed"))
        await update_shard_status(decoy.mock(cls=SpellBot))  # Should not raise

    async def test_update_shard_status_reuses_client(
        self,
        decoy: Decoy,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Repeated calls share a single Redis client (one connection)."""
        connections = serve_redis(monkeypatch, FakeRedis())
        bot = one_shard_bot(decoy, guilds=0)
        await update_shard_status(bot)
        await update_shard_status(bot)
        assert connections == ["redis://localhost"]


@pytest.mark.asyncio
class TestGetAllShardStatuses:
    async def test_get_all_shard_statuses_no_redis(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that get_all_shard_statuses returns empty when Redis is not configured."""
        monkeypatch.setattr(settings, "REDIS_URL", None)
        assert await get_all_shard_statuses() == ([], None)

    async def test_get_all_shard_statuses_with_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
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
        data = {METADATA_KEY: json.dumps(metadata), shard_key(): json.dumps(shard_data)}
        serve_redis(monkeypatch, FakeRedis(data=data))

        statuses, meta = await get_all_shard_statuses()

        assert [status.shard_id for status in statuses] == [0]
        assert meta is not None
        assert meta["shard_count"] == 1

    async def test_get_all_shard_statuses_with_empty_data(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A shard key that comes back empty (say, it expired mid-scan) is skipped."""
        metadata = {
            "shard_count": 1,
            "total_guilds": 0,
            "last_updated": "2026-01-13T12:00:00+00:00",
        }
        data = {METADATA_KEY: json.dumps(metadata), f"{SHARD_STATUS_PREFIX}0:1.0.0": ""}
        serve_redis(monkeypatch, FakeRedis(data=data))

        statuses, meta = await get_all_shard_statuses()

        assert statuses == []
        assert meta is not None

    async def test_get_all_shard_statuses_redis_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that Redis errors are handled gracefully."""
        serve_redis(monkeypatch, Exception("Redis connection failed"))
        assert await get_all_shard_statuses() == ([], None)
