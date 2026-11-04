# Copyright (c) 2026 spellbot@lexicalunit.com

"""An in-memory stand-in for Redis, for code that reaches it through `get_redis()`."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import TYPE_CHECKING

from spellbot import redis_client
from spellbot.settings import settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import pytest


class FakeRedis:
    """
    Covers the Redis commands SpellBot uses, keeping values in `data` and TTLs in `expiry`.

    Lua can't run here, so `eval` records each call in `evals` and answers with `eval_result`.
    Set `error` to make every command raise it, as when Redis goes down mid-request.
    """

    def __init__(
        self,
        *,
        data: dict[str, str] | None = None,
        eval_result: int | str = 1,
        error: BaseException | None = None,
    ) -> None:
        self.data: dict[str, str] = dict(data or {})
        self.expiry: dict[str, int | None] = {}
        self.evals: list[tuple[str | int, ...]] = []
        self.eval_result = eval_result
        self.error = error
        self.closed = False

    def check(self) -> None:
        if self.error is not None:
            raise self.error

    async def get(self, name: str) -> str | None:
        self.check()
        return self.data.get(name)

    async def set(self, name: str, value: str, ex: int | None = None) -> bool:
        self.check()
        self.data[name] = value
        self.expiry[name] = ex
        return True

    async def ping(self) -> bool:
        self.check()
        return True

    async def scan_iter(self, match: str) -> AsyncIterator[str]:
        self.check()
        for key in list(self.data):
            if fnmatchcase(key, match):
                yield key

    async def eval(self, script: str, numkeys: int, *keys_and_args: str) -> int | str:
        self.check()
        self.evals.append((script, numkeys, *keys_and_args))
        return self.eval_result

    async def aclose(self) -> None:
        self.closed = True


def serve_redis(monkeypatch: pytest.MonkeyPatch, redis: FakeRedis | BaseException) -> list[str]:
    """
    Point `get_redis()` at `redis`, or make connecting raise it, for the rest of the test.

    Sets `REDIS_URL` and starts without a cached client. Returns the URLs connected to, one per
    connection made, so a test can check that the client is shared.
    """
    connections: list[str] = []

    async def from_url(url: str) -> FakeRedis:
        connections.append(url)
        if isinstance(redis, BaseException):
            raise redis
        return redis

    monkeypatch.setattr(settings, "REDIS_URL", "redis://localhost")
    monkeypatch.setattr(redis_client.aioredis, "from_url", from_url)
    monkeypatch.setattr(redis_client.shared, "client", None)
    return connections
