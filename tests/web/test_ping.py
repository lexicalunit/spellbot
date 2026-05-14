from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from aiohttp.client import ClientSession


@pytest.mark.asyncio
class TestWebPing:
    async def test_ping(self, client: ClientSession) -> None:
        resp = await client.get("/")
        assert resp.status == 200
        text = await resp.text()
        assert "ok" in text


@pytest.mark.asyncio
class TestWebStaticFiles:
    async def test_analytics_js(self, client: ClientSession) -> None:
        resp = await client.get("/analytics.js")
        assert resp.status == 200
        assert resp.content_type == "application/javascript"
        text = await resp.text()
        assert "ANALYTICS_CONFIG" in text
        assert resp.headers.get("Cache-Control") == "public, max-age=3600"
