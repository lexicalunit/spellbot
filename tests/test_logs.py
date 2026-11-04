# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import json
import logging
from typing import NoReturn

import pytest
from aiohttp.http_exceptions import BadHttpMethod
from gunicorn.config import Config

from spellbot.logs import JsonGunicornLogger, demote_bad_requests


def raised[E: BaseException](error: E) -> E:
    """Return `error` after raising it, so it carries a real traceback."""

    def fail() -> NoReturn:
        raise error

    with pytest.raises(type(error)) as caught:
        fail()
    return caught.value


def logged_lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, str]]:
    """Return what gunicorn's error log wrote to stderr, one JSON record per line."""
    return [json.loads(line) for line in capsys.readouterr().err.splitlines()]


class TestJsonGunicornLogger:
    def test_logs_a_traceback_as_one_json_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger = JsonGunicornLogger(Config())
        error = raised(RuntimeError("boom"))
        logger.error("Error handling request from %s", "203.0.113.7", exc_info=error)

        [record] = logged_lines(capsys)
        assert record["status"] == "ERROR"
        assert record["message"] == "Error handling request from 203.0.113.7"
        assert record["exc_info"].startswith("Traceback (most recent call last):")
        assert record["exc_info"].endswith("RuntimeError: boom")

    def test_logs_malformed_requests_as_warnings(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        logger = JsonGunicornLogger(Config())
        error = raised(BadHttpMethod("NUIU"))
        logger.error("Error handling request from %s", "203.0.113.7", exc_info=error)

        [record] = logged_lines(capsys)
        assert record["status"] == "WARNING"
        assert "BadHttpMethod" in record["exc_info"]

    def test_logs_info_unchanged(self, capsys: pytest.CaptureFixture[str]) -> None:
        JsonGunicornLogger(Config()).info("Booting worker with pid: %s", 42)

        [record] = logged_lines(capsys)
        assert (record["status"], record["message"]) == ("INFO", "Booting worker with pid: 42")


class TestDemoteBadRequests:
    def record(self, level: int, exc: BaseException | None) -> logging.LogRecord:
        exc_info = (type(exc), exc, None) if exc else None
        return logging.LogRecord("gunicorn.error", level, __file__, 1, "msg", (), exc_info)

    def test_demotes_malformed_request_errors(self) -> None:
        record = self.record(logging.ERROR, BadHttpMethod("NUIU"))
        assert demote_bad_requests(record)
        assert (record.levelno, record.levelname) == (logging.WARNING, "WARNING")

    @pytest.mark.parametrize(
        ("level", "exc"),
        [
            pytest.param(logging.ERROR, RuntimeError("boom"), id="other-errors"),
            pytest.param(logging.ERROR, None, id="no-exception"),
            pytest.param(logging.INFO, BadHttpMethod("NUIU"), id="already-quieter"),
        ],
    )
    def test_leaves_other_records_alone(self, level: int, exc: BaseException | None) -> None:
        record = self.record(level, exc)
        assert demote_bad_requests(record)
        assert record.levelno == level
