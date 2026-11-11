# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from aiohttp.test_utils import make_mocked_request
from ddtrace._trace.span import Span

from spellbot import metrics, redis_client
from spellbot.models import Game, User
from spellbot.redis_client import close_redis
from spellbot.settings import settings
from spellbot.web.tools import (
    MAX_PAGE,
    RATE_LIMIT,
    RATE_LIMIT_SCRIPT,
    TIME_WINDOW,
    already_rate_limited,
    is_crawler,
    parse_id,
    parse_page,
    rate_limited,
    route_id,
    tag_web_request,
    too_many_requests,
)
from tests.mocks.redis import FakeRedis, serve_redis

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from aiohttp import web
    from decoy import Decoy
    from sqlalchemy.orm import QueryableAttribute

    from tests.fixtures import Stub


@pytest_asyncio.fixture(autouse=True)
async def reset_redis_client() -> AsyncGenerator[None]:
    redis_client.shared.client = None
    yield
    await close_redis()


def request_from(remote: str, headers: dict[str, str] | None = None) -> web.Request:
    return make_mocked_request("GET", "/", headers=headers).clone(remote=remote)


@pytest.mark.asyncio
class TestRateLimited:
    async def test_no_redis_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that rate limiting is disabled when Redis URL is not configured."""
        monkeypatch.setattr(settings, "REDIS_URL", None)
        assert await rate_limited(request_from("192.168.1.1")) is False

    async def test_under_rate_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test request under rate limit."""
        serve_redis(monkeypatch, FakeRedis(eval_result="5"))
        assert await rate_limited(request_from("192.168.1.1")) is False

    async def test_over_rate_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test request over rate limit."""
        serve_redis(monkeypatch, FakeRedis(eval_result="15"))  # Over RATE_LIMIT of 10
        assert await rate_limited(request_from("192.168.1.1")) is True

    @pytest.mark.parametrize(("count", "expected"), [("20", False), ("21", True)])
    async def test_custom_limit(
        self,
        monkeypatch: pytest.MonkeyPatch,
        count: str,
        expected: bool,
    ) -> None:
        serve_redis(monkeypatch, FakeRedis(eval_result=count))
        assert await rate_limited(request_from("192.168.1.1"), limit=20) is expected

    async def test_keys_on_the_client_ip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        redis = FakeRedis(eval_result="1")
        serve_redis(monkeypatch, redis)
        await rate_limited(request_from("192.168.1.1"))
        [(script, numkeys, key, window)] = redis.evals
        assert (script, numkeys, key, window) == (
            RATE_LIMIT_SCRIPT,
            1,
            "rate_limit:192.168.1.1",
            str(TIME_WINDOW),
        )

    async def test_with_custom_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test rate limiting with custom key."""
        redis = FakeRedis(eval_result="3")
        serve_redis(monkeypatch, redis)
        assert await rate_limited(request_from("192.168.1.1"), key="custom:key") is False
        [(_script, _numkeys, key, _window)] = redis.evals
        assert key == "custom:key"

    async def test_redis_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that Redis errors are handled gracefully."""
        serve_redis(monkeypatch, FakeRedis(error=Exception("Redis error")))
        # Should return False on error (fail open)
        assert await rate_limited(request_from("192.168.1.1")) is False

    async def test_client_is_reused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Repeated calls share a single Redis client (one connection)."""
        connections = serve_redis(monkeypatch, FakeRedis(eval_result="1"))
        await rate_limited(request_from("192.168.1.1"))
        await rate_limited(request_from("192.168.1.1"))
        assert connections == ["redis://localhost"]


@pytest.mark.asyncio
class TestAlreadyRateLimited:
    async def test_no_redis_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "REDIS_URL", None)
        assert await already_rate_limited(request_from("192.168.1.1")) is False

    @pytest.mark.parametrize(
        ("count", "expected"),
        [(None, False), (str(RATE_LIMIT - 1), False), (str(RATE_LIMIT), True)],
    )
    async def test_reads_the_client_ips_count_without_adding_to_it(
        self,
        monkeypatch: pytest.MonkeyPatch,
        count: str | None,
        expected: bool,
    ) -> None:
        data = {} if count is None else {"rate_limit:192.168.1.1": count}
        redis = FakeRedis(data=data)
        serve_redis(monkeypatch, redis)
        assert await already_rate_limited(request_from("192.168.1.1")) is expected
        assert redis.evals == []
        assert redis.data == data

    async def test_custom_key_and_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        serve_redis(monkeypatch, FakeRedis(data={"custom:key": "3"}))
        request = request_from("192.168.1.1")
        assert await already_rate_limited(request, "custom:key", limit=3) is True
        assert await already_rate_limited(request, "custom:key", limit=4) is False

    async def test_redis_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        serve_redis(monkeypatch, FakeRedis(error=Exception("Redis error")))
        assert await already_rate_limited(request_from("192.168.1.1")) is False


class TestParseId:
    def test_accepts_ids_that_fit(self) -> None:
        assert parse_id("0", User.xid) == 0
        assert parse_id(str(2**63 - 1), User.xid) == 2**63 - 1
        assert parse_id(str(2**31 - 1), Game.id) == 2**31 - 1

    @pytest.mark.parametrize(
        ("raw", "column"),
        [
            pytest.param(str(2**63), User.xid, id="past-bigint"),
            pytest.param(str(2**31), Game.id, id="past-int"),
            pytest.param("9" * 5000, User.xid, id="too-many-digits"),
            pytest.param("", User.xid, id="empty"),
            pytest.param("-1", User.xid, id="negative"),
            pytest.param("+1", User.xid, id="plus"),
            pytest.param(" 1", User.xid, id="space"),
            pytest.param("1_000", User.xid, id="underscore"),
            pytest.param("²", User.xid, id="superscript"),
            pytest.param("١٢", User.xid, id="arabic-indic"),
        ],
    )
    def test_rejects_everything_else(self, raw: str, column: QueryableAttribute[int]) -> None:
        with pytest.raises(ValueError, match="id"):
            parse_id(raw, column)

    def test_route_id_uses_the_parameters_column(self) -> None:
        request = make_mocked_request("GET", "/", match_info={"game_id": str(2**31)})
        with pytest.raises(ValueError, match="out of range"):
            route_id(request, "game_id")
        request = make_mocked_request("GET", "/", match_info={"guild": str(2**31)})
        assert route_id(request, "guild") == 2**31


class TestParsePage:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (None, 0),
            ("", 0),
            ("3", 3),
            ("-3", 0),
            ("abc", 0),
            ("²", 0),
            (str(MAX_PAGE + 1), MAX_PAGE),
            ("9" * 5000, MAX_PAGE),
        ],
    )
    def test_parse_page(self, raw: str | None, expected: int) -> None:
        assert parse_page(raw) == expected


class TestTooManyRequests:
    def test_says_when_to_retry(self) -> None:
        resp = too_many_requests()
        assert resp.status == 429
        assert resp.headers["Retry-After"] == str(TIME_WINDOW)


class TestIsCrawler:
    @pytest.mark.parametrize(
        "user_agent",
        [
            "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ShapBot/0.1.0",
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
            "Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)",
            "Sogou web spider/4.0",
            "CCBot/2.0 (https://commoncrawl.org/faq/)",
            (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) HeadlessChrome/139.0.0.0 Safari/537.36"
            ),
            "python-requests/2.32.3",
            "curl/8.7.1",
        ],
    )
    def test_crawler(self, user_agent: str) -> None:
        assert is_crawler(request_from("192.168.1.1", {"User-Agent": user_agent}))

    @pytest.mark.parametrize(
        "user_agent",
        [
            (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/605.1.15"
            ),
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
            (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
                "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
            ),
            "",
        ],
    )
    def test_not_crawler(self, user_agent: str) -> None:
        assert not is_crawler(request_from("192.168.1.1", {"User-Agent": user_agent}))

    def test_missing_user_agent(self) -> None:
        assert not is_crawler(request_from("192.168.1.1"))


class TestTagWebRequest:
    def test_tags_client_ip(self, decoy: Decoy, stub: Stub) -> None:
        span = decoy.mock(cls=Span)
        current_span = stub(metrics.tracer, "current_span")
        decoy.when(current_span()).then_return(span)
        tag_web_request(request_from("203.0.113.7"))
        decoy.verify(span.set_tags({"client_ip": "203.0.113.7"}), times=1)
