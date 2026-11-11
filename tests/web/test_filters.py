# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from spellbot.web import builder, humanize
from spellbot.web.builder import auth_middleware
from tests.mocks import decoys

if TYPE_CHECKING:
    from decoy import Decoy

    from tests.fixtures import Factories, Stub

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestWebFilters:
    async def test_humanize_happy_path(self) -> None:
        s = humanize(1638137981, 480, "America/Los_Angeles")
        assert s == "January 19, 1970, 3:02:17\u202fPM PST"

    async def test_humanize_bogus_timezone(self) -> None:
        s = humanize(1638137981, 480, "BOGUS")
        assert s == "January 19, 1970, 3:02:17\u202fPM UTC"


OK = web.Response(text="ok")


def api_request(authorization: str) -> web.Request:
    return make_mocked_request("GET", "/api/foo", headers={"Authorization": authorization})


# For requests the middleware turns away, which must never reach the handler.
UNREACHABLE = decoys.async_raising(AssertionError("request reached the handler"))


@pytest.mark.asyncio
class TestAuthMiddlewareDirect:
    """Direct invocation tests so coverage can track lines through aiohttp middleware."""

    async def test_empty_token_after_strip(self) -> None:
        request = api_request("Bearer    ")
        resp = await auth_middleware(request, UNREACHABLE)
        assert resp.status == 401

    async def test_unauthorized_unknown_token(self, decoy: Decoy, stub: Stub) -> None:
        request = api_request("Bearer BOGUS")
        rate_limited_fake = stub(builder, "rate_limited")
        decoy.when(await rate_limited_fake(request)).then_return(False)
        resp = await auth_middleware(request, UNREACHABLE)
        assert resp.status == 403

    async def test_rate_limited_unknown_token(self, decoy: Decoy, stub: Stub) -> None:
        request = api_request("Bearer BOGUS")
        rate_limited_fake = stub(builder, "rate_limited")
        decoy.when(await rate_limited_fake(request)).then_return(True)
        resp = await auth_middleware(request, UNREACHABLE)
        assert resp.status == 429

    async def test_refused_before_the_token_lookup_once_over_the_limit(
        self,
        factories: Factories,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Even a valid token: the limiter answers before the database is asked.
        factories.token.create(key="VALID-KEY")
        monkeypatch.setattr(builder, "already_rate_limited", decoys.async_returning(True))
        monkeypatch.setattr(builder.services.apps, "verify_token", UNREACHABLE)
        resp = await auth_middleware(api_request("Bearer VALID-KEY"), UNREACHABLE)
        assert resp.status == 429

    async def test_valid_token_calls_handler(self, factories: Factories, decoy: Decoy) -> None:
        factories.token.create(key="VALID-KEY")
        request = api_request("Bearer VALID-KEY")
        handler = decoy.mock(name="handler", is_async=True)
        decoy.when(await handler(request)).then_return(OK)
        assert await auth_middleware(request, handler) is OK
