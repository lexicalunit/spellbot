from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from spellbot.settings import settings as runtime_settings

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture(autouse=True)
def disable_rate_limit_redis(mocker: MockerFixture) -> None:
    """
    Disable the Redis-backed rate limiter so web tests never touch a real Redis.

    The local `.env` points `REDIS_URL` at a developer Redis, and the test runner's
    `--allow-hosts=127.0.0.1` lets connections to it through. With it set,
    `auth_middleware` would issue real `INCR` calls keyed by the (shared) client IP,
    so unauthorized requests accumulate across tests and eventually return a genuine
    429. Forcing `REDIS_URL` to `None` makes `rate_limited` a no-op. Tests that need
    rate limiting mock `rate_limited` (or `REDIS_URL`) directly.
    """
    mocker.patch.object(runtime_settings, "REDIS_URL", None)


@pytest.fixture(autouse=True)
def block_external_moderation(mocker: MockerFixture) -> None:
    """
    Default web page/endpoint handlers to a non-moderator viewer.

    The guild and channel handlers resolve moderator status via the Discord REST API
    (`viewer_is_moderator`). Without this, any test that renders those pages with an
    authenticated session (e.g. `owner_client`) would make a real network call. Tests
    that need a moderator override this with `mod_client` or an explicit patch; the
    real resolver is exercised directly in `test_moderation.py`.
    """
    mocker.patch(
        "spellbot.web.api.record.viewer_is_moderator",
        AsyncMock(return_value=False),
    )
