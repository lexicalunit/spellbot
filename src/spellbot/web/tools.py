# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from aiohttp import web

from spellbot.redis_client import get_redis
from spellbot.settings import settings

if TYPE_CHECKING:
    from collections.abc import Awaitable

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


def redirect(location: str) -> web.Response:
    """
    Build a 302 redirect response.

    Returning `web.HTTPFound` is deprecated by aiohttp and raising it would skip
    middlewares like `security_headers_middleware`, so return a plain response instead.
    """
    return web.Response(status=302, headers={"Location": location})


async def rate_limited(request: web.Request, key: str | None = None) -> bool:
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
