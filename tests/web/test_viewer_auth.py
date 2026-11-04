# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from aiohttp_session import Session
from yarl import URL

from spellbot.services import users
from spellbot.web.api import oauth, viewer_auth
from spellbot.web.api.admin_auth import ADMIN_NAME_KEY, ADMIN_XID_KEY
from spellbot.web.api.oauth import DISCORD_AUTHORIZE_URL, canonical_host_redirect
from spellbot.web.api.viewer_auth import (
    VIEWER_NAME_KEY,
    VIEWER_XID_KEY,
    get_viewer,
    has_viewer_session,
    viewer_oauth_redirect_uri,
)
from tests.mocks.decoys import ANY
from tests.mocks.http import discord_oauth, raising, serve_httpx

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from aiohttp.test_utils import TestClient
    from decoy import Decoy

    from tests.fixtures import Stub

    WebClient = TestClient[web.Request, web.Application]


class TestViewerOauthRedirectUri:
    def test_strips_trailing_slash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(viewer_auth.settings, "API_BASE_URL", "https://example.com/")
        assert viewer_oauth_redirect_uri() == "https://example.com/queues/oauth/callback"


class TestCanonicalHostRedirect:
    @staticmethod
    def make_request(decoy: Decoy, host: str, rel_url: str) -> web.Request:
        # A decoy rather than `make_mocked_request`, which would normalize away the
        # malformed targets these tests feed in; `encoded=True` keeps them verbatim.
        request = decoy.mock(cls=web.Request)
        decoy.when(request.url).then_return(URL(f"http://{host}/"))
        decoy.when(request.rel_url).then_return(URL(rel_url, encoded=True))
        return request

    def test_returns_none_when_api_base_url_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(oauth.settings, "API_BASE_URL", None)
        assert canonical_host_redirect(make_mocked_request("GET", "/")) is None

    def test_returns_none_when_base_has_no_host(
        self,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
    ) -> None:
        monkeypatch.setattr(oauth.settings, "API_BASE_URL", "/no-host")
        assert (
            canonical_host_redirect(self.make_request(decoy, "alias.example.com", "/foo")) is None
        )

    def test_returns_none_when_host_already_matches(
        self,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
    ) -> None:
        monkeypatch.setattr(oauth.settings, "API_BASE_URL", "https://bot.spellbot.io")
        request = self.make_request(decoy, "bot.spellbot.io", "/queues?my=1")
        assert canonical_host_redirect(request) is None

    def test_redirects_to_canonical_host_with_path_and_query(
        self,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
    ) -> None:
        monkeypatch.setattr(oauth.settings, "API_BASE_URL", "https://bot.spellbot.io")
        request = self.make_request(decoy, "queues.spellbot.io", "/queues?my=1")
        resp = canonical_host_redirect(request)
        assert resp is not None
        assert resp.headers["Location"] == "https://bot.spellbot.io/queues?my=1"

    def test_rejects_target_with_scheme(
        self,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
    ) -> None:
        monkeypatch.setattr(oauth.settings, "API_BASE_URL", "https://bot.spellbot.io")
        request = self.make_request(decoy, "queues.spellbot.io", "https://evil.example.com/x")
        resp = canonical_host_redirect(request)
        assert resp is not None
        assert resp.headers["Location"] == "https://bot.spellbot.io/"

    def test_rejects_protocol_relative_target(
        self,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
    ) -> None:
        monkeypatch.setattr(oauth.settings, "API_BASE_URL", "https://bot.spellbot.io")
        request = self.make_request(decoy, "queues.spellbot.io", "//evil.example.com/x")
        resp = canonical_host_redirect(request)
        assert resp is not None
        assert resp.headers["Location"] == "https://bot.spellbot.io/"

    def test_rejects_backslash_protocol_relative_target(
        self,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
    ) -> None:
        monkeypatch.setattr(oauth.settings, "API_BASE_URL", "https://bot.spellbot.io")
        # Some browsers treat backslashes as forward slashes, so `/\evil.com`
        # would otherwise resolve to `//evil.com` (a host swap).
        request = self.make_request(decoy, "queues.spellbot.io", "/\\evil.example.com/x")
        resp = canonical_host_redirect(request)
        assert resp is not None
        assert resp.headers["Location"] == "https://bot.spellbot.io/"


class TestSafeRelativePath:
    def test_accepts_simple_path(self) -> None:
        assert oauth.safe_relative_path("/g/123") == "/g/123"

    def test_accepts_path_with_query(self) -> None:
        assert oauth.safe_relative_path("/g/1/c/2?page=3") == "/g/1/c/2?page=3"

    def test_rejects_none_and_empty(self) -> None:
        assert oauth.safe_relative_path(None) is None
        assert oauth.safe_relative_path("") is None

    def test_rejects_absolute_url(self) -> None:
        assert oauth.safe_relative_path("https://evil.example/x") is None

    def test_rejects_protocol_relative(self) -> None:
        assert oauth.safe_relative_path("//evil.example/x") is None

    def test_rejects_backslash_protocol_relative(self) -> None:
        assert oauth.safe_relative_path("/\\evil.example/x") is None

    def test_rejects_non_rooted_path(self) -> None:
        assert oauth.safe_relative_path("g/123") is None

    def test_rejects_embedded_newline_protocol_relative(self) -> None:
        # The leading-slash gate sees `/<newline>...`, but urlparse strips the
        # control character, collapsing it to `//evil.example` with a netloc.
        assert oauth.safe_relative_path("/\n/evil.example/x") is None


@pytest.mark.asyncio
class TestGetViewer:
    async def test_empty_session(self, decoy: Decoy, stub: Stub) -> None:
        get_session_fake = stub(viewer_auth, "get_session")
        decoy.when(await get_session_fake(ANY), ignore_extra_args=True).then_return({})
        assert await get_viewer(make_mocked_request("GET", "/")) == (None, None)

    async def test_non_int_xid(self, decoy: Decoy, stub: Stub) -> None:
        get_session_fake = stub(viewer_auth, "get_session")
        decoy.when(await get_session_fake(ANY), ignore_extra_args=True).then_return(
            {VIEWER_XID_KEY: "nope"}
        )
        assert await get_viewer(make_mocked_request("GET", "/")) == (None, None)

    async def test_valid_xid_with_name(self, decoy: Decoy, stub: Stub) -> None:
        get_session_fake = stub(viewer_auth, "get_session")
        decoy.when(await get_session_fake(ANY), ignore_extra_args=True).then_return(
            {VIEWER_XID_KEY: 7, VIEWER_NAME_KEY: "Amy"}
        )
        assert await get_viewer(make_mocked_request("GET", "/")) == (7, "Amy")

    async def test_valid_xid_no_name(self, decoy: Decoy, stub: Stub) -> None:
        get_session_fake = stub(viewer_auth, "get_session")
        decoy.when(await get_session_fake(ANY), ignore_extra_args=True).then_return(
            {VIEWER_XID_KEY: 7, VIEWER_NAME_KEY: 123}
        )
        assert await get_viewer(make_mocked_request("GET", "/")) == (7, None)

    async def test_falls_back_to_admin_session(self, decoy: Decoy, stub: Stub) -> None:
        # An admin session (no viewer keys) is honored as a viewer identity.
        get_session_fake = stub(viewer_auth, "get_session")
        decoy.when(await get_session_fake(ANY), ignore_extra_args=True).then_return(
            {ADMIN_XID_KEY: 9, ADMIN_NAME_KEY: "Boss"}
        )
        assert await get_viewer(make_mocked_request("GET", "/")) == (9, "Boss")

    async def test_admin_fallback_non_str_name(self, decoy: Decoy, stub: Stub) -> None:
        get_session_fake = stub(viewer_auth, "get_session")
        decoy.when(await get_session_fake(ANY), ignore_extra_args=True).then_return(
            {ADMIN_XID_KEY: 9, ADMIN_NAME_KEY: 123}
        )
        assert await get_viewer(make_mocked_request("GET", "/")) == (9, None)

    async def test_viewer_session_takes_precedence_over_admin(
        self,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        get_session_fake = stub(viewer_auth, "get_session")
        decoy.when(await get_session_fake(ANY), ignore_extra_args=True).then_return(
            {
                VIEWER_XID_KEY: 7,
                VIEWER_NAME_KEY: "Amy",
                ADMIN_XID_KEY: 9,
                ADMIN_NAME_KEY: "Boss",
            }
        )
        assert await get_viewer(make_mocked_request("GET", "/")) == (7, "Amy")

    async def test_admin_fallback_non_int_xid(self, decoy: Decoy, stub: Stub) -> None:
        get_session_fake = stub(viewer_auth, "get_session")
        decoy.when(await get_session_fake(ANY), ignore_extra_args=True).then_return(
            {ADMIN_XID_KEY: "nope"}
        )
        assert await get_viewer(make_mocked_request("GET", "/")) == (None, None)


@pytest.mark.asyncio
class TestHasViewerSession:
    async def test_true_with_viewer_key(self, decoy: Decoy, stub: Stub) -> None:
        get_session_fake = stub(viewer_auth, "get_session")
        decoy.when(await get_session_fake(ANY), ignore_extra_args=True).then_return(
            {VIEWER_XID_KEY: 7}
        )
        assert await has_viewer_session(make_mocked_request("GET", "/")) is True

    async def test_false_with_admin_key_only(self, decoy: Decoy, stub: Stub) -> None:
        get_session_fake = stub(viewer_auth, "get_session")
        decoy.when(await get_session_fake(ANY), ignore_extra_args=True).then_return(
            {ADMIN_XID_KEY: 9}
        )
        assert await has_viewer_session(make_mocked_request("GET", "/")) is False

    async def test_false_when_empty(self, decoy: Decoy, stub: Stub) -> None:
        get_session_fake = stub(viewer_auth, "get_session")
        decoy.when(await get_session_fake(ANY), ignore_extra_args=True).then_return({})
        assert await has_viewer_session(make_mocked_request("GET", "/")) is False


@contextlib.asynccontextmanager
async def noop_db_session() -> AsyncGenerator[None]:
    """Stand in for `db_session_manager` without opening a real database session."""
    yield


def blank_session() -> Session:
    """Build an empty session for exercising `grant_admin_if_authorized` directly."""
    return Session(None, data=None, new=True)


async def configure_viewer(decoy: Decoy, stub: Stub, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(viewer_auth.settings, "BOT_APPLICATION_ID", "appid-1")
    monkeypatch.setattr(viewer_auth.settings, "BOT_CLIENT_SECRET", "secret-1")
    # Must match the test client's host (127.0.0.1) so `canonical_host_redirect`
    # in `viewer_login` doesn't bounce the request away before issuing state.
    monkeypatch.setattr(viewer_auth.settings, "API_BASE_URL", "http://127.0.0.1")
    # The viewer callback now elevates owner/admin identities to a full admin session
    # (`grant_admin_if_authorized`), which consults the database for non-owners. Default
    # the flow to a non-admin identity and stub the DB session so the public-viewer path
    # never touches a real database. Tests that exercise elevation override these.
    monkeypatch.setattr(viewer_auth, "db_session_manager", noop_db_session)
    is_admin_fake = stub(users, "is_admin")
    decoy.when(await is_admin_fake(ANY), ignore_extra_args=True).then_return(False)


async def start_viewer_login(client: WebClient) -> str:
    resp = await client.get("/queues/login", allow_redirects=False)
    assert resp.status == 302
    return parse_qs(urlparse(resp.headers["Location"]).query)["state"][0]


@pytest.mark.asyncio
class TestViewerLogin:
    async def test_unconfigured(self, client: WebClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(viewer_auth.settings, "BOT_APPLICATION_ID", None)
        monkeypatch.setattr(viewer_auth.settings, "BOT_CLIENT_SECRET", None)
        resp = await client.get("/queues/login")
        assert resp.status == 503
        assert "Sign-in isn't set up here" in await resp.text()

    async def test_redirects_to_discord(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_viewer(decoy, stub, monkeypatch)
        resp = await client.get("/queues/login", allow_redirects=False)
        assert resp.status == 302
        loc = resp.headers["Location"]
        assert loc.startswith(DISCORD_AUTHORIZE_URL)
        params = parse_qs(urlparse(loc).query)
        assert params["client_id"] == ["appid-1"]
        assert params["scope"] == ["identify"]
        assert params["redirect_uri"] == ["http://127.0.0.1/queues/oauth/callback"]

    async def test_redirects_to_canonical_host_when_on_vanity_alias(
        self,
        client: WebClient,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        # Simulate the user arriving via a vanity hostname (e.g.
        # `queues.spellbot.io`). The session cookie set here would not be
        # visible on the canonical callback host, so the handler must bounce
        # the request to the canonical host before issuing OAuth state.
        await configure_viewer(decoy, stub, monkeypatch)
        monkeypatch.setattr(viewer_auth.settings, "API_BASE_URL", "https://prod.app.spellbot.io")
        resp = await client.get("/queues/login?foo=bar", allow_redirects=False)
        assert resp.status == 302
        assert resp.headers["Location"] == "https://prod.app.spellbot.io/queues/login?foo=bar"


@pytest.mark.asyncio
class TestViewerOauthCallback:
    async def test_unconfigured(self, client: WebClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(viewer_auth.settings, "BOT_APPLICATION_ID", None)
        monkeypatch.setattr(viewer_auth.settings, "BOT_CLIENT_SECRET", None)
        resp = await client.get("/queues/oauth/callback")
        assert resp.status == 503

    async def test_missing_state(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_viewer(decoy, stub, monkeypatch)
        resp = await client.get("/queues/oauth/callback?code=abc")
        assert resp.status == 400

    async def test_state_mismatch(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_viewer(decoy, stub, monkeypatch)
        await start_viewer_login(client)
        resp = await client.get("/queues/oauth/callback?code=abc&state=wrong")
        assert resp.status == 400

    async def test_token_exchange_fails(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_viewer(decoy, stub, monkeypatch)
        state = await start_viewer_login(client)
        serve_httpx(monkeypatch, discord_oauth(token_status=400))
        resp = await client.get(f"/queues/oauth/callback?code=abc&state={state}")
        assert resp.status == 401

    async def test_http_error(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_viewer(decoy, stub, monkeypatch)
        state = await start_viewer_login(client)
        serve_httpx(monkeypatch, raising())
        resp = await client.get(f"/queues/oauth/callback?code=abc&state={state}")
        assert resp.status == 502

    async def test_bad_user_payload(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_viewer(decoy, stub, monkeypatch)
        state = await start_viewer_login(client)
        serve_httpx(monkeypatch, discord_oauth(identify_json={"no_id": True}))
        resp = await client.get(f"/queues/oauth/callback?code=abc&state={state}")
        assert resp.status == 401

    async def test_success_redirects_to_queues_with_my(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_viewer(decoy, stub, monkeypatch)
        state = await start_viewer_login(client)
        serve_httpx(monkeypatch, discord_oauth(identify_json={"id": "42", "global_name": "Amy"}))
        resp = await client.get(
            f"/queues/oauth/callback?code=abc&state={state}",
            allow_redirects=False,
        )
        assert resp.status == 302
        assert resp.headers["Location"] == "/queues?my=1"

    async def test_success_redirects_to_safe_next(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_viewer(decoy, stub, monkeypatch)
        login = await client.get("/queues/login?next=/g/123", allow_redirects=False)
        state = parse_qs(urlparse(login.headers["Location"]).query)["state"][0]
        serve_httpx(monkeypatch, discord_oauth(identify_json={"id": "42", "username": "u"}))
        resp = await client.get(
            f"/queues/oauth/callback?code=abc&state={state}",
            allow_redirects=False,
        )
        assert resp.status == 302
        assert resp.headers["Location"] == "/g/123"

    async def test_unsafe_next_falls_back_to_default(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_viewer(decoy, stub, monkeypatch)
        login = await client.get(
            "/queues/login?next=https://evil.example/x",
            allow_redirects=False,
        )
        state = parse_qs(urlparse(login.headers["Location"]).query)["state"][0]
        serve_httpx(monkeypatch, discord_oauth(identify_json={"id": "42", "username": "u"}))
        resp = await client.get(
            f"/queues/oauth/callback?code=abc&state={state}",
            allow_redirects=False,
        )
        assert resp.status == 302
        assert resp.headers["Location"] == "/queues?my=1"

    async def test_identify_returns_none(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_viewer(decoy, stub, monkeypatch)
        state = await start_viewer_login(client)
        fetch_oauth_identify_fake = stub(viewer_auth, "fetch_oauth_identify")
        decoy.when(await fetch_oauth_identify_fake(ANY, ANY), ignore_extra_args=True).then_return(
            None
        )
        resp = await client.get(f"/queues/oauth/callback?code=abc&state={state}")
        assert resp.status == 401

    async def test_state_pops_after_success(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_viewer(decoy, stub, monkeypatch)
        state = await start_viewer_login(client)
        serve_httpx(monkeypatch, discord_oauth(identify_json={"id": "42", "username": "u"}))
        await client.get(
            f"/queues/oauth/callback?code=abc&state={state}",
            allow_redirects=False,
        )
        # Re-using the same state must now fail because it was popped from the session.
        resp = await client.get(f"/queues/oauth/callback?code=abc&state={state}")
        assert resp.status == 400


@pytest.mark.asyncio
class TestViewerLogout:
    async def test_logout_clears_viewer_keys(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_viewer(decoy, stub, monkeypatch)
        state = await start_viewer_login(client)
        serve_httpx(monkeypatch, discord_oauth(identify_json={"id": "42", "username": "u"}))
        await client.get(
            f"/queues/oauth/callback?code=abc&state={state}",
            allow_redirects=False,
        )
        resp = await client.post("/queues/logout", allow_redirects=False)
        assert resp.status == 302
        assert resp.headers["Location"] == "/queues"


@pytest.mark.asyncio
class TestGrantAdminIfAuthorized:
    async def test_owner_gets_admin_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(viewer_auth.settings, "OWNER_XID", 42)
        session = blank_session()
        await viewer_auth.grant_admin_if_authorized(
            session,
            {"id": "42", "global_name": "Owner"},
            42,
        )
        assert session[ADMIN_XID_KEY] == 42
        assert session[ADMIN_NAME_KEY] == "Owner"

    async def test_owner_check_skips_database(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # An owner is recognized without ever consulting the database.
        monkeypatch.setattr(viewer_auth.settings, "OWNER_XID", 42)
        is_admin = stub(users, "is_admin")
        session = blank_session()
        await viewer_auth.grant_admin_if_authorized(session, {"id": "42"}, 42)
        assert session[ADMIN_XID_KEY] == 42
        decoy.verify(await is_admin(ANY), times=0, ignore_extra_args=True)

    async def test_dashboard_admin_gets_admin_keys(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(viewer_auth.settings, "OWNER_XID", 99)
        monkeypatch.setattr(viewer_auth, "db_session_manager", noop_db_session)
        is_admin_fake = stub(users, "is_admin")
        decoy.when(await is_admin_fake(ANY), ignore_extra_args=True).then_return(True)
        session = blank_session()
        await viewer_auth.grant_admin_if_authorized(
            session,
            {"id": "7", "username": "mod"},
            7,
        )
        assert session[ADMIN_XID_KEY] == 7
        assert session[ADMIN_NAME_KEY] == "mod"

    async def test_non_admin_gets_no_admin_keys(
        self,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(viewer_auth.settings, "OWNER_XID", 99)
        monkeypatch.setattr(viewer_auth, "db_session_manager", noop_db_session)
        is_admin_fake = stub(users, "is_admin")
        decoy.when(await is_admin_fake(ANY), ignore_extra_args=True).then_return(False)
        session = blank_session()
        await viewer_auth.grant_admin_if_authorized(session, {"id": "7"}, 7)
        assert ADMIN_XID_KEY not in session
        assert ADMIN_NAME_KEY not in session


@pytest.mark.asyncio
class TestAdminIsolation:
    """A viewer-only session must never grant access to `/admin/*` routes."""

    async def test_viewer_session_does_not_unlock_admin(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_viewer(decoy, stub, monkeypatch)  # defaults this identity to a non-admin
        state = await start_viewer_login(client)
        serve_httpx(monkeypatch, discord_oauth(identify_json={"id": "42", "username": "u"}))
        callback = await client.get(
            f"/queues/oauth/callback?code=abc&state={state}",
            allow_redirects=False,
        )
        assert callback.status == 302
        # Viewer is "logged in" but the admin middleware must still redirect.
        resp = await client.get("/admin/dashboard", allow_redirects=False)
        assert resp.status == 302
        assert resp.headers["Location"] == "/admin/login"

    async def test_owner_viewer_login_unlocks_admin(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Logging in as the owner from the public /queues flow also starts an admin
        # session, so /admin/* is reachable without a separate /admin/login.
        await configure_viewer(decoy, stub, monkeypatch)
        monkeypatch.setattr(viewer_auth.settings, "OWNER_XID", 42)
        state = await start_viewer_login(client)
        serve_httpx(monkeypatch, discord_oauth(identify_json={"id": "42", "username": "owner"}))
        callback = await client.get(
            f"/queues/oauth/callback?code=abc&state={state}",
            allow_redirects=False,
        )
        assert callback.status == 302
        resp = await client.get("/admin/dashboard", allow_redirects=False)
        assert resp.status == 200

    async def test_dashboard_admin_viewer_login_unlocks_admin(
        self,
        client: WebClient,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await configure_viewer(decoy, stub, monkeypatch)
        monkeypatch.setattr(viewer_auth.settings, "OWNER_XID", 99)
        is_admin_fake = stub(users, "is_admin")
        decoy.when(await is_admin_fake(ANY), ignore_extra_args=True).then_return(True)
        state = await start_viewer_login(client)
        serve_httpx(monkeypatch, discord_oauth(identify_json={"id": "7", "username": "mod"}))
        callback = await client.get(
            f"/queues/oauth/callback?code=abc&state={state}",
            allow_redirects=False,
        )
        assert callback.status == 302
        resp = await client.get("/admin/dashboard", allow_redirects=False)
        assert resp.status == 200
