from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlparse

import pytest

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
from tests.web.test_admin_auth import make_httpx_client

if TYPE_CHECKING:
    from aiohttp import web
    from aiohttp.test_utils import TestClient
    from pytest_mock import MockerFixture

    WebClient = TestClient[web.Request, web.Application]


class TestViewerOauthRedirectUri:
    def test_strips_trailing_slash(self, mocker: MockerFixture) -> None:
        mocker.patch.object(viewer_auth.settings, "API_BASE_URL", "https://example.com/")
        assert viewer_oauth_redirect_uri() == "https://example.com/queues/oauth/callback"


class TestCanonicalHostRedirect:
    @staticmethod
    def make_request(host: str, rel_url: str) -> MagicMock:
        request = MagicMock()
        request.url.host = host
        request.rel_url = rel_url
        return request

    def test_returns_none_when_api_base_url_unset(self, mocker: MockerFixture) -> None:
        mocker.patch.object(oauth.settings, "API_BASE_URL", None)
        assert canonical_host_redirect(MagicMock()) is None

    def test_returns_none_when_base_has_no_host(self, mocker: MockerFixture) -> None:
        mocker.patch.object(oauth.settings, "API_BASE_URL", "/no-host")
        assert canonical_host_redirect(self.make_request("alias.example.com", "/foo")) is None

    def test_returns_none_when_host_already_matches(self, mocker: MockerFixture) -> None:
        mocker.patch.object(oauth.settings, "API_BASE_URL", "https://bot.spellbot.io")
        request = self.make_request("bot.spellbot.io", "/queues?my=1")
        assert canonical_host_redirect(request) is None

    def test_redirects_to_canonical_host_with_path_and_query(
        self,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch.object(oauth.settings, "API_BASE_URL", "https://bot.spellbot.io")
        request = self.make_request("queues.spellbot.io", "/queues?my=1")
        resp = canonical_host_redirect(request)
        assert resp is not None
        assert resp.location == "https://bot.spellbot.io/queues?my=1"

    def test_rejects_target_with_scheme(self, mocker: MockerFixture) -> None:
        mocker.patch.object(oauth.settings, "API_BASE_URL", "https://bot.spellbot.io")
        request = self.make_request("queues.spellbot.io", "https://evil.example.com/x")
        resp = canonical_host_redirect(request)
        assert resp is not None
        assert resp.location == "https://bot.spellbot.io/"

    def test_rejects_protocol_relative_target(self, mocker: MockerFixture) -> None:
        mocker.patch.object(oauth.settings, "API_BASE_URL", "https://bot.spellbot.io")
        request = self.make_request("queues.spellbot.io", "//evil.example.com/x")
        resp = canonical_host_redirect(request)
        assert resp is not None
        assert resp.location == "https://bot.spellbot.io/"

    def test_rejects_backslash_protocol_relative_target(self, mocker: MockerFixture) -> None:
        mocker.patch.object(oauth.settings, "API_BASE_URL", "https://bot.spellbot.io")
        # Some browsers treat backslashes as forward slashes, so `/\evil.com`
        # would otherwise resolve to `//evil.com` (a host swap).
        request = self.make_request("queues.spellbot.io", "/\\evil.example.com/x")
        resp = canonical_host_redirect(request)
        assert resp is not None
        assert resp.location == "https://bot.spellbot.io/"


@pytest.mark.asyncio
class TestGetViewer:
    async def test_empty_session(self, mocker: MockerFixture) -> None:
        mocker.patch("spellbot.web.api.viewer_auth.get_session", AsyncMock(return_value={}))
        assert await get_viewer(MagicMock()) == (None, None)

    async def test_non_int_xid(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "spellbot.web.api.viewer_auth.get_session",
            AsyncMock(return_value={VIEWER_XID_KEY: "nope"}),
        )
        assert await get_viewer(MagicMock()) == (None, None)

    async def test_valid_xid_with_name(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "spellbot.web.api.viewer_auth.get_session",
            AsyncMock(return_value={VIEWER_XID_KEY: 7, VIEWER_NAME_KEY: "Amy"}),
        )
        assert await get_viewer(MagicMock()) == (7, "Amy")

    async def test_valid_xid_no_name(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "spellbot.web.api.viewer_auth.get_session",
            AsyncMock(return_value={VIEWER_XID_KEY: 7, VIEWER_NAME_KEY: 123}),
        )
        assert await get_viewer(MagicMock()) == (7, None)

    async def test_falls_back_to_admin_session(self, mocker: MockerFixture) -> None:
        # An admin session (no viewer keys) is honored as a viewer identity.
        mocker.patch(
            "spellbot.web.api.viewer_auth.get_session",
            AsyncMock(return_value={ADMIN_XID_KEY: 9, ADMIN_NAME_KEY: "Boss"}),
        )
        assert await get_viewer(MagicMock()) == (9, "Boss")

    async def test_admin_fallback_non_str_name(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "spellbot.web.api.viewer_auth.get_session",
            AsyncMock(return_value={ADMIN_XID_KEY: 9, ADMIN_NAME_KEY: 123}),
        )
        assert await get_viewer(MagicMock()) == (9, None)

    async def test_viewer_session_takes_precedence_over_admin(
        self,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "spellbot.web.api.viewer_auth.get_session",
            AsyncMock(
                return_value={
                    VIEWER_XID_KEY: 7,
                    VIEWER_NAME_KEY: "Amy",
                    ADMIN_XID_KEY: 9,
                    ADMIN_NAME_KEY: "Boss",
                },
            ),
        )
        assert await get_viewer(MagicMock()) == (7, "Amy")

    async def test_admin_fallback_non_int_xid(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "spellbot.web.api.viewer_auth.get_session",
            AsyncMock(return_value={ADMIN_XID_KEY: "nope"}),
        )
        assert await get_viewer(MagicMock()) == (None, None)


@pytest.mark.asyncio
class TestHasViewerSession:
    async def test_true_with_viewer_key(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "spellbot.web.api.viewer_auth.get_session",
            AsyncMock(return_value={VIEWER_XID_KEY: 7}),
        )
        assert await has_viewer_session(MagicMock()) is True

    async def test_false_with_admin_key_only(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "spellbot.web.api.viewer_auth.get_session",
            AsyncMock(return_value={ADMIN_XID_KEY: 9}),
        )
        assert await has_viewer_session(MagicMock()) is False

    async def test_false_when_empty(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "spellbot.web.api.viewer_auth.get_session",
            AsyncMock(return_value={}),
        )
        assert await has_viewer_session(MagicMock()) is False


def configure_viewer(mocker: MockerFixture) -> None:
    mocker.patch.object(viewer_auth.settings, "BOT_APPLICATION_ID", "appid-1")
    mocker.patch.object(viewer_auth.settings, "BOT_CLIENT_SECRET", "secret-1")
    # Must match the test client's host (127.0.0.1) so `canonical_host_redirect`
    # in `viewer_login` doesn't bounce the request away before issuing state.
    mocker.patch.object(viewer_auth.settings, "API_BASE_URL", "http://127.0.0.1")


async def start_viewer_login(client: WebClient) -> str:
    resp = await client.get("/queues/login", allow_redirects=False)
    assert resp.status == 302
    return parse_qs(urlparse(resp.headers["Location"]).query)["state"][0]


@pytest.mark.asyncio
class TestViewerLogin:
    async def test_unconfigured(self, client: WebClient, mocker: MockerFixture) -> None:
        mocker.patch.object(viewer_auth.settings, "BOT_APPLICATION_ID", None)
        mocker.patch.object(viewer_auth.settings, "BOT_CLIENT_SECRET", None)
        resp = await client.get("/queues/login")
        assert resp.status == 503

    async def test_redirects_to_discord(self, client: WebClient, mocker: MockerFixture) -> None:
        configure_viewer(mocker)
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
        mocker: MockerFixture,
    ) -> None:
        # Simulate the user arriving via a vanity hostname (e.g.
        # `queues.spellbot.io`). The session cookie set here would not be
        # visible on the canonical callback host, so the handler must bounce
        # the request to the canonical host before issuing OAuth state.
        configure_viewer(mocker)
        mocker.patch.object(
            viewer_auth.settings,
            "API_BASE_URL",
            "https://prod.app.spellbot.io",
        )
        resp = await client.get("/queues/login?foo=bar", allow_redirects=False)
        assert resp.status == 302
        assert resp.headers["Location"] == "https://prod.app.spellbot.io/queues/login?foo=bar"


@pytest.mark.asyncio
class TestViewerOauthCallback:
    async def test_unconfigured(self, client: WebClient, mocker: MockerFixture) -> None:
        mocker.patch.object(viewer_auth.settings, "BOT_APPLICATION_ID", None)
        mocker.patch.object(viewer_auth.settings, "BOT_CLIENT_SECRET", None)
        resp = await client.get("/queues/oauth/callback")
        assert resp.status == 503

    async def test_missing_state(self, client: WebClient, mocker: MockerFixture) -> None:
        configure_viewer(mocker)
        resp = await client.get("/queues/oauth/callback?code=abc")
        assert resp.status == 400

    async def test_state_mismatch(self, client: WebClient, mocker: MockerFixture) -> None:
        configure_viewer(mocker)
        await start_viewer_login(client)
        resp = await client.get("/queues/oauth/callback?code=abc&state=wrong")
        assert resp.status == 400

    async def test_token_exchange_fails(self, client: WebClient, mocker: MockerFixture) -> None:
        configure_viewer(mocker)
        state = await start_viewer_login(client)
        mocker.patch(
            "spellbot.web.api.oauth.httpx.AsyncClient",
            return_value=make_httpx_client(token_status=400),
        )
        resp = await client.get(f"/queues/oauth/callback?code=abc&state={state}")
        assert resp.status == 401

    async def test_http_error(self, client: WebClient, mocker: MockerFixture) -> None:
        configure_viewer(mocker)
        state = await start_viewer_login(client)
        mocker.patch(
            "spellbot.web.api.oauth.httpx.AsyncClient",
            return_value=make_httpx_client(raise_http=True),
        )
        resp = await client.get(f"/queues/oauth/callback?code=abc&state={state}")
        assert resp.status == 502

    async def test_bad_user_payload(self, client: WebClient, mocker: MockerFixture) -> None:
        configure_viewer(mocker)
        state = await start_viewer_login(client)
        mocker.patch(
            "spellbot.web.api.oauth.httpx.AsyncClient",
            return_value=make_httpx_client(identify_json={"no_id": True}),
        )
        resp = await client.get(f"/queues/oauth/callback?code=abc&state={state}")
        assert resp.status == 401

    async def test_success_redirects_to_queues_with_my(
        self,
        client: WebClient,
        mocker: MockerFixture,
    ) -> None:
        configure_viewer(mocker)
        state = await start_viewer_login(client)
        mocker.patch(
            "spellbot.web.api.oauth.httpx.AsyncClient",
            return_value=make_httpx_client(identify_json={"id": "42", "global_name": "Amy"}),
        )
        resp = await client.get(
            f"/queues/oauth/callback?code=abc&state={state}",
            allow_redirects=False,
        )
        assert resp.status == 302
        assert resp.headers["Location"] == "/queues?my=1"

    async def test_identify_returns_none(self, client: WebClient, mocker: MockerFixture) -> None:
        configure_viewer(mocker)
        state = await start_viewer_login(client)
        mocker.patch(
            "spellbot.web.api.viewer_auth.fetch_oauth_identify",
            AsyncMock(return_value=None),
        )
        resp = await client.get(f"/queues/oauth/callback?code=abc&state={state}")
        assert resp.status == 401

    async def test_state_pops_after_success(
        self,
        client: WebClient,
        mocker: MockerFixture,
    ) -> None:
        configure_viewer(mocker)
        state = await start_viewer_login(client)
        mocker.patch(
            "spellbot.web.api.oauth.httpx.AsyncClient",
            return_value=make_httpx_client(identify_json={"id": "42", "username": "u"}),
        )
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
        mocker: MockerFixture,
    ) -> None:
        configure_viewer(mocker)
        state = await start_viewer_login(client)
        mocker.patch(
            "spellbot.web.api.oauth.httpx.AsyncClient",
            return_value=make_httpx_client(identify_json={"id": "42", "username": "u"}),
        )
        await client.get(
            f"/queues/oauth/callback?code=abc&state={state}",
            allow_redirects=False,
        )
        resp = await client.post("/queues/logout", allow_redirects=False)
        assert resp.status == 302
        assert resp.headers["Location"] == "/queues"


@pytest.mark.asyncio
class TestAdminIsolation:
    """A viewer-only session must never grant access to `/admin/*` routes."""

    async def test_viewer_session_does_not_unlock_admin(
        self,
        client: WebClient,
        mocker: MockerFixture,
    ) -> None:
        configure_viewer(mocker)
        state = await start_viewer_login(client)
        mocker.patch(
            "spellbot.web.api.oauth.httpx.AsyncClient",
            return_value=make_httpx_client(identify_json={"id": "42", "username": "u"}),
        )
        callback = await client.get(
            f"/queues/oauth/callback?code=abc&state={state}",
            allow_redirects=False,
        )
        assert callback.status == 302
        # Viewer is "logged in" but the admin middleware must still redirect.
        resp = await client.get("/admin/dashboard", allow_redirects=False)
        assert resp.status == 302
        assert resp.headers["Location"] == "/admin/login"
