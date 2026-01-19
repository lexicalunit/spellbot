from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from spellbot.web.tools import rate_limited


@pytest.mark.asyncio
class TestRateLimited:
    async def test_no_redis_url(self) -> None:
        """Test that rate limiting is disabled when Redis URL is not configured."""
        request = MagicMock()
        with patch("spellbot.web.tools.settings") as mock_settings:
            mock_settings.REDIS_URL = None
            result = await rate_limited(request)
            assert result is False

    async def test_under_rate_limit(self) -> None:
        """Test request under rate limit."""
        request = MagicMock()
        request.remote = "192.168.1.1"

        mock_redis = AsyncMock()
        mock_redis.eval = AsyncMock(return_value="5")

        with (
            patch("spellbot.web.tools.settings") as mock_settings,
            patch("spellbot.web.tools.aioredis.from_url", AsyncMock(return_value=mock_redis)),
        ):
            mock_settings.REDIS_URL = "redis://localhost"
            result = await rate_limited(request)
            assert result is False

    async def test_over_rate_limit(self) -> None:
        """Test request over rate limit."""
        request = MagicMock()
        request.remote = "192.168.1.1"

        mock_redis = AsyncMock()
        mock_redis.eval = AsyncMock(return_value="15")  # Over RATE_LIMIT of 10

        with (
            patch("spellbot.web.tools.settings") as mock_settings,
            patch("spellbot.web.tools.aioredis.from_url", AsyncMock(return_value=mock_redis)),
        ):
            mock_settings.REDIS_URL = "redis://localhost"
            result = await rate_limited(request)
            assert result is True

    async def test_with_custom_key(self) -> None:
        """Test rate limiting with custom key."""
        request = MagicMock()
        request.remote = "192.168.1.1"

        mock_redis = AsyncMock()
        mock_redis.eval = AsyncMock(return_value="3")

        with (
            patch("spellbot.web.tools.settings") as mock_settings,
            patch("spellbot.web.tools.aioredis.from_url", AsyncMock(return_value=mock_redis)),
        ):
            mock_settings.REDIS_URL = "redis://localhost"
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
            patch("spellbot.web.tools.settings") as mock_settings,
            patch("spellbot.web.tools.aioredis.from_url", AsyncMock(return_value=mock_redis)),
        ):
            mock_settings.REDIS_URL = "redis://localhost"
            result = await rate_limited(request)
            # Should return False on error (fail open)
            assert result is False
