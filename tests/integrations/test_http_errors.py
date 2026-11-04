# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import httpx
import pytest

from spellbot.integrations import http_errors
from spellbot.integrations.http_errors import (
    MAX_BODY_CHARS,
    Integration,
    describe_http_error,
    is_terminal_client_error,
    request_with_retries,
)
from tests import REPO_ROOT
from tests.mocks.http import raising, serve_httpx

if TYPE_CHECKING:
    from tests.fixtures import Stub


def status_error(
    status: int,
    body: str = "",
    url: str = "https://api.example.com/thing",
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


class TestDescribeUnreadBody:
    def test_unread_streaming_body(self) -> None:
        request = httpx.Request("GET", "https://api.example.com/thing")
        response = httpx.Response(500, request=request, stream=httpx.ByteStream(b"never read"))
        ex = httpx.HTTPStatusError("500", request=request, response=response)
        assert describe_http_error(ex).endswith(": <unavailable>")


MONITORS = REPO_ROOT / "infrastructure" / "o11y" / "main.tf"


class TestIntegration:
    def test_about_marks_logs_with_the_integration(self) -> None:
        assert Integration.PLAYGROUP_LIVE.about() == {"integration": "Playgroup Live"}

    def test_every_integration_has_a_monitor(self) -> None:
        source = MONITORS.read_text()
        windows = source[source.index("integration_failure_windows = {") :]
        windows = windows[: windows.index("}")]
        monitored = set(re.findall(r'^\s*"([^"]+)"\s*=', windows, re.MULTILINE))
        assert monitored == {integration.value for integration in Integration}


@pytest.mark.asyncio
class TestRequestWithRetries:
    async def test_failures_are_logged_about_the_integration(
        self,
        monkeypatch: pytest.MonkeyPatch,
        stub: Stub,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        stub(http_errors, "add_span_error")
        serve_httpx(monkeypatch, raising())

        async def request(client: httpx.AsyncClient) -> httpx.Response:
            return await client.get("https://api.example.com/thing")

        result = await request_with_retries(
            Integration.CASTLOG,
            request,
            attempts=2,
            timeout_s=1,
        )

        assert result is None
        retry, failure = caplog.records
        assert (retry.levelname, retry.getMessage()) == (
            "WARNING",
            "Castlog API issue (attempt 1). ",
        )
        assert (failure.levelname, failure.getMessage()) == ("ERROR", "Castlog API failure. ")
        assert retry.__dict__["integration"] == failure.__dict__["integration"] == "Castlog"
