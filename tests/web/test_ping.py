from __future__ import annotations

import pytest
from aiohttp.client import ClientSession


@pytest.mark.asyncio
class TestWebPing:
    async def test_ping(self, client: ClientSession):
        resp = await client.get("/")
        assert resp.status == 200
        text = await resp.text()
        assert "ok" in text
