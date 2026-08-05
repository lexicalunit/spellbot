from __future__ import annotations

from typing import TYPE_CHECKING

from redis import asyncio as aioredis
from redis.exceptions import RedisError

from .settings import settings

if TYPE_CHECKING:
    import logging

# Process-wide Redis client, lazily created on first use and reused. The redis-py
# async client manages its own connection pool internally; creating a new client
# per request defeats the pool and pays a TCP/handshake cost every call.
_redis_client: aioredis.Redis | None = None


def log_redis_failure(logger: logging.Logger, what: str, ex: BaseException) -> None:
    """
    Log a Redis failure at a volume that matches how much it actually matters.

    Every Redis call site in this codebase is fail-open: when Redis is unreachable the
    feature degrades (no rate limiting, no shard status) and the caller carries on. A
    stack trace for that reads like an unhandled fault, buries real errors, and — since
    these paths run per request or on a short loop — repeats endlessly whenever Redis is
    simply not running, which is the normal state in local development. So a connection
    or timeout failure gets one concise line. Anything else is genuinely unexpected and
    keeps its traceback.
    """
    if isinstance(ex, RedisError | OSError):
        logger.warning("%s unavailable: %s", what, ex)
    else:
        # Pass the exception explicitly rather than relying on `exc_info=True` picking up
        # ambient handler state, since this runs a frame below the `except` that caught it.
        logger.warning("unexpected error in %s", what, exc_info=ex)


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
