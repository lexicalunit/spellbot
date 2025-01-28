from __future__ import annotations

from typing import TYPE_CHECKING

from redis import asyncio as aioredis

from spellbot.settings import settings

if TYPE_CHECKING:
    from aiohttp import web

RATE_LIMIT = 10  # attempts
TIME_WINDOW = 60  # seconds


async def rate_limited(request: web.Request, key: str | None = None) -> bool:
    try:
        redis = await aioredis.from_url(settings.REDISCLOUD_URL)
        ip = request.remote
        key = key or f"rate_limit:{ip}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, TIME_WINDOW)
    except Exception:
        return False
    return count > RATE_LIMIT
