# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import pytest

from spellbot.dm_limiter import (
    DM_LIMIT_SCRIPT,
    threshold_for,
    try_consume_dm_slot,
    window_key_for,
)
from spellbot.settings import settings
from tests.mocks.redis import FakeRedis, serve_redis


@pytest.mark.asyncio
class TestThresholdFor:
    async def test_start_uses_window_limit(self) -> None:
        assert threshold_for("start") == settings.DM_WINDOW_LIMIT

    async def test_notification_uses_notification_budget(self) -> None:
        assert threshold_for("notification") == settings.DM_NOTIFICATION_BUDGET


@pytest.mark.asyncio
class TestTryConsumeDmSlot:
    async def test_start_always_allowed_without_redis(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "REDIS_URL", None)
        assert await try_consume_dm_slot("start") is True

    async def test_no_redis_url_blocks_notification(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "REDIS_URL", None)
        assert await try_consume_dm_slot("notification") is False

    async def test_start_bypasses_redis(self, monkeypatch: pytest.MonkeyPatch) -> None:
        redis = FakeRedis(eval_result=0)
        serve_redis(monkeypatch, redis)
        assert await try_consume_dm_slot("start") is True
        assert redis.evals == []

    async def test_redis_error_fails_closed_for_notification(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        serve_redis(monkeypatch, RuntimeError("down"))
        assert await try_consume_dm_slot("notification") is False

    async def test_returns_true_when_script_allows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        redis = FakeRedis(eval_result=1)
        serve_redis(monkeypatch, redis)
        assert await try_consume_dm_slot("notification") is True
        assert len(redis.evals) == 1

    async def test_returns_false_when_script_denies(self, monkeypatch: pytest.MonkeyPatch) -> None:
        serve_redis(monkeypatch, FakeRedis(eval_result=0))
        assert await try_consume_dm_slot("notification") is False

    async def test_zero_threshold_short_circuits_to_false(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "REDIS_URL", "redis://localhost")
        monkeypatch.setattr(settings, "DM_NOTIFICATION_BUDGET", 0)
        assert await try_consume_dm_slot("notification") is False

    async def test_runs_the_script_on_the_notification_window(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        redis = FakeRedis()
        serve_redis(monkeypatch, redis)
        await try_consume_dm_slot("notification")

        [(script, numkeys, key, _window, _now, threshold, _member)] = redis.evals
        assert (script, numkeys) == (DM_LIMIT_SCRIPT, 1)
        assert key == window_key_for("notification")
        assert threshold == str(settings.DM_NOTIFICATION_BUDGET)


@pytest.mark.asyncio
class TestWindowKeyFor:
    async def test_start_and_notification_keys_differ(self) -> None:
        assert window_key_for("start") != window_key_for("notification")

    async def test_keys_use_expected_prefix(self) -> None:
        assert window_key_for("start") == "dm:window:start"
        assert window_key_for("notification") == "dm:window:notification"
