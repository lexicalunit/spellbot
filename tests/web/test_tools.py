from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from spellbot import redis_client
from spellbot.redis_client import close_redis
from spellbot.settings import settings
from spellbot.web.tools import rate_limited

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest_asyncio.fixture(autouse=True)
async def reset_redis_client() -> AsyncGenerator[None]:
    redis_client._redis_client = None
    yield
    await close_redis()


@pytest.mark.asyncio
class TestRateLimited:
    async def test_no_redis_url(self) -> None:
        """Test that rate limiting is disabled when Redis URL is not configured."""
        request = MagicMock()
        with patch.object(settings, "REDIS_URL", None):
            result = await rate_limited(request)
            assert result is False

    async def test_under_rate_limit(self) -> None:
        """Test request under rate limit."""
        request = MagicMock()
        request.remote = "192.168.1.1"

        mock_redis = AsyncMock()
        mock_redis.eval = AsyncMock(return_value="5")

        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch("spellbot.redis_client.aioredis.from_url", AsyncMock(return_value=mock_redis)),
        ):
            result = await rate_limited(request)
            assert result is False

    async def test_over_rate_limit(self) -> None:
        """Test request over rate limit."""
        request = MagicMock()
        request.remote = "192.168.1.1"

        mock_redis = AsyncMock()
        mock_redis.eval = AsyncMock(return_value="15")  # Over RATE_LIMIT of 10

        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch("spellbot.redis_client.aioredis.from_url", AsyncMock(return_value=mock_redis)),
        ):
            result = await rate_limited(request)
            assert result is True

    async def test_with_custom_key(self) -> None:
        """Test rate limiting with custom key."""
        request = MagicMock()
        request.remote = "192.168.1.1"

        mock_redis = AsyncMock()
        mock_redis.eval = AsyncMock(return_value="3")

        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch("spellbot.redis_client.aioredis.from_url", AsyncMock(return_value=mock_redis)),
        ):
            result = await rate_limited(request, key="custom:key")
            assert result is False
            # Verify the custom key was used
            mock_redis.eval.assert_called_once()
            call_args = mock_redis.eval.call_args[0]
            assert call_args[2] == "custom:key"

    async def test_redis_error(self) -> None:
        """Test that Redis errors are handled gracefully."""
        request = MagicMock()
        request.remote = "192.168.1.1"

        mock_redis = AsyncMock()
        mock_redis.eval = AsyncMock(side_effect=Exception("Redis error"))

        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch("spellbot.redis_client.aioredis.from_url", AsyncMock(return_value=mock_redis)),
        ):
            result = await rate_limited(request)
            # Should return False on error (fail open)
            assert result is False

    async def test_client_is_reused(self) -> None:
        """Repeated calls share a single Redis client (from_url called once)."""
        request = MagicMock()
        request.remote = "192.168.1.1"

        mock_redis = AsyncMock()
        mock_redis.eval = AsyncMock(return_value="1")

        from_url = AsyncMock(return_value=mock_redis)
        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch("spellbot.redis_client.aioredis.from_url", from_url),
        ):
            await rate_limited(request)
            await rate_limited(request)
            assert from_url.call_count == 1
