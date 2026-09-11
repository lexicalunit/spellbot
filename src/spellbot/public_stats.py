# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from spellbot import services
from spellbot.database import db_session_manager
from spellbot.redis_client import get_redis

from .settings import settings

logger = logging.getLogger(__name__)

# Redis key holding the most recently computed public stats.
PUBLIC_STATS_KEY = "public_stats"

# Deliberately several times longer than the refresh interval. The task recomputes
# every `PUBLIC_STATS_LOOP_M` minutes, so a longer TTL means a transient failure
# (or a bot restart) shows slightly stale numbers instead of an empty widget. The
# payload carries `last_updated` so consumers can judge staleness themselves.
PUBLIC_STATS_TTL = 1800


@dataclass
class PublicStats:
    """Aggregate activity counts safe to expose publicly."""

    active_servers: int
    active_players: int
    active_games: int
    last_updated: str  # ISO format timestamp

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PublicStats:
        return cls(
            active_servers=int(data["active_servers"]),
            active_players=int(data["active_players"]),
            active_games=int(data["active_games"]),
            last_updated=str(data["last_updated"]),
        )


async def compute_public_stats() -> PublicStats:
    """
    Compute current activity counts from the database.

    Counts are derived from the same service calls that back the queues page, so
    the numbers shown on spellbot.io always agree with what a visitor sees after
    clicking through. A player in a pending queue and a player seated in a game
    that just started both count as active; started games are full, so their seat
    count is the player count.
    """
    async with db_session_manager():
        queues = await services.queues.public_active_queues()
        games = await services.queues.public_active_games(
            services.queues.STARTED_GAMES_WINDOW,
        )

    servers = {row["guild_xid"] for row in queues} | {game["guild_xid"] for game in games}
    players = sum(row["players"] for row in queues) + sum(game["seats"] for game in games)

    return PublicStats(
        active_servers=len(servers),
        active_players=players,
        active_games=len(queues) + len(games),
        last_updated=datetime.now(tz=UTC).isoformat(),
    )


async def update_public_stats() -> None:
    """Recompute public stats and write them to Redis."""
    if not settings.REDIS_URL:
        logger.debug("REDIS_URL not configured, skipping public stats update")
        return

    try:
        stats = await compute_public_stats()
        redis = await get_redis()
        await redis.set(PUBLIC_STATS_KEY, json.dumps(stats.to_dict()), ex=PUBLIC_STATS_TTL)
    except Exception:
        # Never propagate: this runs on a task loop and a failed refresh should
        # leave the last good value in place rather than kill the loop.
        logger.warning("Failed to update public stats in Redis", exc_info=True)
    else:
        logger.debug("Updated public stats: %s", stats.to_dict())


async def get_public_stats() -> PublicStats | None:
    """
    Read the cached public stats from Redis.

    Returns `None` when Redis is unconfigured, empty, or unreachable. Callers are
    expected to degrade gracefully rather than fall back to querying the database:
    this endpoint exists specifically to keep marketing-site traffic off the DB.
    """
    if not settings.REDIS_URL:
        return None

    try:
        redis = await get_redis()
        raw = await redis.get(PUBLIC_STATS_KEY)
        if not raw:
            return None
        return PublicStats.from_dict(json.loads(raw))
    except Exception:
        logger.warning("Failed to get public stats from Redis", exc_info=True)
        return None
