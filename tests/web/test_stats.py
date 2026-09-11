# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from spellbot.public_stats import PublicStats
from spellbot.web.builder import PUBLIC_CORS_PATHS

if TYPE_CHECKING:
    from aiohttp import web
    from aiohttp.test_utils import TestClient

    WebClient = TestClient[web.Request, web.Application]

pytestmark = pytest.mark.use_db

STATS = PublicStats(
    active_servers=3,
    active_players=12,
    active_games=5,
    last_updated="2024-06-15T12:00:00+00:00",
)


@pytest.mark.asyncio
class TestStatsJson:
    async def test_serves_cached_stats(self, client: WebClient) -> None:
        with patch(
            "spellbot.web.api.stats.get_public_stats",
            AsyncMock(return_value=STATS),
        ):
            resp = await client.get("/stats.json")

        assert resp.status == 200
        assert await resp.json() == STATS.to_dict()
        assert resp.headers.get("Cache-Control") == "public, max-age=60"

    async def test_never_touches_the_database(self, client: WebClient) -> None:
        """The whole point of the endpoint is to keep site traffic off the DB."""
        with (
            patch(
                "spellbot.web.api.stats.get_public_stats",
                AsyncMock(return_value=STATS),
            ),
            patch("spellbot.database.begin_session", AsyncMock()) as begin_session,
        ):
            resp = await client.get("/stats.json")

        assert resp.status == 200
        begin_session.assert_not_called()

    async def test_returns_503_when_no_stats_are_cached(self, client: WebClient) -> None:
        with patch(
            "spellbot.web.api.stats.get_public_stats",
            AsyncMock(return_value=None),
        ):
            resp = await client.get("/stats.json")

        assert resp.status == 503
        assert await resp.json() == {"error": "stats unavailable"}
        # A failure must not be cached, or the widget stays broken for a minute.
        assert resp.headers.get("Cache-Control") == "no-store"


@pytest.mark.asyncio
class TestPublicCors:
    async def test_stats_json_is_readable_cross_origin(self, client: WebClient) -> None:
        with patch(
            "spellbot.web.api.stats.get_public_stats",
            AsyncMock(return_value=STATS),
        ):
            resp = await client.get("/stats.json", headers={"Origin": "https://spellbot.io"})

        assert resp.headers.get("Access-Control-Allow-Origin") == "*"

    async def test_queues_json_is_readable_cross_origin(self, client: WebClient) -> None:
        resp = await client.get("/queues.json", headers={"Origin": "https://spellbot.io"})

        assert resp.status == 200
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"

    async def test_status_json_is_readable_cross_origin(self, client: WebClient) -> None:
        """`/status.json` was already public; CORS only widens who may read it."""
        resp = await client.get("/status.json", headers={"Origin": "https://example.com"})

        assert resp.status == 200
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"

    async def test_status_page_still_serves_normally(self, client: WebClient) -> None:
        """Navigation is not a CORS operation, so the HTML page is unaffected."""
        resp = await client.get("/status")

        assert resp.status == 200

    async def test_other_paths_are_not_cors_enabled(self, client: WebClient) -> None:
        resp = await client.get("/health")

        assert resp.status == 200
        assert "Access-Control-Allow-Origin" not in resp.headers

    async def test_no_authenticated_prefix_is_ever_allowlisted(self) -> None:
        """Guard against someone adding an authenticated route to the allowlist."""
        for path in PUBLIC_CORS_PATHS:
            assert not path.startswith(("/api", "/admin"))
