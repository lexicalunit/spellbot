from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from redis import asyncio as aioredis

from spellbot.settings import settings

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from aiohttp import web

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


async def rate_limited(request: web.Request, key: str | None = None) -> bool:
    if not settings.REDIS_URL:
        return False

    redis = await aioredis.from_url(settings.REDIS_URL)
    ip = request.remote
    key = key or f"rate_limit:{ip}"

    try:
        resp = await cast(
            "Awaitable[str]",
            redis.eval(RATE_LIMIT_SCRIPT, 1, key, str(TIME_WINDOW)),
        )
        count = int(resp)
    except Exception:
        logger.warning("redis error in rate limiter", exc_info=True)
        return False

    return count > RATE_LIMIT
