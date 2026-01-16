from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from spellbot.shard_status import ShardStatus

if TYPE_CHECKING:
    from aiohttp.client import ClientSession


@pytest.mark.asyncio
class TestWebStatus:
    async def test_status_no_redis(self, client: ClientSession) -> None:
        """Test status page when Redis is not configured."""
        with patch("spellbot.shard_status.settings") as mock_settings:
            mock_settings.REDIS_URL = None
            resp = await client.get("/status")
            assert resp.status == 200
            text = await resp.text()
            assert "SpellBot Status" in text
            assert "No shard data available" in text

    async def test_status_with_shards(self, client: ClientSession) -> None:
        """Test status page with shard data."""
        mock_statuses = [
            ShardStatus(
                shard_id=0,
                latency_ms=45.5,
                guild_count=100,
                is_ready=True,
                last_updated="2026-01-13T12:00:00+00:00",
                version="1.0.0",
            ),
            ShardStatus(
                shard_id=1,
                latency_ms=62.3,
                guild_count=150,
                is_ready=True,
                last_updated="2026-01-13T12:00:00+00:00",
                version="1.0.0",
            ),
        ]
        mock_metadata = {
            "shard_count": 2,
            "total_guilds": 250,
            "last_updated": "2026-01-13T12:00:00+00:00",
        }

        with patch(
            "spellbot.web.api.status.get_all_shard_statuses",
            new_callable=AsyncMock,
            return_value=(mock_statuses, mock_metadata),
        ):
            resp = await client.get("/status")
            assert resp.status == 200
            text = await resp.text()
            assert "SpellBot Status" in text
            assert "Shard 0" in text
            assert "Shard 1" in text
            assert "45.5ms" in text
            assert "250" in text  # total guilds
            assert "healthy" in text.lower()

    async def test_status_degraded(self, client: ClientSession) -> None:
        """Test status page when some shards are down."""
        mock_statuses = [
            ShardStatus(
                shard_id=0,
                latency_ms=45.5,
                guild_count=100,
                is_ready=True,
                last_updated="2026-01-13T12:00:00+00:00",
                version="1.0.0",
            ),
            ShardStatus(
                shard_id=1,
                latency_ms=None,
                guild_count=0,
                is_ready=False,
                last_updated="2026-01-13T12:00:00+00:00",
                version="1.0.0",
            ),
        ]
        mock_metadata = {
            "shard_count": 2,
            "total_guilds": 100,
            "last_updated": "2026-01-13T12:00:00+00:00",
        }

        with patch(
            "spellbot.web.api.status.get_all_shard_statuses",
            new_callable=AsyncMock,
            return_value=(mock_statuses, mock_metadata),
        ):
            resp = await client.get("/status")
            assert resp.status == 200
            text = await resp.text()
            assert "degraded" in text.lower()
            assert "Not Ready" in text
