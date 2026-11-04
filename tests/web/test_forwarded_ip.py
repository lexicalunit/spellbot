# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from multidict import CIMultiDict

from spellbot.settings import settings
from spellbot.web.builder import forwarded_client_ip, forwarded_ip_middleware

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def make_request(*forwarded: str) -> web.Request:
    headers = CIMultiDict(("X-Forwarded-For", value) for value in forwarded)
    return make_mocked_request("GET", "/", headers=headers)


class TestForwardedClientIp:
    @pytest.mark.parametrize(
        ("forwarded", "hops", "expected"),
        [
            pytest.param(("203.0.113.7",), 1, "203.0.113.7", id="single"),
            pytest.param(("1.1.1.1, 203.0.113.7",), 1, "203.0.113.7", id="ignores-spoofed"),
            pytest.param(("1.1.1.1", "203.0.113.7"), 1, "203.0.113.7", id="repeated-header"),
            pytest.param(("1.1.1.1, 203.0.113.7, 10.0.0.2",), 2, "203.0.113.7", id="two-hops"),
            pytest.param(("203.0.113.7",), 2, "203.0.113.7", id="fewer-than-hops"),
            pytest.param(("2001:db8::1",), 1, "2001:db8::1", id="ipv6"),
            pytest.param((), 1, None, id="missing"),
            pytest.param((" , ",), 1, None, id="empty-entries"),
            pytest.param(("not-an-ip",), 1, None, id="garbage"),
        ],
    )
    def test_forwarded_client_ip(
        self,
        forwarded: tuple[str, ...],
        hops: int,
        expected: str | None,
    ) -> None:
        assert forwarded_client_ip(make_request(*forwarded), hops) == expected


@pytest.mark.asyncio
class TestForwardedIpMiddleware:
    async def remote_seen_by_handler(self, request: web.Request) -> str | None:
        seen: list[str | None] = []

        async def handler(req: web.Request) -> web.StreamResponse:
            seen.append(req.remote)
            return web.Response()

        await forwarded_ip_middleware(request, handler)
        return seen[0]

    async def test_uses_forwarded_ip_when_trusted(self, mocker: MockerFixture) -> None:
        mocker.patch.object(settings, "TRUSTED_PROXY_HOPS", 1)
        request = make_request("1.1.1.1, 203.0.113.7")
        assert await self.remote_seen_by_handler(request) == "203.0.113.7"

    async def test_ignores_header_when_no_trusted_proxies(self, mocker: MockerFixture) -> None:
        mocker.patch.object(settings, "TRUSTED_PROXY_HOPS", 0)
        request = make_request("203.0.113.7")
        assert await self.remote_seen_by_handler(request) == request.remote

    async def test_keeps_remote_without_usable_header(self, mocker: MockerFixture) -> None:
        mocker.patch.object(settings, "TRUSTED_PROXY_HOPS", 1)
        request = make_request("not-an-ip")
        assert await self.remote_seen_by_handler(request) == request.remote
