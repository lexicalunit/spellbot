from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
import pytest_asyncio

from spellbot.web.api import admin_auth

if TYPE_CHECKING:
    from aiohttp import web
    from aiohttp.test_utils import TestClient
    from pytest_mock import MockerFixture

    WebClient = TestClient[web.Request, web.Application]

pytestmark = pytest.mark.use_db


def make_httpx_client(*, identify_json: dict[str, Any] | None = None) -> MagicMock:
    """Build an `httpx.AsyncClient` mock context manager for successful OAuth."""
    inner = MagicMock()
    token_resp = MagicMock(status_code=200)
    token_resp.json = MagicMock(return_value={"access_token": "tok"})
    inner.post = AsyncMock(return_value=token_resp)
    identify_resp = MagicMock(status_code=200)
    identify_resp.json = MagicMock(
        return_value=identify_json or {"id": "42", "username": "admin"},
    )
    inner.get = AsyncMock(return_value=identify_resp)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=inner)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


async def configure_admin(mocker: MockerFixture) -> None:
    mocker.patch.object(admin_auth.settings, "BOT_APPLICATION_ID", "appid-1")
    mocker.patch.object(admin_auth.settings, "BOT_CLIENT_SECRET", "secret-1")
    # Must match the test client's host so `canonical_host_redirect` is a no-op.
    mocker.patch.object(admin_auth.settings, "API_BASE_URL", "http://127.0.0.1")
    mocker.patch.object(admin_auth.settings, "OWNER_XID", 42)


@pytest_asyncio.fixture
async def admin_client(client: WebClient, mocker: MockerFixture) -> WebClient:
    """Return a test client whose cookie jar holds a valid admin session for xid=42."""
    await configure_admin(mocker)
    login_resp = await client.get("/admin/login", allow_redirects=False)
    state = parse_qs(urlparse(login_resp.headers["Location"]).query)["state"][0]
    mocker.patch(
        "spellbot.web.api.admin_auth.httpx.AsyncClient",
        return_value=make_httpx_client(),
    )
    cb = await client.get(
        f"/admin/oauth/callback?code=abc&state={state}",
        allow_redirects=False,
    )
    assert cb.status == 302
    return client


# Each tuple: (url path, expected top-level JSON key(s) that must be present).
JSON_ENDPOINTS: list[tuple[str, set[str]]] = [
    (
        "/admin/dashboard/summary",
        {
            "games",
            "expired",
            "fill_rate",
            "players",
            "servers",
            "brackets",
            "period",
            "bucket",
        },
    ),
    ("/admin/dashboard/totals", {"games", "players", "servers"}),
    ("/admin/dashboard/users-activity", {"new_users", "dau", "wau", "mau", "dau_mau"}),
    ("/admin/dashboard/games", {"started", "expired"}),
    ("/admin/dashboard/player-growth", {"cumulative_players"}),
    ("/admin/dashboard/casual-vs-cedh", {"casual", "cedh"}),
    ("/admin/dashboard/server-popularity", {"series", "totals"}),
    ("/admin/dashboard/service-popularity", {"series"}),
    ("/admin/dashboard/bracket-adoption", {"rate", "leaders"}),
    ("/admin/dashboard/user-languages", {"rows"}),
    ("/admin/dashboard/game-languages", {"rows"}),
    ("/admin/dashboard/top-guild-per-game-language", {"rows"}),
    ("/admin/dashboard/guild-languages", {"rows"}),
    ("/admin/dashboard/hour-of-day", {"hours"}),
    ("/admin/dashboard/day-of-week", {"days"}),
    ("/admin/dashboard/popular-formats", {"rows"}),
    ("/admin/dashboard/popular-seats", {"rows"}),
    ("/admin/dashboard/top-players", {"rows"}),
    ("/admin/dashboard/top-blocked", {"rows"}),
    ("/admin/dashboard/avg-wait-time", {"series"}),
    ("/admin/dashboard/games-per-player", {"median", "histogram"}),
    ("/admin/dashboard/rules", {"top_rules", "rule_ngrams"}),
    ("/admin/dashboard/cohort-retention", {"cohorts", "max_weeks"}),
    ("/admin/dashboard/activity-heatmap", {"cells"}),
    ("/admin/dashboard/wait-time-distribution", {"p50", "p95", "p99"}),
    ("/admin/dashboard/voice-adoption", {"rate"}),
    ("/admin/dashboard/blind-adoption", {"rate"}),
    ("/admin/dashboard/mythic-verification", {"rate"}),
    ("/admin/dashboard/queue-depth", {"total", "by_format"}),
    ("/admin/dashboard/active-queues", {"rows"}),
    ("/admin/dashboard/guilds", {"guilds"}),
]


@pytest.mark.asyncio
class TestDashboardShell:
    async def test_shell_renders_when_authenticated(self, admin_client: WebClient) -> None:
        resp = await admin_client.get("/admin/dashboard")
        assert resp.status == 200
        body = await resp.text()
        assert "SpellBot" in body or "dashboard" in body.lower()

    async def test_shell_redirects_when_unauthenticated(self, client: WebClient) -> None:
        resp = await client.get("/admin/dashboard", allow_redirects=False)
        assert resp.status == 302
        assert resp.headers["Location"] == "/admin/login"

    async def test_shell_links_to_active_queues(self, admin_client: WebClient) -> None:
        resp = await admin_client.get("/admin/dashboard")
        body = await resp.text()
        assert '<a class="nav-link" href="/queues">Active Queues</a>' in body


@pytest.mark.asyncio
class TestDashboardJsonEndpoints:
    @pytest.mark.parametrize(("path", "expected_keys"), JSON_ENDPOINTS)
    async def test_endpoint_returns_json(
        self,
        admin_client: WebClient,
        path: str,
        expected_keys: set[str],
    ) -> None:
        resp = await admin_client.get(path)
        assert resp.status == 200
        assert resp.content_type == "application/json"
        body = await resp.text()
        data = json.loads(body)
        assert expected_keys <= set(data.keys())

    async def test_endpoint_accepts_period_and_guild_query_params(
        self,
        admin_client: WebClient,
    ) -> None:
        resp = await admin_client.get(
            "/admin/dashboard/summary?period=7d&guild=12345",
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["period"] == "7d"

    async def test_endpoint_accepts_exclude_guild_filter(
        self,
        admin_client: WebClient,
    ) -> None:
        resp = await admin_client.get(
            "/admin/dashboard/summary?period=all&guild=not:99",
        )
        assert resp.status == 200

    async def test_endpoint_unauthenticated_redirects(self, client: WebClient) -> None:
        resp = await client.get("/admin/dashboard/summary", allow_redirects=False)
        assert resp.status == 302
        assert resp.headers["Location"] == "/admin/login"


@pytest_asyncio.fixture
async def non_owner_admin_client(client: WebClient, mocker: MockerFixture) -> WebClient:
    """Return a client logged in as an admin (xid=99) who is not the owner (xid=42)."""
    await configure_admin(mocker)
    mocker.patch("spellbot.services.users.is_admin", AsyncMock(return_value=True))
    login_resp = await client.get("/admin/login", allow_redirects=False)
    state = parse_qs(urlparse(login_resp.headers["Location"]).query)["state"][0]
    mocker.patch(
        "spellbot.web.api.admin_auth.httpx.AsyncClient",
        return_value=make_httpx_client(identify_json={"id": "99", "username": "helper"}),
    )
    cb = await client.get(
        f"/admin/oauth/callback?code=abc&state={state}",
        allow_redirects=False,
    )
    assert cb.status == 302
    return client


@pytest.mark.asyncio
class TestDashboardSqlConsole:
    async def test_owner_sees_console_in_shell(self, admin_client: WebClient) -> None:
        resp = await admin_client.get("/admin/dashboard")
        body = await resp.text()
        assert "SQL Console" in body
        assert "window.SQL_CONSOLE_ENABLED = true" in body

    async def test_non_owner_admin_does_not_see_console(
        self,
        non_owner_admin_client: WebClient,
    ) -> None:
        resp = await non_owner_admin_client.get("/admin/dashboard")
        body = await resp.text()
        assert "SQL Console" not in body
        assert "window.SQL_CONSOLE_ENABLED = false" in body

    async def test_owner_runs_select(self, admin_client: WebClient) -> None:
        resp = await admin_client.post(
            "/admin/dashboard/sql",
            json={"query": "SELECT 1 AS n, 'hi' AS label"},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["columns"] == ["n", "label"]
        assert data["rows"] == [[1, "hi"]]
        assert data["row_count"] == 1
        assert data["truncated"] is False

    async def test_non_primitive_cell_is_stringified(self, admin_client: WebClient) -> None:
        resp = await admin_client.post(
            "/admin/dashboard/sql",
            json={"query": "SELECT TIMESTAMP '2020-01-02 03:04:05' AS t"},
        )
        assert resp.status == 200
        data = await resp.json()
        # Timestamps aren't JSON primitives, so they come back as strings.
        assert data["rows"] == [["2020-01-02 03:04:05"]]

    async def test_statement_without_result_set(self, admin_client: WebClient) -> None:
        resp = await admin_client.post(
            "/admin/dashboard/sql",
            json={"query": "DO $$ BEGIN END $$"},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data == {"columns": [], "rows": [], "row_count": 0, "truncated": False}

    async def test_large_int_is_stringified(self, admin_client: WebClient) -> None:
        resp = await admin_client.post(
            "/admin/dashboard/sql",
            json={"query": "SELECT 9007199254740993 AS big"},
        )
        data = await resp.json()
        # Beyond JS's safe integer range, so returned as a string to keep precision.
        assert data["rows"] == [["9007199254740993"]]

    async def test_write_is_rejected_by_read_only_transaction(
        self,
        admin_client: WebClient,
    ) -> None:
        resp = await admin_client.post(
            "/admin/dashboard/sql",
            json={"query": "CREATE TABLE sql_console_ro_check (id int)"},
        )
        assert resp.status == 400
        data = await resp.json()
        assert "error" in data
        assert "read-only" in data["error"].lower()

    async def test_syntax_error_returns_message(self, admin_client: WebClient) -> None:
        resp = await admin_client.post(
            "/admin/dashboard/sql",
            json={"query": "SELEC bogus"},
        )
        assert resp.status == 400
        assert "error" in await resp.json()

    async def test_empty_query_returns_error(self, admin_client: WebClient) -> None:
        resp = await admin_client.post("/admin/dashboard/sql", json={"query": "  ;  "})
        assert resp.status == 400
        assert (await resp.json())["error"] == "Empty query."

    async def test_missing_query_field(self, admin_client: WebClient) -> None:
        resp = await admin_client.post("/admin/dashboard/sql", json={})
        assert resp.status == 400

    async def test_invalid_json_body(self, admin_client: WebClient) -> None:
        resp = await admin_client.post(
            "/admin/dashboard/sql",
            data="not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400

    async def test_non_owner_admin_forbidden(
        self,
        non_owner_admin_client: WebClient,
    ) -> None:
        resp = await non_owner_admin_client.post(
            "/admin/dashboard/sql",
            json={"query": "SELECT 1"},
        )
        assert resp.status == 403

    async def test_unauthenticated_redirects(self, client: WebClient) -> None:
        resp = await client.post(
            "/admin/dashboard/sql",
            json={"query": "SELECT 1"},
            allow_redirects=False,
        )
        assert resp.status == 302
        assert resp.headers["Location"] == "/admin/login"
