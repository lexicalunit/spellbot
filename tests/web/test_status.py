from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from spellbot.shard_status import ShardStatus
from spellbot.web.api.status import _get_int, format_latency, format_time_ago, get_latency_class

if TYPE_CHECKING:
    from aiohttp.client import ClientSession


class TestGetInt:
    @pytest.mark.parametrize(
        ("metadata", "key", "default", "expected"),
        [
            pytest.param({"count": 5}, "count", 0, 5, id="int_value"),
            pytest.param({"count": "10"}, "count", 0, 10, id="string_value"),
            pytest.param({}, "count", 42, 42, id="missing_key"),
        ],
    )
    def test_get_int(
        self,
        metadata: dict[str, int | str],
        key: str,
        default: int,
        expected: int,
    ) -> None:
        assert _get_int(metadata, key, default) == expected


class TestFormatLatency:
    @pytest.mark.parametrize(
        ("latency", "expected"),
        [
            pytest.param(None, "N/A", id="none"),
            pytest.param(45.123, "45.1ms", id="normal"),
            pytest.param(100.0, "100.0ms", id="exact"),
        ],
    )
    def testformat_latency(self, latency: float | None, expected: str) -> None:
        assert format_latency(latency) == expected


class TestFormatTimeAgo:
    def test_seconds_ago(self) -> None:
        now = datetime.now(tz=UTC)
        timestamp = (now - timedelta(seconds=30)).isoformat()
        result = format_time_ago(timestamp)
        assert "s ago" in result

    def test_minutes_ago(self) -> None:
        now = datetime.now(tz=UTC)
        timestamp = (now - timedelta(minutes=5)).isoformat()
        result = format_time_ago(timestamp)
        assert "m ago" in result

    def test_hours_ago(self) -> None:
        now = datetime.now(tz=UTC)
        timestamp = (now - timedelta(hours=2)).isoformat()
        result = format_time_ago(timestamp)
        assert "h ago" in result

    def test_invalid_timestamp(self) -> None:
        result = format_time_ago("not a valid timestamp")
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
    def testget_latency_class(self, latency: float | None, expected: str) -> None:
        assert get_latency_class(latency) == expected


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


@pytest.mark.asyncio
class TestWebStatusJson:
    async def test_status_json_healthy(self, client: ClientSession) -> None:
        """Test JSON status endpoint when all shards are healthy."""
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
            "version": "1.0.0",
        }

        with patch(
            "spellbot.web.api.status.get_all_shard_statuses",
            new_callable=AsyncMock,
            return_value=(mock_statuses, mock_metadata),
        ):
            resp = await client.get("/status.json")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"]["indicator"] == "operational"
            assert data["status"]["description"] == "All Systems Operational"
            assert data["shards"]["total"] == 2
            assert data["shards"]["ready"] == 2
            assert len(data["shards"]["data"]) == 2
            assert data["guilds"] == 250
            assert data["version"] == "1.0.0"
            assert data["upgrade_in_progress"] is False

    async def test_status_json_degraded(self, client: ClientSession) -> None:
        """Test JSON status endpoint when some shards are down."""
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
            "version": "1.0.0",
        }

        with patch(
            "spellbot.web.api.status.get_all_shard_statuses",
            new_callable=AsyncMock,
            return_value=(mock_statuses, mock_metadata),
        ):
            resp = await client.get("/status.json")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"]["indicator"] == "degraded_performance"
            assert data["shards"]["ready"] == 1

    async def test_status_json_down(self, client: ClientSession) -> None:
        """Test JSON status endpoint when all shards are down."""
        mock_statuses = [
            ShardStatus(
                shard_id=0,
                latency_ms=None,
                guild_count=0,
                is_ready=False,
                last_updated="2026-01-13T12:00:00+00:00",
                version="1.0.0",
            ),
        ]
        mock_metadata = {
            "shard_count": 1,
            "total_guilds": 0,
            "last_updated": "2026-01-13T12:00:00+00:00",
            "version": "1.0.0",
        }

        with patch(
            "spellbot.web.api.status.get_all_shard_statuses",
            new_callable=AsyncMock,
            return_value=(mock_statuses, mock_metadata),
        ):
            resp = await client.get("/status.json")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"]["indicator"] == "major_outage"

    async def test_status_json_upgrading(self, client: ClientSession) -> None:
        """Test JSON status endpoint during upgrade."""
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
                latency_ms=50.0,
                guild_count=150,
                is_ready=True,
                last_updated="2026-01-13T12:00:00+00:00",
                version="1.1.0",
            ),
        ]
        mock_metadata = {
            "shard_count": 2,
            "total_guilds": 250,
            "last_updated": "2026-01-13T12:00:00+00:00",
            "version": "1.1.0",
        }

        with patch(
            "spellbot.web.api.status.get_all_shard_statuses",
            new_callable=AsyncMock,
            return_value=(mock_statuses, mock_metadata),
        ):
            resp = await client.get("/status.json")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"]["indicator"] == "maintenance"
            assert data["upgrade_in_progress"] is True

    async def test_status_json_no_data(self, client: ClientSession) -> None:
        """Test JSON status endpoint when no data is available."""
        with patch(
            "spellbot.web.api.status.get_all_shard_statuses",
            new_callable=AsyncMock,
            return_value=([], None),
        ):
            resp = await client.get("/status.json")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"]["indicator"] == "unknown"
