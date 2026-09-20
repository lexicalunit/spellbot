# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import httpx
import pytest

from spellbot.integrations.http_errors import (
    MAX_BODY_CHARS,
    describe_http_error,
    is_terminal_client_error,
)


def status_error(
    status: int, body: str = "", url: str = "https://api.example.com/thing"
) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", url)
    response = httpx.Response(status, text=body, request=request)
    return httpx.HTTPStatusError(f"{status}", request=request, response=response)


class TestIsTerminalClientError:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            pytest.param(400, True, id="bad_request"),
            pytest.param(401, True, id="unauthorized"),
            pytest.param(403, True, id="forbidden"),
            pytest.param(404, True, id="not_found"),
            pytest.param(422, True, id="unprocessable"),
            pytest.param(499, True, id="upper_4xx"),
            pytest.param(408, False, id="request_timeout_is_retryable"),
            pytest.param(429, False, id="rate_limited_is_retryable"),
            pytest.param(500, False, id="server_error"),
            pytest.param(503, False, id="service_unavailable"),
            pytest.param(200, False, id="success"),
            pytest.param(399, False, id="below_4xx"),
        ],
    )
    def test_status_codes(self, status: int, expected: bool) -> None:
        assert is_terminal_client_error(status_error(status)) is expected

    def test_non_http_error(self) -> None:
        assert is_terminal_client_error(httpx.ReadTimeout("slow")) is False

    def test_arbitrary_exception(self) -> None:
        assert is_terminal_client_error(ValueError("nope")) is False


class TestDescribeHttpError:
    def test_includes_status_url_and_body(self) -> None:
        ex = status_error(400, body='{"error":"invalid_body","details":"seatLimit"}')
        described = describe_http_error(ex)
        assert "HTTP 400" in described
        assert "https://api.example.com/thing" in described
        assert "seatLimit" in described

    def test_empty_body(self) -> None:
        assert "<empty body>" in describe_http_error(status_error(404, body=""))

    def test_whitespace_only_body_reads_as_empty(self) -> None:
        assert "<empty body>" in describe_http_error(status_error(404, body="   \n  "))

    def test_long_body_is_truncated(self) -> None:
        ex = status_error(400, body="y" * (MAX_BODY_CHARS + 500))
        described = describe_http_error(ex)
        assert "(truncated)" in described
        assert described.count("y") == MAX_BODY_CHARS

    def test_body_at_limit_is_not_truncated(self) -> None:
        ex = status_error(400, body="y" * MAX_BODY_CHARS)
        assert "(truncated)" not in describe_http_error(ex)

    def test_non_http_error_returns_empty_string(self) -> None:
        assert describe_http_error(httpx.ReadTimeout("slow")) == ""

    def test_arbitrary_exception_returns_empty_string(self) -> None:
        assert describe_http_error(ValueError("nope")) == ""
