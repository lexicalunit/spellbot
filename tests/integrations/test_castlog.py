# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest

import spellbot.integrations.castlog as castlog_module
from spellbot.integrations import http_errors
from spellbot.integrations.castlog import fetch_castlog_report, report_match
from tests.mocks import decoys
from tests.mocks.http import client_for, in_order, serve_httpx

if TYPE_CHECKING:
    from tests.fixtures import Stub

ENDPOINT = "https://dev.api.castlog.gg/functions/v1/spellbot-webhook"


@pytest.fixture(autouse=True)
def castlog_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(castlog_module.settings, "CASTLOG_SECRET", "test-secret")
    monkeypatch.setattr(castlog_module.settings, "CASTLOG_ENDPOINT", ENDPOINT)


@pytest.fixture
def quiet_span_errors(stub: Stub) -> None:
    stub(http_errors, "add_span_error")


@pytest.mark.asyncio
class TestFetchCastlogReport:
    async def test_fetch_castlog_report_success(self) -> None:
        report = {
            "match_id": "abc-123",
            "castlog_url": "https://app.castlog.gg/match/abc-123",
            "linked_players": ["ravepool"],
            "unlinked_players": [],
        }
        requests: list[httpx.Request] = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=report)

        payload = {"players": [{"xid": 1, "commander": "Atraxa", "is_winner": True}]}
        result = await fetch_castlog_report(client_for(respond), payload)

        assert result == report
        [request] = requests
        assert (request.method, str(request.url)) == ("POST", ENDPOINT)
        assert json.loads(request.content) == payload
        assert request.headers["X-SpellBot-Secret"] == "test-secret"


@pytest.mark.asyncio
class TestReportMatch:
    async def test_report_match_no_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(castlog_module.settings, "CASTLOG_ENDPOINT", "")
        assert await report_match({"players": []}) is None

    async def test_report_match_no_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(castlog_module.settings, "CASTLOG_SECRET", None)
        assert await report_match({"players": []}) is None

    async def test_report_match_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        serve_httpx(monkeypatch, in_order(httpx.Response(200, json={"match_id": "abc-123"})))
        payload = {"players": [{"xid": 1, "commander": "Atraxa"}]}
        assert await report_match(payload) == {"match_id": "abc-123"}

    @pytest.mark.usefixtures("quiet_span_errors")
    async def test_report_match_retries_on_failure_then_succeeds(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        requests = serve_httpx(
            monkeypatch,
            in_order(httpx.ConnectError, httpx.Response(200, json={"match_id": "xyz-789"})),
        )
        assert await report_match({"players": []}) == {"match_id": "xyz-789"}
        assert len(requests) == 2

    @pytest.mark.usefixtures("quiet_span_errors")
    async def test_report_match_fails_after_all_retries(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        attempts = [httpx.ConnectError] * castlog_module.RETRY_ATTEMPTS
        requests = serve_httpx(monkeypatch, in_order(*attempts))
        assert await report_match({"players": []}) is None
        assert len(requests) == castlog_module.RETRY_ATTEMPTS

    async def test_report_match_zero_retry_attempts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(castlog_module, "RETRY_ATTEMPTS", 0)
        monkeypatch.setattr(
            castlog_module,
            "fetch_castlog_report",
            decoys.async_raising(AssertionError("no attempts means no requests")),
        )
        assert await report_match({"players": []}) is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("quiet_span_errors")
class TestCastlogTerminalClientErrors:
    async def test_400_is_not_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        requests = serve_httpx(
            monkeypatch,
            in_order(httpx.Response(400, text="malformed payload")),
        )
        assert await report_match({"players": []}) is None
        assert len(requests) == 1

    async def test_503_is_still_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        attempts = [httpx.Response(503)] * castlog_module.RETRY_ATTEMPTS
        requests = serve_httpx(monkeypatch, in_order(*attempts))
        assert await report_match({"players": []}) is None
        assert len(requests) == castlog_module.RETRY_ATTEMPTS
