from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from spellbot.web import humanize
from spellbot.web.builder import auth_middleware

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestWebFilters:
    async def test_humanize_happy_path(self) -> None:
        s = humanize(1638137981, 480, "America/Los_Angeles")
        assert s == "January 19, 1970, 3:02:17\u202fPM PST"

    async def test_humanize_bogus_timezone(self) -> None:
        s = humanize(1638137981, 480, "BOGUS")
        assert s == "January 19, 1970, 3:02:17\u202fPM UTC"


@pytest.mark.asyncio
class TestAuthMiddlewareDirect:
    """Direct invocation tests so coverage can track lines through aiohttp middleware."""

    async def test_empty_token_after_strip(self) -> None:
        request = MagicMock()
        request.path = "/api/foo"
        request.headers = {"Authorization": "Bearer    "}
        resp = await auth_middleware(request, AsyncMock())
        assert resp.status == 401

    async def test_unauthorized_unknown_token(self, mocker: MockerFixture) -> None:
        mocker.patch("spellbot.web.builder.rate_limited", AsyncMock(return_value=False))
        request = MagicMock()
        request.path = "/api/foo"
        request.headers = {"Authorization": "Bearer BOGUS"}
        request.rel_url.path = "/api/foo"
        resp = await auth_middleware(request, AsyncMock())
        assert resp.status == 403

    async def test_rate_limited_unknown_token(self, mocker: MockerFixture) -> None:
        mocker.patch("spellbot.web.builder.rate_limited", AsyncMock(return_value=True))
        request = MagicMock()
        request.path = "/api/foo"
        request.headers = {"Authorization": "Bearer BOGUS"}
        request.rel_url.path = "/api/foo"
        resp = await auth_middleware(request, AsyncMock())
        assert resp.status == 429

    async def test_valid_token_calls_handler(self, factories: Factories) -> None:
        token = factories.token.create(key="VALID-KEY")
        handler = AsyncMock(return_value="handler-result")
        request = MagicMock()
        request.path = "/api/foo"
        request.headers = {"Authorization": f"Bearer {token.key}"}
        request.rel_url.path = "/api/foo"
        result = await auth_middleware(request, handler)
        assert result == "handler-result"
        handler.assert_awaited_once_with(request)
