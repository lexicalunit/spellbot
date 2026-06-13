from __future__ import annotations

import logging
import secrets
import time
from typing import TYPE_CHECKING, Literal, cast

from spellbot.redis_client import get_redis
from spellbot.settings import settings

if TYPE_CHECKING:
    from collections.abc import Awaitable

logger = logging.getLogger(__name__)

DMKind = Literal["start", "notification"]

DM_WINDOW_KEY_PREFIX = "dm:window:"


def window_key_for(kind: DMKind) -> str:
    return f"{DM_WINDOW_KEY_PREFIX}{kind}"


# Atomic sliding-window check-and-record. Trims entries older than ARGV[1]
# seconds, compares the remaining count against the kind-specific threshold
# in ARGV[3], records the current timestamp on success and returns 1, or
# leaves the set untouched and returns 0 on rejection.
DM_LIMIT_SCRIPT = """
local now = tonumber(ARGV[2])
local window = tonumber(ARGV[1])
local threshold = tonumber(ARGV[3])
local cutoff = now - window
redis.call("ZREMRANGEBYSCORE", KEYS[1], "-inf", cutoff)
local count = redis.call("ZCARD", KEYS[1])
if count >= threshold then
  return 0
end
redis.call("ZADD", KEYS[1], now, ARGV[4])
redis.call("EXPIRE", KEYS[1], window)
return 1
"""


def threshold_for(kind: DMKind) -> int:
    if kind == "notification":
        return settings.DM_NOTIFICATION_BUDGET
    return settings.DM_WINDOW_LIMIT


async def try_consume_dm_slot(kind: DMKind) -> bool:
    """
    Reserve a DM slot in the sliding window for the given priority.

    Returns True if the DM may proceed. "start" DMs are always allowed and
    bypass the rate limiter entirely since they are user-critical. For
    "notification" the limiter is fail-closed so a Redis outage cannot
    trigger a flood.
    """
    if kind == "start":
        return True

    if not settings.REDIS_URL:
        return False

    threshold = threshold_for(kind)
    if threshold <= 0:
        return False

    member = f"{time.time_ns()}:{secrets.token_hex(4)}"
    try:
        redis = await get_redis()
        result = await cast(
            "Awaitable[int]",
            redis.eval(
                DM_LIMIT_SCRIPT,
                1,
                window_key_for(kind),
                str(settings.DM_WINDOW_SECONDS),
                str(int(time.time())),
                str(threshold),
                member,
            ),
        )
    except Exception:
        logger.warning("redis error in dm rate limiter", exc_info=True)
        return False
    return int(result) == 1
