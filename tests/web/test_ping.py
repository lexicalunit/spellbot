from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from spellbot import redis_client
from spellbot.redis_client import close_redis
from spellbot.settings import settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from aiohttp.client import ClientSession

pytestmark = pytest.mark.use_db


@pytest_asyncio.fixture(autouse=True)
async def reset_redis_client() -> AsyncGenerator[None]:
    redis_client._redis_client = None
    yield
    await close_redis()


@pytest.mark.asyncio
class TestWebPing:
    async def test_ping(self, client: ClientSession) -> None:
        resp = await client.get("/")
        assert resp.status == 200
        text = await resp.text()
        assert "ok" in text


@pytest.mark.asyncio
class TestWebStaticFiles:
    async def test_analytics_js(self, client: ClientSession) -> None:
        resp = await client.get("/analytics.js")
        assert resp.status == 200
        assert resp.content_type == "application/javascript"
        text = await resp.text()
        assert "ANALYTICS_CONFIG" in text
        assert resp.headers.get("Cache-Control") == "public, max-age=3600"


@pytest.mark.asyncio
class TestWebHealth:
    async def test_health_all_healthy(self, client: ClientSession) -> None:
        """Test health check when database is healthy and Redis is disabled."""
        with patch.object(settings, "REDIS_URL", None):
            resp = await client.get("/health")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "healthy"
            assert data["database"]["status"] == "healthy"
            assert data["redis"]["status"] == "disabled"

    async def test_health_with_redis_healthy(self, client: ClientSession) -> None:
        """Test health check when both database and Redis are healthy."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch(
                "spellbot.redis_client.aioredis.from_url",
                AsyncMock(return_value=mock_redis),
            ),
        ):
            resp = await client.get("/health")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "healthy"
            assert data["database"]["status"] == "healthy"
            assert data["redis"]["status"] == "healthy"

    async def test_health_database_unhealthy(self, client: ClientSession) -> None:
        """Test health check when database connection fails."""
        with (
            patch.object(settings, "REDIS_URL", None),
            patch(
                "spellbot.web.api.ping.db_session_manager",
                side_effect=Exception("Connection refused"),
            ),
        ):
            resp = await client.get("/health")
            assert resp.status == 503
            data = await resp.json()
            assert data["status"] == "unhealthy"
            assert data["database"]["status"] == "unhealthy"
            assert "Connection refused" in data["database"]["error"]

    async def test_health_redis_unhealthy(self, client: ClientSession) -> None:
        """Test health check when Redis connection fails."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(side_effect=Exception("Redis connection failed"))

        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch(
                "spellbot.redis_client.aioredis.from_url",
                AsyncMock(return_value=mock_redis),
            ),
        ):
            resp = await client.get("/health")
            assert resp.status == 503
            data = await resp.json()
            assert data["status"] == "unhealthy"
            assert data["database"]["status"] == "healthy"
            assert data["redis"]["status"] == "unhealthy"
            assert "Redis connection failed" in data["redis"]["error"]
