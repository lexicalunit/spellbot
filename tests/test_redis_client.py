from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from spellbot.redis_client import log_redis_failure

if TYPE_CHECKING:
    import pytest


class TestLogRedisFailure:
    def test_connection_error_is_one_concise_line(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Redis being down is a fail-open condition the caller handles, so it must not
        # produce a stack trace: that reads as an unhandled fault and, on a per-request
        # path, repeats endlessly whenever Redis simply is not running.
        ex = RedisConnectionError("Error 61 connecting to localhost:6380. Connection refused.")
        with caplog.at_level(logging.DEBUG):
            log_redis_failure(logging.getLogger("test"), "rate limiter", ex)

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelno == logging.WARNING
        assert record.exc_info is None
        assert "rate limiter unavailable" in record.getMessage()
        assert "Connection refused" in record.getMessage()

    def test_timeout_is_also_concise(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG):
            log_redis_failure(logging.getLogger("test"), "dm rate limiter", RedisTimeoutError())
        assert caplog.records[0].exc_info is None

    def test_raw_socket_error_is_also_concise(self, caplog: pytest.LogCaptureFixture) -> None:
        # A `ConnectionRefusedError` can reach us unwrapped; it means the same thing.
        ex = ConnectionRefusedError(61, "Connection refused")
        with caplog.at_level(logging.DEBUG):
            log_redis_failure(logging.getLogger("test"), "shard status update", ex)
        assert caplog.records[0].exc_info is None
        assert "shard status update unavailable" in caplog.records[0].getMessage()

    def test_unexpected_error_keeps_its_traceback(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Anything that is not a connectivity problem is a real bug we want to see.
        ex = ValueError("something we did not anticipate")
        with caplog.at_level(logging.DEBUG):
            log_redis_failure(logging.getLogger("test"), "rate limiter", ex)

        record = caplog.records[0]
        assert record.levelno == logging.WARNING
        assert record.exc_info is not None
        assert record.exc_info[1] is ex
        assert "unexpected error in rate limiter" in record.getMessage()
