from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from packaging.version import parse as parse_version
from redis import asyncio as aioredis

from spellbot import __version__

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
    version: str  # Bot version running this shard

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
            version=str(data.get("version", "unknown")),
        )


async def update_shard_status(bot: SpellBot) -> None:
    """Update shard status information in Redis."""
    if not settings.REDIS_URL:
        logger.debug("REDIS_URL not configured, skipping shard status update")
        return

    try:
        redis = await aioredis.from_url(settings.REDIS_URL)

        shard_count = bot.shard_count or 1
        shard_ids = list(bot.shards.keys()) if bot.shards else [0]

        logger.info(
            "update_shard_status: shard_count=%s, shard_ids=%s, ready_shards=%s",
            shard_count,
            shard_ids,
            bot.ready_shards,
        )

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
                version=__version__,
            )

            # Include version in key so multiple versions can coexist during rolling deployments
            key = f"{SHARD_STATUS_PREFIX}{shard_id}:{__version__}"
            await redis.set(key, json.dumps(status.to_dict()), ex=SHARD_STATUS_TTL)

        # Also store metadata about total shards
        # Only update version if current version is greater than stored version
        # This prevents version flip-flopping during rolling deployments
        current_version = parse_version(__version__)
        metadata_key = f"{SHARD_STATUS_PREFIX}metadata"
        existing_metadata_raw = await redis.get(metadata_key)
        existing_version_str = None
        if existing_metadata_raw:
            existing_metadata = json.loads(existing_metadata_raw)
            existing_version_str = existing_metadata.get("version")

        # Determine which version to write
        version_to_write = __version__
        if existing_version_str:
            try:
                if parse_version(existing_version_str) > current_version:
                    version_to_write = existing_version_str
            except Exception:
                logger.debug(
                    "Failed to parse existing version %r, using current",
                    existing_version_str,
                )

        metadata = {
            "version": version_to_write,
            "shard_count": shard_count,
            "total_guilds": len(bot.guilds),
            "last_updated": datetime.now(tz=UTC).isoformat(),
        }
        await redis.set(metadata_key, json.dumps(metadata), ex=SHARD_STATUS_TTL)

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

        # Get all shard status keys (pattern: shard_status:{shard_id}:{version})
        keys = [key async for key in redis.scan_iter(match=f"{SHARD_STATUS_PREFIX}[0-9]*:*")]

        statuses: list[ShardStatus] = []
        for key in keys:
            data = await redis.get(key)
            if data:
                statuses.append(ShardStatus.from_dict(json.loads(data)))

        await redis.aclose()

        # Sort by shard_id, then by version (newest first)
        statuses.sort(
            key=lambda s: (
                s.shard_id,
                parse_version(s.version) if s.version != "unknown" else parse_version("0.0.0"),
            ),
        )

    except Exception:
        logger.warning("Failed to get shard statuses from Redis", exc_info=True)
        return [], None
    else:
        return statuses, metadata
