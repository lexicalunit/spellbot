from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from spellbot import dm_limiter
from spellbot.dm_limiter import current_dm_count, threshold_for, try_consume_dm_slot
from spellbot.settings import settings


@pytest.mark.asyncio
class TestThresholdFor:
    async def test_start_uses_window_limit(self) -> None:
        assert threshold_for("start") == settings.DM_WINDOW_LIMIT

    async def test_notification_uses_notification_budget(self) -> None:
        assert threshold_for("notification") == settings.DM_NOTIFICATION_BUDGET


@pytest.mark.asyncio
class TestTryConsumeDmSlot:
    async def test_no_redis_url_allows_start(self) -> None:
        with patch.object(settings, "REDIS_URL", None):
            assert await try_consume_dm_slot("start") is True

    async def test_no_redis_url_blocks_notification(self) -> None:
        with patch.object(settings, "REDIS_URL", None):
            assert await try_consume_dm_slot("notification") is False

    async def test_redis_error_fails_open_for_start(self) -> None:
        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch.object(dm_limiter, "get_redis", AsyncMock(side_effect=RuntimeError("down"))),
        ):
            assert await try_consume_dm_slot("start") is True

    async def test_redis_error_fails_closed_for_notification(self) -> None:
        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch.object(dm_limiter, "get_redis", AsyncMock(side_effect=RuntimeError("down"))),
        ):
            assert await try_consume_dm_slot("notification") is False

    async def test_returns_true_when_script_allows(self) -> None:
        fake_redis = AsyncMock()
        fake_redis.eval = AsyncMock(return_value=1)
        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch.object(dm_limiter, "get_redis", AsyncMock(return_value=fake_redis)),
        ):
            assert await try_consume_dm_slot("start") is True
        fake_redis.eval.assert_awaited_once()

    async def test_returns_false_when_script_denies(self) -> None:
        fake_redis = AsyncMock()
        fake_redis.eval = AsyncMock(return_value=0)
        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch.object(dm_limiter, "get_redis", AsyncMock(return_value=fake_redis)),
        ):
            assert await try_consume_dm_slot("notification") is False

    async def test_zero_threshold_short_circuits_to_false(self) -> None:
        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch.object(settings, "DM_NOTIFICATION_BUDGET", 0),
        ):
            assert await try_consume_dm_slot("notification") is False

    async def test_uses_correct_threshold_per_kind(self) -> None:
        captured: list[int] = []

        async def fake_eval(*args: object, **_: object) -> int:
            captured.append(int(str(args[5])))
            return 1

        fake_redis = AsyncMock()
        fake_redis.eval = fake_eval
        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch.object(dm_limiter, "get_redis", AsyncMock(return_value=fake_redis)),
        ):
            await try_consume_dm_slot("start")
            await try_consume_dm_slot("notification")

        assert captured == [settings.DM_WINDOW_LIMIT, settings.DM_NOTIFICATION_BUDGET]


@pytest.mark.asyncio
class TestCurrentDmCount:
    async def test_no_redis_returns_zero(self) -> None:
        with patch.object(settings, "REDIS_URL", None):
            assert await current_dm_count() == 0

    async def test_redis_error_returns_zero(self) -> None:
        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch.object(dm_limiter, "get_redis", AsyncMock(side_effect=RuntimeError("down"))),
        ):
            assert await current_dm_count() == 0

    async def test_returns_zcard_value(self) -> None:
        fake_redis = AsyncMock()
        fake_redis.zremrangebyscore = AsyncMock(return_value=0)
        fake_redis.zcard = AsyncMock(return_value=42)
        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch.object(dm_limiter, "get_redis", AsyncMock(return_value=fake_redis)),
        ):
            assert await current_dm_count() == 42
