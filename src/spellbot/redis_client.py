from __future__ import annotations

from redis import asyncio as aioredis

from .settings import settings

# Process-wide Redis client, lazily created on first use and reused. The redis-py
# async client manages its own connection pool internally; creating a new client
# per request defeats the pool and pays a TCP/handshake cost every call.
_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis_client  # noqa: PLW0603
    if _redis_client is None:
        assert settings.REDIS_URL is not None
        _redis_client = await aioredis.from_url(settings.REDIS_URL)
    return _redis_client


async def close_redis() -> None:
    global _redis_client  # noqa: PLW0603
    if _redis_client is not None:
        await _redis_client.aclose()
    _redis_client = None
