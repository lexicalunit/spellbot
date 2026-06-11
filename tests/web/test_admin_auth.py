from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet

from spellbot.web.api import admin_auth
from spellbot.web.api.admin_auth import (
    admin_auth_middleware,
    get_admin_user_xid,
    oauth_redirect_uri,
    resolve_session_key,
)

if TYPE_CHECKING:
    from aiohttp import web
    from aiohttp.test_utils import TestClient
    from pytest_mock import MockerFixture

    WebClient = TestClient[web.Request, web.Application]


class TestResolveSessionKey:
    def test_unset_generates_key(self, mocker: MockerFixture) -> None:
        mocker.patch.object(admin_auth.settings, "SESSION_SECRET_KEY", None)
        fernet = resolve_session_key()
        assert isinstance(fernet, Fernet)

    def test_valid_key(self, mocker: MockerFixture) -> None:
        key = Fernet.generate_key().decode("utf-8")
        mocker.patch.object(admin_auth.settings, "SESSION_SECRET_KEY", f'  "{key}"  ')
        fernet = resolve_session_key()
        assert isinstance(fernet, Fernet)

    def test_invalid_key_raises(self, mocker: MockerFixture) -> None:
        mocker.patch.object(admin_auth.settings, "SESSION_SECRET_KEY", "not-a-real-key")
        with pytest.raises(ValueError, match="SESSION_SECRET_KEY"):
            resolve_session_key()


class TestOauthRedirectUri:
    def test_strips_trailing_slash(self, mocker: MockerFixture) -> None:
        mocker.patch.object(admin_auth.settings, "API_BASE_URL", "https://example.com/")
        assert oauth_redirect_uri() == "https://example.com/admin/oauth/callback"


@pytest.mark.asyncio
class TestGetAdminUserXid:
    async def test_no_xid_in_session(self, mocker: MockerFixture) -> None:
        mocker.patch("spellbot.web.api.admin_auth.get_session", AsyncMock(return_value={}))
        assert await get_admin_user_xid(MagicMock()) is None

    async def test_non_int_xid(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "spellbot.web.api.admin_auth.get_session",
            AsyncMock(return_value={"xid": "not-an-int"}),
        )
        assert await get_admin_user_xid(MagicMock()) is None

    async def test_valid_xid(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "spellbot.web.api.admin_auth.get_session",
            AsyncMock(return_value={"xid": 42}),
        )
        assert await get_admin_user_xid(MagicMock()) == 42


@pytest.mark.asyncio
class TestAdminAuthMiddleware:
    async def test_non_admin_path_passes_through(self) -> None:
        request = MagicMock()
        request.path = "/something/else"
        handler = AsyncMock(return_value="ok")
        assert await admin_auth_middleware(request, handler) == "ok"
        handler.assert_awaited_once_with(request)

    async def test_public_admin_path_passes_through(self) -> None:
        request = MagicMock()
        request.path = "/admin/login"
        handler = AsyncMock(return_value="ok")
        assert await admin_auth_middleware(request, handler) == "ok"

    async def test_unauthenticated_admin_path_redirects(self, mocker: MockerFixture) -> None:
        request = MagicMock()
        request.path = "/admin/dashboard"
        mocker.patch(
            "spellbot.web.api.admin_auth.get_admin_user_xid",
            AsyncMock(return_value=None),
        )
        handler = AsyncMock()
        resp = await admin_auth_middleware(request, handler)
        assert resp.status == 302
        assert resp.headers["Location"] == "/admin/login"
        handler.assert_not_awaited()

    async def test_authenticated_admin_path_passes_through(self, mocker: MockerFixture) -> None:
        request = MagicMock()
        request.path = "/admin/dashboard"
        mocker.patch(
            "spellbot.web.api.admin_auth.get_admin_user_xid",
            AsyncMock(return_value=42),
        )
        handler = AsyncMock(return_value="ok")
        assert await admin_auth_middleware(request, handler) == "ok"

    async def test_bare_admin_path_requires_auth(self, mocker: MockerFixture) -> None:
        request = MagicMock()
        request.path = "/admin"
        mocker.patch(
            "spellbot.web.api.admin_auth.get_admin_user_xid",
            AsyncMock(return_value=None),
        )
        resp = await admin_auth_middleware(request, AsyncMock())
        assert resp.status == 302


@pytest.mark.asyncio
class TestAdminLogin:
    async def test_unconfigured(self, client: WebClient, mocker: MockerFixture) -> None:
        mocker.patch.object(admin_auth.settings, "BOT_APPLICATION_ID", None)
        mocker.patch.object(admin_auth.settings, "BOT_CLIENT_SECRET", None)
        resp = await client.get("/admin/login")
        assert resp.status == 503

    async def test_redirects_to_discord(self, client: WebClient, mocker: MockerFixture) -> None:
        mocker.patch.object(admin_auth.settings, "BOT_APPLICATION_ID", "appid-1")
        mocker.patch.object(admin_auth.settings, "BOT_CLIENT_SECRET", "secret-1")
        # Match the test client's host so `canonical_host_redirect` is a no-op.
        mocker.patch.object(admin_auth.settings, "API_BASE_URL", "http://127.0.0.1")
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
        mocker: MockerFixture,
    ) -> None:
        mocker.patch.object(admin_auth.settings, "BOT_APPLICATION_ID", "appid-1")
        mocker.patch.object(admin_auth.settings, "BOT_CLIENT_SECRET", "secret-1")
        mocker.patch.object(
            admin_auth.settings,
            "API_BASE_URL",
            "https://prod.app.spellbot.io",
        )
        resp = await client.get("/admin/login?next=/admin/dashboard", allow_redirects=False)
        assert resp.status == 302
        assert (
            resp.headers["Location"]
            == "https://prod.app.spellbot.io/admin/login?next=/admin/dashboard"
        )


async def configure_admin(mocker: MockerFixture) -> None:
    mocker.patch.object(admin_auth.settings, "BOT_APPLICATION_ID", "appid-1")
    mocker.patch.object(admin_auth.settings, "BOT_CLIENT_SECRET", "secret-1")
    mocker.patch.object(admin_auth.settings, "API_BASE_URL", "http://127.0.0.1")
    mocker.patch.object(admin_auth.settings, "OWNER_XID", 42)


async def start_login(client: WebClient) -> str:
    """Hit /admin/login and return the oauth state from the redirect URL."""
    resp = await client.get("/admin/login", allow_redirects=False)
    assert resp.status == 302
    params = parse_qs(urlparse(resp.headers["Location"]).query)
    return params["state"][0]


def make_httpx_client(
    *,
    token_status: int = 200,
    token_json: dict[str, Any] | None = None,
    identify_status: int = 200,
    identify_json: dict[str, Any] | None = None,
    raise_http: bool = False,
) -> MagicMock:
    inner = MagicMock()
    if raise_http:
        inner.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
    else:
        token_resp = MagicMock(status_code=token_status)
        token_resp.json = MagicMock(return_value=token_json or {"access_token": "tok"})
        inner.post = AsyncMock(return_value=token_resp)
    identify_resp = MagicMock(status_code=identify_status)
    identify_resp.json = MagicMock(return_value=identify_json or {"id": "42", "username": "u"})
    inner.get = AsyncMock(return_value=identify_resp)
    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=inner)
    client_cm.__aexit__ = AsyncMock(return_value=None)
    return client_cm


@pytest.mark.asyncio
class TestAdminOauthCallback:
    async def test_unconfigured(self, client: WebClient, mocker: MockerFixture) -> None:
        mocker.patch.object(admin_auth.settings, "BOT_APPLICATION_ID", None)
        mocker.patch.object(admin_auth.settings, "BOT_CLIENT_SECRET", None)
        resp = await client.get("/admin/oauth/callback")
        assert resp.status == 503

    async def test_missing_state(self, client: WebClient, mocker: MockerFixture) -> None:
        await configure_admin(mocker)
        resp = await client.get("/admin/oauth/callback?code=abc")
        assert resp.status == 400

    async def test_state_mismatch(self, client: WebClient, mocker: MockerFixture) -> None:
        await configure_admin(mocker)
        await start_login(client)
        resp = await client.get("/admin/oauth/callback?code=abc&state=wrong")
        assert resp.status == 400

    async def test_token_exchange_fails(self, client: WebClient, mocker: MockerFixture) -> None:
        await configure_admin(mocker)
        state = await start_login(client)
        mocker.patch(
            "spellbot.web.api.oauth.httpx.AsyncClient",
            return_value=make_httpx_client(token_status=400),
        )
        resp = await client.get(f"/admin/oauth/callback?code=abc&state={state}")
        assert resp.status == 401

    async def test_identify_fails(self, client: WebClient, mocker: MockerFixture) -> None:
        await configure_admin(mocker)
        state = await start_login(client)
        mocker.patch(
            "spellbot.web.api.oauth.httpx.AsyncClient",
            return_value=make_httpx_client(identify_status=500),
        )
        resp = await client.get(f"/admin/oauth/callback?code=abc&state={state}")
        assert resp.status == 401

    async def test_http_error(self, client: WebClient, mocker: MockerFixture) -> None:
        await configure_admin(mocker)
        state = await start_login(client)
        mocker.patch(
            "spellbot.web.api.oauth.httpx.AsyncClient",
            return_value=make_httpx_client(raise_http=True),
        )
        resp = await client.get(f"/admin/oauth/callback?code=abc&state={state}")
        assert resp.status == 502

    async def test_bad_user_payload(self, client: WebClient, mocker: MockerFixture) -> None:
        await configure_admin(mocker)
        state = await start_login(client)
        mocker.patch(
            "spellbot.web.api.oauth.httpx.AsyncClient",
            return_value=make_httpx_client(identify_json={"no_id": True}),
        )
        resp = await client.get(f"/admin/oauth/callback?code=abc&state={state}")
        assert resp.status == 401

    async def test_unauthorized_xid(self, client: WebClient, mocker: MockerFixture) -> None:
        await configure_admin(mocker)
        state = await start_login(client)
        mocker.patch(
            "spellbot.web.api.oauth.httpx.AsyncClient",
            return_value=make_httpx_client(identify_json={"id": "999", "username": "x"}),
        )
        mocker.patch(
            "spellbot.web.api.admin_auth.db_session_manager",
            return_value=AsyncMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()),
        )
        mocker.patch(
            "spellbot.web.api.admin_auth.services.users.is_admin",
            AsyncMock(return_value=False),
        )
        resp = await client.get(f"/admin/oauth/callback?code=abc&state={state}")
        assert resp.status == 403

    async def test_promoted_xid_authorized(
        self,
        client: WebClient,
        mocker: MockerFixture,
    ) -> None:
        await configure_admin(mocker)
        state = await start_login(client)
        mocker.patch(
            "spellbot.web.api.oauth.httpx.AsyncClient",
            return_value=make_httpx_client(identify_json={"id": "777", "username": "promoted"}),
        )
        mocker.patch(
            "spellbot.web.api.admin_auth.db_session_manager",
            return_value=AsyncMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()),
        )
        mocker.patch(
            "spellbot.web.api.admin_auth.services.users.is_admin",
            AsyncMock(return_value=True),
        )
        resp = await client.get(
            f"/admin/oauth/callback?code=abc&state={state}",
            allow_redirects=False,
        )
        assert resp.status == 302
        assert resp.headers["Location"] == "/admin/dashboard"

    async def test_success(self, client: WebClient, mocker: MockerFixture) -> None:
        await configure_admin(mocker)
        state = await start_login(client)
        mocker.patch(
            "spellbot.web.api.oauth.httpx.AsyncClient",
            return_value=make_httpx_client(
                identify_json={"id": "42", "global_name": "Amy", "username": "u"},
            ),
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
        mocker: MockerFixture,
    ) -> None:
        await configure_admin(mocker)
        state = await start_login(client)
        mocker.patch(
            "spellbot.web.api.oauth.httpx.AsyncClient",
            return_value=make_httpx_client(identify_json={"id": "42", "username": "fallback"}),
        )
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
        mocker: MockerFixture,
    ) -> None:
        await configure_admin(mocker)
        state = await start_login(client)
        mocker.patch(
            "spellbot.web.api.oauth.httpx.AsyncClient",
            return_value=make_httpx_client(identify_json={"id": "42", "username": "u"}),
        )
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
        mocker: MockerFixture,
    ) -> None:
        await configure_admin(mocker)
        resp = await client.get("/admin/login?logged_out=1", allow_redirects=False)
        assert resp.status == 200
        body = await resp.text()
        assert "You've been signed out" in body
        # The manual sign-in link is present, but no automatic OAuth redirect.
        assert 'href="/admin/login"' in body
        assert admin_auth.DISCORD_AUTHORIZE_URL not in body
