from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from spellbot.shard_status import ShardStatus
from spellbot.web.api.status import _format_latency, _format_time_ago, _get_latency_class

if TYPE_CHECKING:
    from aiohttp.client import ClientSession


class TestFormatLatency:
    @pytest.mark.parametrize(
        ("latency", "expected"),
        [
            pytest.param(None, "N/A", id="none"),
            pytest.param(45.123, "45.1ms", id="normal"),
            pytest.param(100.0, "100.0ms", id="exact"),
        ],
    )
    def test_format_latency(self, latency: float | None, expected: str) -> None:
        assert _format_latency(latency) == expected


class TestFormatTimeAgo:
    def test_seconds_ago(self) -> None:
        now = datetime.now(tz=UTC)
        timestamp = (now - timedelta(seconds=30)).isoformat()
        result = _format_time_ago(timestamp)
        assert "s ago" in result

    def test_minutes_ago(self) -> None:
        now = datetime.now(tz=UTC)
        timestamp = (now - timedelta(minutes=5)).isoformat()
        result = _format_time_ago(timestamp)
        assert "m ago" in result

    def test_hours_ago(self) -> None:
        now = datetime.now(tz=UTC)
        timestamp = (now - timedelta(hours=2)).isoformat()
        result = _format_time_ago(timestamp)
        assert "h ago" in result

    def test_invalid_timestamp(self) -> None:
        result = _format_time_ago("not a valid timestamp")
        assert result == "unknown"


class TestGetLatencyClass:
    @pytest.mark.parametrize(
        ("latency", "expected"),
        [
            pytest.param(None, "latency-unknown", id="none"),
            pytest.param(50.0, "latency-good", id="good_low"),
            pytest.param(99.9, "latency-good", id="good_high"),
            pytest.param(100.0, "latency-ok", id="ok_low"),
            pytest.param(249.9, "latency-ok", id="ok_high"),
            pytest.param(250.0, "latency-bad", id="bad_low"),
            pytest.param(500.0, "latency-bad", id="bad_high"),
        ],
    )
    def test_get_latency_class(self, latency: float | None, expected: str) -> None:
        assert _get_latency_class(latency) == expected


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

    async def test_status_upgrading(self, client: ClientSession) -> None:
        """Test status page during upgrade (multiple versions)."""
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
                version="2.0.0",  # Different version
            ),
        ]
        mock_metadata = {
            "shard_count": 2,
            "total_guilds": 250,
            "last_updated": "2026-01-13T12:00:00+00:00",
            "version": "2.0.0",
        }

        with patch(
            "spellbot.web.api.status.get_all_shard_statuses",
            new_callable=AsyncMock,
            return_value=(mock_statuses, mock_metadata),
        ):
            resp = await client.get("/status")
            assert resp.status == 200
            text = await resp.text()
            assert "upgrading" in text.lower()

    async def test_status_all_down(self, client: ClientSession) -> None:
        """Test status page when all shards are down."""
        mock_statuses = [
            ShardStatus(
                shard_id=0,
                latency_ms=None,
                guild_count=0,
                is_ready=False,
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
            "total_guilds": 0,
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
            assert "down" in text.lower()

    async def test_status_high_latency(self, client: ClientSession) -> None:
        """Test status page with high latency shards."""
        mock_statuses = [
            ShardStatus(
                shard_id=0,
                latency_ms=300.0,  # Bad latency
                guild_count=100,
                is_ready=True,
                last_updated="2026-01-13T12:00:00+00:00",
                version="1.0.0",
            ),
        ]
        mock_metadata = {
            "shard_count": 1,
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
            assert "300.0ms" in text
