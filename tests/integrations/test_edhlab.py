# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest

import spellbot.integrations.edhlab as edhlab_module
from spellbot.data import GameLinkDetails
from spellbot.enums import GameBracket
from spellbot.integrations import http_errors
from spellbot.integrations.edhlab import fetch_edhlab_link, generate_link
from tests.mocks import create_mock_game, decoys
from tests.mocks.http import client_for, in_order, serve_httpx

if TYPE_CHECKING:
    from tests.fixtures import Stub

CREATE_URL = "https://api.edhlab.gg/create-game"


@pytest.fixture(autouse=True)
def edhlab_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(edhlab_module.settings, "EDHLAB_API_KEY", "test_key")
    monkeypatch.setattr(edhlab_module.settings, "EDHLAB_CREATE", CREATE_URL)


def created(game_url: str | None) -> httpx.Response:
    return httpx.Response(200, json={"gameUrl": game_url} if game_url else {})


@pytest.mark.asyncio
class TestFetchEdhlabLink:
    async def test_fetch_edhlab_link_success(self) -> None:
        requests: list[httpx.Request] = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return created("https://edhlab.gg/game/123")

        game = create_mock_game(game_id=42, bracket=GameBracket.NONE.value)
        result = await fetch_edhlab_link(client_for(respond), game)

        assert result == {"gameUrl": "https://edhlab.gg/game/123"}
        [request] = requests
        assert str(request.url) == CREATE_URL
        assert request.headers["Authorization"] == "Bearer test_key"
        # No bracket when NONE
        assert json.loads(request.content) == {}

    async def test_fetch_edhlab_link_with_bracket(self) -> None:
        requests: list[httpx.Request] = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return created("https://edhlab.gg/game/456")

        game = create_mock_game(game_id=99, bracket=GameBracket.BRACKET_2.value)
        result = await fetch_edhlab_link(client_for(respond), game)

        assert result == {"gameUrl": "https://edhlab.gg/game/456"}
        # BRACKET_2.value (3) -> bracket = 3 - 1 = 2
        assert json.loads(requests[0].content) == {"bracket": 2}


@pytest.mark.asyncio
class TestGenerateLink:
    async def test_generate_link_no_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(edhlab_module.settings, "EDHLAB_API_KEY", "")
        assert await generate_link(create_mock_game(game_id=1)) == GameLinkDetails()

    async def test_generate_link_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        serve_httpx(monkeypatch, in_order(created("https://edhlab.gg/game/123")))
        result = await generate_link(create_mock_game(game_id=1))
        assert result == GameLinkDetails("https://edhlab.gg/game/123")

    async def test_generate_link_retries_on_failure_then_succeeds(
        self,
        monkeypatch: pytest.MonkeyPatch,
        stub: Stub,
    ) -> None:
        """Test that generate_link retries after failure and succeeds on second attempt."""
        stub(http_errors, "add_span_error")
        requests = serve_httpx(
            monkeypatch,
            in_order(httpx.ConnectError, created("https://edhlab.gg/game/789")),
        )

        result = await generate_link(create_mock_game(game_id=1))

        assert result == GameLinkDetails("https://edhlab.gg/game/789")
        assert len(requests) == 2

    async def test_generate_link_fails_after_all_retries(
        self,
        monkeypatch: pytest.MonkeyPatch,
        stub: Stub,
    ) -> None:
        """Test that generate_link returns None after exhausting all retry attempts."""
        stub(http_errors, "add_span_error")
        attempts = [httpx.ConnectError] * edhlab_module.RETRY_ATTEMPTS
        requests = serve_httpx(monkeypatch, in_order(*attempts))

        assert await generate_link(create_mock_game(game_id=1)) == GameLinkDetails()
        assert len(requests) == edhlab_module.RETRY_ATTEMPTS

    async def test_generate_link_returns_none_when_data_is_empty(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that generate_link returns None when fetch_edhlab_link returns empty dict."""
        serve_httpx(monkeypatch, in_order(created(None)))
        assert await generate_link(create_mock_game(game_id=1)) == GameLinkDetails()

    async def test_generate_link_zero_retry_attempts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that generate_link returns None when RETRY_ATTEMPTS is 0."""
        monkeypatch.setattr(edhlab_module, "RETRY_ATTEMPTS", 0)
        monkeypatch.setattr(
            edhlab_module,
            "fetch_edhlab_link",
            decoys.async_raising(AssertionError("no attempts means no requests")),
        )
        assert await generate_link(create_mock_game(game_id=1)) == GameLinkDetails()
