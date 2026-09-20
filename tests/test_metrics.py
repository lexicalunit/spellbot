# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import httpx
from ddtrace.constants import ERROR_MSG, ERROR_TYPE

from spellbot.metrics import MAX_SPAN_ERROR_MSG, REPORTED_ERROR_TAG, span_error_tags


class TestSpanErrorTags:
    def test_reports_the_real_exception_type(self) -> None:
        tags = span_error_tags(httpx.ReadTimeout("took too long"))
        assert tags[ERROR_TYPE] == "ReadTimeout"

    def test_reports_the_real_message(self) -> None:
        tags = span_error_tags(ValueError("seatLimit must be at least 2"))
        assert tags[ERROR_MSG] == "seatLimit must be at least 2"

    def test_marks_the_span_as_a_reported_error(self) -> None:
        assert span_error_tags(ValueError("boom"))[REPORTED_ERROR_TAG] == "true"

    def test_falls_back_to_the_type_name_for_a_blank_message(self) -> None:
        tags = span_error_tags(httpx.ConnectError(""))
        assert tags[ERROR_MSG] == "ConnectError"

    def test_long_message_is_truncated(self) -> None:
        tags = span_error_tags(ValueError("y" * (MAX_SPAN_ERROR_MSG + 100)))
        assert tags[ERROR_MSG].count("y") == MAX_SPAN_ERROR_MSG
        assert tags[ERROR_MSG].endswith("… (truncated)")

    def test_message_at_limit_is_not_truncated(self) -> None:
        tags = span_error_tags(ValueError("y" * MAX_SPAN_ERROR_MSG))
        assert "(truncated)" not in tags[ERROR_MSG]

    def test_http_status_error_keeps_its_own_type(self) -> None:
        request = httpx.Request("POST", "https://api.convoke.games/api/game/create-game")
        response = httpx.Response(400, text="nope", request=request)
        ex = httpx.HTTPStatusError("400", request=request, response=response)
        tags = span_error_tags(ex)
        assert tags[ERROR_TYPE] == "HTTPStatusError"
        assert tags[ERROR_TYPE] != "OperationalError"
