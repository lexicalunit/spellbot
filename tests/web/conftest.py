# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import pytest
import pytest_asyncio

from spellbot.settings import settings as runtime_settings
from spellbot.web import builder
from spellbot.web.api import admin_auth, record
from tests.mocks.http import discord_oauth, serve_httpx

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from aiohttp.client import ClientSession


@pytest.fixture(autouse=True)
def disable_rate_limit_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Disable the Redis-backed rate limiter so web tests never touch a real Redis.

    The local `.env` points `REDIS_URL` at a developer Redis, and the test runner's
    `--allow-hosts=127.0.0.1` lets connections to it through. With it set,
    `auth_middleware` would issue real `INCR` calls keyed by the (shared) client IP,
    so unauthorized requests accumulate across tests and eventually return a genuine
    429. Forcing `REDIS_URL` to `None` makes `rate_limited` a no-op. Tests that need
    rate limiting mock `rate_limited` (or `REDIS_URL`) directly.
    """
    monkeypatch.setattr(runtime_settings, "REDIS_URL", None)


@pytest.fixture(autouse=True)
def pin_csp_nonce(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the per-request CSP nonce so rendered pages, and their HTML snapshots, are stable."""
    monkeypatch.setattr(builder, "new_csp_nonce", lambda: "test-nonce")


@pytest.fixture(autouse=True)
def block_external_moderation(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Default web page/endpoint handlers to a non-moderator viewer.

    The guild and channel handlers resolve moderator status via the Discord REST API
    (`viewer_is_moderator`). Without this, any test that renders those pages with an
    authenticated session (e.g. `owner_client`) would make a real network call. Tests
    that need a moderator override this with `mod_client` or an explicit patch; the
    real resolver is exercised directly in `test_moderation.py`.
    """
    monkeypatch.setattr(record, "viewer_is_moderator", moderator_check(is_moderator=False))


def moderator_check(*, is_moderator: bool) -> Callable[[int, int], Awaitable[bool]]:
    """Stand in for `record.viewer_is_moderator`, answering the same for every guild."""

    async def check(viewer_xid: int, guild_xid: int) -> bool:
        return is_moderator

    return check


@pytest.fixture(autouse=True)
def configure_oauth_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Pin the Discord OAuth credentials so login state is deterministic across environments.

    The shared site header shows a "Log in" control only when `BOT_APPLICATION_ID` and
    `BOT_CLIENT_SECRET` are set (`login_enabled`). A developer's local `.env` provides
    them but CI does not, so rendered pages — and their HTML snapshots — would otherwise
    differ between the two. Pinning both to fixed test values keeps every page render (and
    every snapshot) stable. Tests that exercise the "not configured" path patch them back
    to `None` themselves.
    """
    monkeypatch.setattr(runtime_settings, "BOT_APPLICATION_ID", "appid-1")
    monkeypatch.setattr(runtime_settings, "BOT_CLIENT_SECRET", "secret-1")


@pytest_asyncio.fixture
async def owner_client(client: ClientSession, monkeypatch: pytest.MonkeyPatch) -> ClientSession:
    """Return a client whose cookie jar holds an authenticated owner session."""
    monkeypatch.setattr(admin_auth.settings, "BOT_APPLICATION_ID", "appid-1")
    monkeypatch.setattr(admin_auth.settings, "BOT_CLIENT_SECRET", "secret-1")
    monkeypatch.setattr(admin_auth.settings, "API_BASE_URL", "http://127.0.0.1")
    monkeypatch.setattr(admin_auth.settings, "OWNER_XID", 42)
    login_resp = await client.get("/admin/login", allow_redirects=False)
    state = parse_qs(urlparse(login_resp.headers["Location"]).query)["state"][0]
    serve_httpx(monkeypatch, discord_oauth(identify_json={"id": "42", "username": "owner"}))
    cb = await client.get(
        f"/admin/oauth/callback?code=abc&state={state}",
        allow_redirects=False,
    )
    assert cb.status == 302
    return client


@pytest_asyncio.fixture
async def mod_client(
    owner_client: ClientSession,
    monkeypatch: pytest.MonkeyPatch,
) -> ClientSession:
    """Return a logged-in client whose viewer moderates every guild."""
    monkeypatch.setattr(record, "viewer_is_moderator", moderator_check(is_moderator=True))
    return owner_client
