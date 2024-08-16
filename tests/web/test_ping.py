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
