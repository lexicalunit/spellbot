# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from spellbot import redis_client
from spellbot.redis_client import close_redis
from spellbot.settings import settings
from spellbot.web.api import ping
from tests.mocks.redis import FakeRedis, serve_redis

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from aiohttp.client import ClientSession
    from decoy import Decoy

    from tests.fixtures import Stub

pytestmark = pytest.mark.use_db


@pytest_asyncio.fixture(autouse=True)
async def reset_redis_client() -> AsyncGenerator[None]:
    redis_client.shared.client = None
    yield
    await close_redis()


@pytest.mark.asyncio
class TestWebPing:
    async def test_ping(self, client: ClientSession) -> None:
        resp = await client.get("/")
        assert resp.status == 200
        text = await resp.text()
        assert "ok" in text


@pytest.mark.asyncio
class TestSecurityHeaders:
    @pytest.mark.parametrize("path", ["/", "/no-such-page"])
    async def test_security_headers(self, client: ClientSession, path: str) -> None:
        resp = await client.get(path)
        assert resp.headers["Server"] == "SpellBot"
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "X-XSS-Protection" not in resp.headers
        assert "Access-Control-Allow-Origin" not in resp.headers
        assert "Strict-Transport-Security" not in resp.headers

    async def test_hsts_when_served_over_https(
        self,
        client: ClientSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "API_BASE_URL", "https://prod.app.spellbot.io")
        resp = await client.get("/")
        assert resp.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"


@pytest.mark.asyncio
class TestWebStaticFiles:
    async def test_analytics_js(self, client: ClientSession) -> None:
        resp = await client.get("/analytics.js")
        assert resp.status == 200
        assert resp.content_type == "application/javascript"
        text = await resp.text()
        assert "ANALYTICS_CONFIG" in text
        # pure helpers are concatenated ahead of the main IIFE
        assert "function toDayMap" in text
        assert resp.headers.get("Cache-Control") == "no-cache, no-store, must-revalidate"

    async def test_dashboard_js(self, client: ClientSession) -> None:
        resp = await client.get("/dashboard.js")
        assert resp.status == 200
        assert resp.content_type == "application/javascript"
        text = await resp.text()
        # pure helpers are concatenated ahead of the main IIFE
        assert "PERIOD_BUCKET" in text
        assert resp.headers.get("Cache-Control") == "no-cache, no-store, must-revalidate"

    async def test_robots_txt(self, client: ClientSession) -> None:
        resp = await client.get("/robots.txt")
        assert resp.status == 200
        assert resp.content_type == "text/plain"
        text = await resp.text()
        assert text == "User-agent: *\nDisallow: /\n"


@pytest.mark.asyncio
class TestWebHealth:
    async def test_health_all_healthy(
        self,
        client: ClientSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test health check when database is healthy and Redis is disabled."""
        monkeypatch.setattr(settings, "REDIS_URL", None)
        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "healthy"
        assert data["database"]["status"] == "healthy"
        assert data["redis"]["status"] == "disabled"

    async def test_health_with_redis_healthy(
        self,
        client: ClientSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test health check when both database and Redis are healthy."""
        serve_redis(monkeypatch, FakeRedis())
        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "healthy"
        assert data["database"]["status"] == "healthy"
        assert data["redis"]["status"] == "healthy"

    async def test_health_database_unhealthy(
        self,
        client: ClientSession,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test health check when database connection fails."""
        monkeypatch.setattr(settings, "REDIS_URL", None)
        db_session_manager_fake = stub(ping, "db_session_manager")
        decoy.when(db_session_manager_fake(), ignore_extra_args=True).then_raise(
            Exception("Connection refused")
        )
        resp = await client.get("/health")
        assert resp.status == 503
        data = await resp.json()
        assert data["status"] == "unhealthy"
        assert data["database"]["status"] == "unhealthy"
        assert "Connection refused" in data["database"]["error"]

    async def test_health_redis_unhealthy(
        self,
        client: ClientSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test health check when Redis connection fails."""
        serve_redis(monkeypatch, FakeRedis(error=Exception("Redis connection failed")))
        resp = await client.get("/health")
        assert resp.status == 503
        data = await resp.json()
        assert data["status"] == "unhealthy"
        assert data["database"]["status"] == "healthy"
        assert data["redis"]["status"] == "unhealthy"
        assert "Redis connection failed" in data["redis"]["error"]
