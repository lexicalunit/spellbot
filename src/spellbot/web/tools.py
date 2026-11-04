# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING, cast

from aiohttp import web
from crawlerdetect import CrawlerDetect
from ddtrace.trace import tracer

from spellbot.database import db_session_manager
from spellbot.metrics import add_span_request_id, generate_request_id, tag_span
from spellbot.redis_client import get_redis
from spellbot.settings import settings

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

RATE_LIMIT = 10  # attempts
TIME_WINDOW = 60  # seconds
RATE_LIMIT_SCRIPT = """
local current
current = redis.call("INCR", KEYS[1])
if tonumber(current) == 1 then
  redis.call("EXPIRE", KEYS[1], ARGV[1])
end
return current
"""

# Shared across requests: `is_crawler` doesn't await between matching and returning,
# so the detector's per-call match state can't interleave between requests.
crawler_detect = CrawlerDetect()


def redirect(location: str) -> web.Response:
    """
    Build a 302 redirect response.

    Returning `web.HTTPFound` is deprecated by aiohttp and raising it would skip
    the middlewares, so return a plain response instead.
    """
    return web.Response(status=302, headers={"Location": location})


def tag_web_request(request: web.Request) -> None:
    """
    Tag the current web span with a fresh request id and the client's IP.

    Behind the load balancer `request.remote` is the forwarded client address (see
    `forwarded_ip_middleware`), which is also what the rate limiter keys on.
    """
    add_span_request_id(generate_request_id())
    tag_span(client_ip=request.remote)


def is_crawler(request: web.Request) -> bool:
    """Whether the request comes from a self-identified crawler."""
    return crawler_detect.is_crawler(request.headers.get("User-Agent", ""))


async def rate_limited(request: web.Request, key: str | None = None) -> bool:
    """
    Count this request against `key` (default: the client IP) and report if it's over.

    Without Redis, whether unconfigured or erroring, there's no limit: an outage
    shouldn't take the API down with it.
    """
    if not settings.REDIS_URL:
        return False

    ip = request.remote
    key = key or f"rate_limit:{ip}"

    try:
        redis = await get_redis()
        resp = await cast(
            "Awaitable[str]",
            redis.eval(RATE_LIMIT_SCRIPT, 1, key, str(TIME_WINDOW)),
        )
    except Exception:
        logger.warning("redis error in rate limiter", exc_info=True)
        return False
    return int(resp) > RATE_LIMIT


type Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


def web_endpoint(resource: str) -> Callable[[Handler], Handler]:
    """Trace a route as the `web` span `resource`, tagged with a request id, in a DB session."""

    def decorate(handler: Handler) -> Handler:
        @functools.wraps(handler)
        async def endpoint(request: web.Request) -> web.StreamResponse:
            tag_web_request(request)
            async with db_session_manager():
                return await handler(request)

        return tracer.wrap(name="web", resource=resource)(endpoint)

    return decorate
