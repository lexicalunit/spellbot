from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from spellbot import dm_limiter
from spellbot.dm_limiter import (
    threshold_for,
    try_consume_dm_slot,
    window_key_for,
)
from spellbot.settings import settings


@pytest.mark.asyncio
class TestThresholdFor:
    async def test_start_uses_window_limit(self) -> None:
        assert threshold_for("start") == settings.DM_WINDOW_LIMIT

    async def test_notification_uses_notification_budget(self) -> None:
        assert threshold_for("notification") == settings.DM_NOTIFICATION_BUDGET


@pytest.mark.asyncio
class TestTryConsumeDmSlot:
    async def test_start_always_allowed_without_redis(self) -> None:
        with patch.object(settings, "REDIS_URL", None):
            assert await try_consume_dm_slot("start") is True

    async def test_no_redis_url_blocks_notification(self) -> None:
        with patch.object(settings, "REDIS_URL", None):
            assert await try_consume_dm_slot("notification") is False

    async def test_start_bypasses_redis(self) -> None:
        fake_redis = AsyncMock()
        fake_redis.eval = AsyncMock(return_value=0)
        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch.object(dm_limiter, "get_redis", AsyncMock(return_value=fake_redis)),
        ):
            assert await try_consume_dm_slot("start") is True
        fake_redis.eval.assert_not_called()

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
            assert await try_consume_dm_slot("notification") is True
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

    async def test_uses_notification_threshold(self) -> None:
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
            await try_consume_dm_slot("notification")

        assert captured == [settings.DM_NOTIFICATION_BUDGET]

    async def test_uses_notification_redis_key(self) -> None:
        captured: list[str] = []

        async def fake_eval(*args: object, **_: object) -> int:
            captured.append(str(args[2]))
            return 1

        fake_redis = AsyncMock()
        fake_redis.eval = fake_eval
        with (
            patch.object(settings, "REDIS_URL", "redis://localhost"),
            patch.object(dm_limiter, "get_redis", AsyncMock(return_value=fake_redis)),
        ):
            await try_consume_dm_slot("notification")

        assert captured == [window_key_for("notification")]


@pytest.mark.asyncio
class TestWindowKeyFor:
    async def test_start_and_notification_keys_differ(self) -> None:
        assert window_key_for("start") != window_key_for("notification")

    async def test_keys_use_expected_prefix(self) -> None:
        assert window_key_for("start") == "dm:window:start"
        assert window_key_for("notification") == "dm:window:notification"
