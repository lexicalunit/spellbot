from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from redis import asyncio as aioredis

from .settings import settings

if TYPE_CHECKING:
    from spellbot import SpellBot

logger = logging.getLogger(__name__)

# Redis key prefix for shard status
SHARD_STATUS_PREFIX = "shard_status:"
# TTL for shard status keys (2 minutes - if not updated, considered stale)
SHARD_STATUS_TTL = 120


@dataclass
class ShardStatus:
    """Status information for a single shard."""

    shard_id: int
    latency_ms: float | None  # Latency in milliseconds, None if unavailable
    guild_count: int
    is_ready: bool
    last_updated: str  # ISO format timestamp

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShardStatus:
        latency = data.get("latency_ms")
        return cls(
            shard_id=int(data["shard_id"]),
            latency_ms=float(latency) if latency is not None else None,
            guild_count=int(data["guild_count"]),
            is_ready=bool(data["is_ready"]),
            last_updated=str(data["last_updated"]),
        )


async def update_shard_status(bot: SpellBot) -> None:
    """Update shard status information in Redis."""
    if not settings.REDIS_URL:
        logger.debug("REDIS_URL not configured, skipping shard status update")
        return

    try:
        redis = await aioredis.from_url(settings.REDIS_URL)

        # Get shard count - if not sharded, treat as single shard
        shard_count = bot.shard_count or 1
        shard_ids = bot.shard_ids or [0]

        for shard_id in shard_ids:
            # Calculate latency for this shard
            latency = bot.get_shard(shard_id)
            latency_ms = None
            if latency is not None and latency.latency is not None:
                latency_ms = round(latency.latency * 1000, 2)

            # Count guilds for this shard
            guild_count = sum(1 for g in bot.guilds if g.shard_id == shard_id)

            # Check if shard is ready (tracked via on_shard_ready/on_shard_disconnect events)
            is_ready = shard_id in bot.ready_shards

            status = ShardStatus(
                shard_id=shard_id,
                latency_ms=latency_ms,
                guild_count=guild_count,
                is_ready=is_ready,
                last_updated=datetime.now(tz=UTC).isoformat(),
            )

            key = f"{SHARD_STATUS_PREFIX}{shard_id}"
            await redis.set(key, json.dumps(status.to_dict()), ex=SHARD_STATUS_TTL)

        # Also store metadata about total shards
        metadata = {
            "shard_count": shard_count,
            "total_guilds": len(bot.guilds),
            "last_updated": datetime.now(tz=UTC).isoformat(),
        }
        await redis.set(f"{SHARD_STATUS_PREFIX}metadata", json.dumps(metadata), ex=SHARD_STATUS_TTL)

        await redis.aclose()
        logger.debug("Updated shard status for %d shards", shard_count)

    except Exception:
        logger.warning("Failed to update shard status in Redis", exc_info=True)


async def get_all_shard_statuses() -> tuple[list[ShardStatus], dict[str, object] | None]:
    """
    Retrieve all shard statuses from Redis.

    Returns a tuple of (list of ShardStatus, metadata dict or None).
    """
    if not settings.REDIS_URL:
        return [], None

    try:
        redis = await aioredis.from_url(settings.REDIS_URL)

        # Get metadata first
        metadata_raw = await redis.get(f"{SHARD_STATUS_PREFIX}metadata")
        metadata = json.loads(metadata_raw) if metadata_raw else None

        # Get all shard status keys
        keys = [key async for key in redis.scan_iter(match=f"{SHARD_STATUS_PREFIX}[0-9]*")]

        statuses: list[ShardStatus] = []
        for key in keys:
            data = await redis.get(key)
            if data:
                statuses.append(ShardStatus.from_dict(json.loads(data)))

        await redis.aclose()

        # Sort by shard_id
        statuses.sort(key=lambda s: s.shard_id)

    except Exception:
        logger.warning("Failed to get shard statuses from Redis", exc_info=True)
        return [], None
    else:
        return statuses, metadata
