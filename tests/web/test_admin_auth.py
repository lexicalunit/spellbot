# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from aiohttp_session import Session
from cryptography.fernet import Fernet

from spellbot.web.api import admin_auth
from spellbot.web.api.admin_auth import (
    ADMIN_RECHECK_S,
    admin_auth_middleware,
    get_admin_user_xid,
    oauth_redirect_uri,
    resolve_session_key,
    start_admin_session,
    still_admin,
)
from tests.mocks.decoys import ANY
from tests.mocks.http import discord_oauth, raising, serve_httpx

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from aiohttp.test_utils import TestClient
    from decoy import Decoy

    from tests.fixtures import Stub

    WebClient = TestClient[web.Request, web.Application]

NOW = 1_800_000_000
OK = web.Response(text="ok")


@asynccontextmanager
async def no_session() -> AsyncGenerator[None]:
    """Stand in for `db_session_manager` where the database calls are stubbed out."""
    yield


class TestResolveSessionKey:
    def test_unset_generates_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(admin_auth.settings, "SESSION_SECRET_KEY", None)
        fernet = resolve_session_key()
        assert isinstance(fernet, Fernet)

    def test_valid_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        key = Fernet.generate_key().decode("utf-8")
        monkeypatch.setattr(admin_auth.settings, "SESSION_SECRET_KEY", f'  "{key}"  ')
        fernet = resolve_session_key()
        assert isinstance(fernet, Fernet)

    def test_invalid_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(admin_auth.settings, "SESSION_SECRET_KEY", "not-a-real-key")
        with pytest.raises(ValueError, match="SESSION_SECRET_KEY"):
            resolve_session_key()


class TestOauthRedirectUri:
    def test_strips_trailing_slash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(admin_auth.settings, "API_BASE_URL", "https://example.com/")
        assert oauth_redirect_uri() == "https://example.com/admin/oauth/callback"


@pytest.mark.asyncio
class TestGetAdminUserXid:
    async def test_no_xid_in_session(self, decoy: Decoy, stub: Stub) -> None:
        get_session_fake = stub(admin_auth, "get_session")
        decoy.when(await get_session_fake(ANY), ignore_extra_args=True).then_return({})
        assert await get_admin_user_xid(make_mocked_request("GET", "/")) is None

    async def test_non_int_xid(self, decoy: Decoy, stub: Stub) -> None:
        get_session_fake = stub(admin_auth, "get_session")
        decoy.when(await get_session_fake(ANY), ignore_extra_args=True).then_return(
            {"xid": "not-an-int"}
        )
        assert await get_admin_user_xid(make_mocked_request("GET", "/")) is None

    async def test_owner_is_not_rechecked(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(admin_auth.settings, "OWNER_XID", 42)
        get_session_fake = stub(admin_auth, "get_session")
        decoy.when(await get_session_fake(ANY), ignore_extra_args=True).then_return({"xid": 42})
        still_admin = stub(admin_auth, "still_admin")
        assert await get_admin_user_xid(make_mocked_request("GET", "/")) == 42
        decoy.verify(await still_admin(ANY), times=0, ignore_extra_args=True)

    async def test_recently_checked_admin_is_trusted(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(admin_auth.settings, "OWNER_XID", 1)
        session = {"xid": 42, "admin_checked_at": NOW - ADMIN_RECHECK_S + 1}
        get_session_fake = stub(admin_auth, "get_session")
        decoy.when(await get_session_fake(ANY), ignore_extra_args=True).then_return(session)
        time_fake = stub(admin_auth.time, "time")
        decoy.when(time_fake(), ignore_extra_args=True).then_return(NOW)
        still_admin = stub(admin_auth, "still_admin")
        assert await get_admin_user_xid(make_mocked_request("GET", "/")) == 42
        decoy.verify(await still_admin(ANY), times=0, ignore_extra_args=True)

    @pytest.mark.parametrize(
        "checked_at",
        [
            pytest.param(None, id="never"),
            pytest.param(NOW - ADMIN_RECHECK_S, id="stale"),
        ],
    )
    async def test_admin_is_rechecked(
        self,
        checked_at: int | None,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(admin_auth.settings, "OWNER_XID", 1)
        session: dict[str, Any] = {"xid": 42, "name": "admin"}
        if checked_at is not None:
            session["admin_checked_at"] = checked_at
        get_session_fake = stub(admin_auth, "get_session")
        decoy.when(await get_session_fake(ANY), ignore_extra_args=True).then_return(session)
        time_fake = stub(admin_auth.time, "time")
        decoy.when(time_fake(), ignore_extra_args=True).then_return(NOW)
        still_admin_fake = stub(admin_auth, "still_admin")
        decoy.when(await still_admin_fake(ANY), ignore_extra_args=True).then_return(True)
        assert await get_admin_user_xid(make_mocked_request("GET", "/")) == 42
        assert session == {"xid": 42, "name": "admin", "admin_checked_at": NOW}

    async def test_demoted_admin_loses_admin_keys(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(admin_auth.settings, "OWNER_XID", 1)
        session = {
            "xid": 42,
            "name": "admin",
            "admin_checked_at": NOW - ADMIN_RECHECK_S,
            "viewer_xid": 42,
        }
        get_session_fake = stub(admin_auth, "get_session")
        decoy.when(await get_session_fake(ANY), ignore_extra_args=True).then_return(session)
        time_fake = stub(admin_auth.time, "time")
        decoy.when(time_fake(), ignore_extra_args=True).then_return(NOW)
        still_admin_fake = stub(admin_auth, "still_admin")
        decoy.when(await still_admin_fake(ANY), ignore_extra_args=True).then_return(False)
        assert await get_admin_user_xid(make_mocked_request("GET", "/")) is None
        assert session == {"viewer_xid": 42}


@pytest.mark.asyncio
class TestStillAdmin:
    async def test_reuses_open_session(self, decoy: Decoy, stub: Stub) -> None:
        is_set_fake = stub(admin_auth.DatabaseSession, "is_set")
        decoy.when(is_set_fake(), ignore_extra_args=True).then_return(True)
        manager = stub(admin_auth, "db_session_manager")
        is_admin = stub(admin_auth.services.users, "is_admin")
        decoy.when(await is_admin(ANY), ignore_extra_args=True).then_return(True)
        assert await still_admin(42) is True
        decoy.verify(await is_admin(42), times=1)
        decoy.verify(manager(), times=0, ignore_extra_args=True)

    async def test_opens_session_when_none(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        is_set_fake = stub(admin_auth.DatabaseSession, "is_set")
        decoy.when(is_set_fake()).then_return(False)
        opened: list[bool] = []

        @asynccontextmanager
        async def session_manager() -> AsyncGenerator[None]:
            opened.append(True)
            yield

        monkeypatch.setattr(admin_auth, "db_session_manager", session_manager)
        is_admin_fake = stub(admin_auth.services.users, "is_admin")
        decoy.when(await is_admin_fake(42)).then_return(False)
        assert await still_admin(42) is False
        assert opened == [True]


class TestStartAdminSession:
    def test_start_admin_session(self, decoy: Decoy, stub: Stub) -> None:
        time_fake = stub(admin_auth.time, "time")
        decoy.when(time_fake(), ignore_extra_args=True).then_return(NOW + 0.5)
        session = Session(None, data=None, new=True)
        start_admin_session(session, 42, "admin")
        assert dict(session) == {"xid": 42, "name": "admin", "admin_checked_at": NOW}


@pytest.mark.asyncio
class TestAdminAuthMiddleware:
    async def test_non_admin_path_passes_through(self, decoy: Decoy) -> None:
        request = make_mocked_request("GET", "/something/else")
        handler = decoy.mock(name="handler", is_async=True)
        decoy.when(await handler(request)).then_return(OK)
        assert await admin_auth_middleware(request, handler) is OK

    async def test_public_admin_path_passes_through(self, decoy: Decoy) -> None:
        request = make_mocked_request("GET", "/admin/login")
        handler = decoy.mock(name="handler", is_async=True)
        decoy.when(await handler(request)).then_return(OK)
        assert await admin_auth_middleware(request, handler) is OK

    async def test_unauthenticated_admin_path_redirects(self, decoy: Decoy, stub: Stub) -> None:
        request = make_mocked_request("GET", "/admin/dashboard")
        get_admin_user_xid_fake = stub(admin_auth, "get_admin_user_xid")
        decoy.when(await get_admin_user_xid_fake(ANY), ignore_extra_args=True).then_return(None)
        handler = decoy.mock(name="handler", is_async=True)
        resp = await admin_auth_middleware(request, handler)
        assert resp.status == 302
        assert resp.headers["Location"] == "/admin/login"
        decoy.verify(await handler(request), times=0)

    async def test_authenticated_admin_path_passes_through(self, decoy: Decoy, stub: Stub) -> None:
        request = make_mocked_request("GET", "/admin/dashboard")
        get_admin_user_xid_fake = stub(admin_auth, "get_admin_user_xid")
        decoy.when(await get_admin_user_xid_fake(ANY), ignore_extra_args=True).then_return(42)
        handler = decoy.mock(name="handler", is_async=True)
        decoy.when(await handler(request)).then_return(OK)
        assert await admin_auth_middleware(request, handler) is OK

    async def test_bare_admin_path_requires_auth(self, decoy: Decoy, stub: Stub) -> None:
        request = make_mocked_request("GET", "/admin")
        get_admin_user_xid_fake = stub(admin_auth, "get_admin_user_xid")
        decoy.when(await get_admin_user_xid_fake(ANY), ignore_extra_args=True).then_return(None)
        resp = await admin_auth_middleware(request, decoy.mock(name="handler", is_async=True))
        assert resp.status == 302


@pytest.mark.asyncio
class TestAdminLogin:
    async def test_unconfigured(self, client: WebClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(admin_auth.settings, "BOT_APPLICATION_ID", None)
        monkeypatch.setattr(admin_auth.settings, "BOT_CLIENT_SECRET", None)
        resp = await client.get("/admin/login")
        assert resp.status == 503
        assert resp.content_type == "text/html"
        text = await resp.text()
        assert "Sign-in isn't set up here" in text
        assert "<code>BOT_APPLICATION_ID</code>" in text
        assert "<code>BOT_CLIENT_SECRET</code>" in text

    async def test_unconfigured_lists_only_missing(
        self,
        client: WebClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(admin_auth.settings, "BOT_APPLICATION_ID", "appid-1")
        monkeypatch.setattr(admin_auth.settings, "BOT_CLIENT_SECRET", None)
        resp = await client.get("/admin/login")
        assert resp.status == 503
        text = await resp.text()
        assert "<code>BOT_APPLICATION_ID</code>" not in text
        assert "<code>BOT_CLIENT_SECRET</code>" in text

    async def test_redirects_to_discord(
        self,
        client: WebClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(admin_auth.settings, "BOT_APPLICATION_ID", "appid-1")
        monkeypatch.setattr(admin_auth.settings, "BOT_CLIENT_SECRET", "secret-1")
        # Match the test client's host so `canonical_host_redirect` is a no-op.
        monkeypatch.setattr(admin_auth.settings, "API_BASE_URL", "http://127.0.0.1")
        resp = await client.get("/admin/login", allow_redirects=False)
        assert resp.status == 302
        loc = resp.headers["Location"]
        assert loc.startswith(admin_auth.DISCORD_AUTHORIZE_URL)
        params = parse_qs(urlparse(loc).query)
        assert params["client_id"] == ["appid-1"]
        assert params["response_type"] == ["code"]
        assert params["scope"] == ["identify"]
        assert params["redirect_uri"] == ["http://127.0.0.1/admin/oauth/callback"]

    async def test_redirects_to_canonical_host_when_on_vanity_alias(
        self,
        client: WebClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(admin_auth.settings, "BOT_APPLICATION_ID", "appid-1")
        monkeypatch.setattr(admin_auth.settings, "BOT_CLIENT_SECRET", "secret-1")
        monkeypatch.setattr(admin_auth.settings, "API_BASE_URL", "https://prod.app.spellbot.io")
        resp = await client.get("/admin/login?next=/admin/dashboard", allow_redirects=False)
        assert resp.status == 302
        assert (
            resp.headers["Location"]
            == "https://prod.app.spellbot.io/admin/login?next=/admin/dashboard"
        )


async def configure_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_auth.settings, "BOT_APPLICATION_ID", "appid-1")
    monkeypatch.setattr(admin_auth.settings, "BOT_CLIENT_SECRET", "secret-1")
    monkeypatch.setattr(admin_auth.settings, "API_BASE_URL", "http://127.0.0.1")
    monkeypatch.setattr(admin_auth.settings, "OWNER_XID", 42)


async def start_login(client: WebClient) -> str:
    """Hit /admin/login and return the oauth state from the redirect URL."""
    resp = await client.get("/admin/login", allow_redirects=False)
    assert resp.status == 302
    params = parse_qs(urlparse(resp.headers["Location"]).query)
    return params["state"][0]


@pytest.mark.asyncio
class TestAdminOauthCallback:
    async def test_unconfigured(self, client: WebClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(admin_auth.settings, "BOT_APPLICATION_ID", None)
        monkeypatch.setattr(admin_auth.settings, "BOT_CLIENT_SECRET", None)
        resp = await client.get("/admin/oauth/callback")
        assert resp.status == 503

    async def test_missing_state(self, client: WebClient, monkeypatch: pytest.MonkeyPatch) -> None:
        await configure_admin(monkeypatch)
        resp = await client.get("/admin/oauth/callback?code=abc")
        assert resp.status == 400

    async def test_state_mismatch(self, client: WebClient, monkeypatch: pytest.MonkeyPatch) -> None:
        await configure_admin(monkeypatch)
        await start_login(client)
        resp = await client.get("/admin/oauth/callback?code=abc&state=wrong")
        assert resp.status == 400

    async def test_token_exchange_fails(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_admin(monkeypatch)
        state = await start_login(client)
        serve_httpx(monkeypatch, discord_oauth(token_status=400))
        resp = await client.get(f"/admin/oauth/callback?code=abc&state={state}")
        assert resp.status == 401

    async def test_identify_fails(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_admin(monkeypatch)
        state = await start_login(client)
        serve_httpx(monkeypatch, discord_oauth(identify_status=500))
        resp = await client.get(f"/admin/oauth/callback?code=abc&state={state}")
        assert resp.status == 401

    async def test_http_error(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_admin(monkeypatch)
        state = await start_login(client)
        serve_httpx(monkeypatch, raising())
        resp = await client.get(f"/admin/oauth/callback?code=abc&state={state}")
        assert resp.status == 502

    async def test_bad_user_payload(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_admin(monkeypatch)
        state = await start_login(client)
        serve_httpx(monkeypatch, discord_oauth(identify_json={"no_id": True}))
        resp = await client.get(f"/admin/oauth/callback?code=abc&state={state}")
        assert resp.status == 401

    async def test_unauthorized_xid(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_admin(monkeypatch)
        state = await start_login(client)
        serve_httpx(monkeypatch, discord_oauth(identify_json={"id": "999", "username": "x"}))
        monkeypatch.setattr(admin_auth, "db_session_manager", no_session)
        is_admin_fake = stub(admin_auth.services.users, "is_admin")
        decoy.when(await is_admin_fake(ANY), ignore_extra_args=True).then_return(False)
        resp = await client.get(f"/admin/oauth/callback?code=abc&state={state}")
        assert resp.status == 403

    async def test_promoted_xid_authorized(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_admin(monkeypatch)
        state = await start_login(client)
        serve_httpx(monkeypatch, discord_oauth(identify_json={"id": "777", "username": "promoted"}))
        monkeypatch.setattr(admin_auth, "db_session_manager", no_session)
        is_admin_fake = stub(admin_auth.services.users, "is_admin")
        decoy.when(await is_admin_fake(ANY), ignore_extra_args=True).then_return(True)
        resp = await client.get(
            f"/admin/oauth/callback?code=abc&state={state}",
            allow_redirects=False,
        )
        assert resp.status == 302
        assert resp.headers["Location"] == "/admin/dashboard"

    async def test_success(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_admin(monkeypatch)
        state = await start_login(client)
        serve_httpx(
            monkeypatch,
            discord_oauth(identify_json={"id": "42", "global_name": "Amy", "username": "u"}),
        )
        resp = await client.get(
            f"/admin/oauth/callback?code=abc&state={state}",
            allow_redirects=False,
        )
        assert resp.status == 302
        assert resp.headers["Location"] == "/admin/dashboard"

    async def test_success_fallback_username(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_admin(monkeypatch)
        state = await start_login(client)
        serve_httpx(monkeypatch, discord_oauth(identify_json={"id": "42", "username": "fallback"}))
        resp = await client.get(
            f"/admin/oauth/callback?code=abc&state={state}",
            allow_redirects=False,
        )
        assert resp.status == 302


@pytest.mark.asyncio
class TestAdminLogout:
    async def test_logout_clears_session(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_admin(monkeypatch)
        state = await start_login(client)
        serve_httpx(monkeypatch, discord_oauth(identify_json={"id": "42", "username": "u"}))
        await client.get(
            f"/admin/oauth/callback?code=abc&state={state}",
            allow_redirects=False,
        )
        resp = await client.post("/admin/logout", allow_redirects=False)
        assert resp.status == 302
        # Redirect carries `logged_out=1` so `/admin/login` shows the signed-out
        # landing instead of auto-bouncing back through Discord's still-valid grant.
        assert resp.headers["Location"] == "/admin/login?logged_out=1"

    async def test_logged_out_landing_does_not_start_oauth(
        self,
        client: WebClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_admin(monkeypatch)
        resp = await client.get("/admin/login?logged_out=1", allow_redirects=False)
        assert resp.status == 200
        body = await resp.text()
        assert "You've been signed out" in body
        # The manual sign-in link is present, but no automatic OAuth redirect.
        assert 'href="/admin/login"' in body
        assert admin_auth.DISCORD_AUTHORIZE_URL not in body
