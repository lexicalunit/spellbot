# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from dataclasses import dataclass

from redis import asyncio as aioredis

from .settings import settings


# Process-wide Redis client, lazily created on first use and reused. The redis-py
# async client manages its own connection pool internally; creating a new client
# per request defeats the pool and pays a TCP/handshake cost every call.
@dataclass
class RedisHolder:
    client: aioredis.Redis | None = None


shared = RedisHolder()


async def get_redis() -> aioredis.Redis:
    if shared.client is None:
        assert settings.REDIS_URL is not None
        shared.client = await aioredis.from_url(settings.REDIS_URL)
    return shared.client


async def close_redis() -> None:
    if shared.client is not None:
        await shared.client.aclose()
    shared.client = None
