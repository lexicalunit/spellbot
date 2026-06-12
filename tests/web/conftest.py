from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
import pytest_asyncio

from spellbot.settings import settings as runtime_settings
from spellbot.web.api import admin_auth

if TYPE_CHECKING:
    from aiohttp.client import ClientSession
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


def make_owner_httpx_client() -> MagicMock:
    """Mock `httpx.AsyncClient` for an OAuth flow identifying the owner (xid=42)."""
    inner = MagicMock()
    token_resp = MagicMock(status_code=200)
    token_resp.json = MagicMock(return_value={"access_token": "tok"})
    inner.post = AsyncMock(return_value=token_resp)
    identify_resp = MagicMock(status_code=200)
    identify_resp.json = MagicMock(return_value={"id": "42", "username": "owner"})
    inner.get = AsyncMock(return_value=identify_resp)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=inner)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest_asyncio.fixture
async def owner_client(client: ClientSession, mocker: MockerFixture) -> ClientSession:
    """Return a client whose cookie jar holds an authenticated owner session."""
    mocker.patch.object(admin_auth.settings, "BOT_APPLICATION_ID", "appid-1")
    mocker.patch.object(admin_auth.settings, "BOT_CLIENT_SECRET", "secret-1")
    mocker.patch.object(admin_auth.settings, "API_BASE_URL", "http://127.0.0.1")
    mocker.patch.object(admin_auth.settings, "OWNER_XID", 42)
    login_resp = await client.get("/admin/login", allow_redirects=False)
    state = parse_qs(urlparse(login_resp.headers["Location"]).query)["state"][0]
    mocker.patch(
        "spellbot.web.api.admin_auth.httpx.AsyncClient",
        return_value=make_owner_httpx_client(),
    )
    cb = await client.get(
        f"/admin/oauth/callback?code=abc&state={state}",
        allow_redirects=False,
    )
    assert cb.status == 302
    return client


@pytest_asyncio.fixture
async def mod_client(owner_client: ClientSession, mocker: MockerFixture) -> ClientSession:
    """Return a logged-in client whose viewer moderates every guild."""
    mocker.patch(
        "spellbot.web.api.record.viewer_is_moderator",
        AsyncMock(return_value=True),
    )
    return owner_client
