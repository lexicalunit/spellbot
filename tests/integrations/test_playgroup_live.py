# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest

import spellbot.integrations.playgroup_live as playgroup_live_module
from spellbot.data import GameLinkDetails
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.integrations import http_errors
from spellbot.integrations.playgroup_live import (
    fetch_playgroup_live_session,
    find_linked_player,
    generate_link,
    lookup_playgroup_user,
    playgroup_bracket,
    playgroup_life_amount,
)
from tests.mocks import create_mock_game, create_mock_user, decoys
from tests.mocks.http import client_for, in_order, recording_client, serve_httpx

if TYPE_CHECKING:
    from spellbot.data import GameData
    from tests.fixtures import Stub

API_URL = "https://playgroup.gg"
SESSIONS_URL = f"{API_URL}/api/public/v1/live_sessions"


@pytest.fixture(autouse=True)
def playgroup_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(playgroup_live_module.settings, "PLAYGROUP_LIVE_API_KEY", "test-key")
    monkeypatch.setattr(playgroup_live_module.settings, "PLAYGROUP_LIVE_API_URL", API_URL)


@pytest.fixture
def quiet_span_errors(stub: Stub) -> None:
    stub(http_errors, "add_span_error")


def linked_game(seats: int = 4) -> GameData:
    """Build a Playgroup Live game hosted by a player linked to Playgroup user 42."""
    game = create_mock_game(
        game_id=42,
        game_format=GameFormat.COMMANDER.value,
        service=GameService.PLAYGROUP_LIVE.value,
        seats=seats,
        bracket=GameBracket.NONE.value,
    )
    host = create_mock_user(xid=100)
    host.playgroup_user_id = 42
    game.players = [host]
    return game


def session(url: str | None) -> httpx.Response:
    return httpx.Response(200, json={"url": url} if url else {})


class TestPlaygroupLifeAmount:
    @pytest.mark.parametrize(
        ("game_format", "expected"),
        [
            pytest.param(GameFormat.COMMANDER, 40, id="commander"),
            pytest.param(GameFormat.EDH_MAX, 40, id="edh_max"),
            pytest.param(GameFormat.EDH_HIGH, 40, id="edh_high"),
            pytest.param(GameFormat.EDH_MID, 40, id="edh_mid"),
            pytest.param(GameFormat.EDH_LOW, 40, id="edh_low"),
            pytest.param(GameFormat.EDH_BATTLECRUISER, 40, id="edh_battlecruiser"),
            pytest.param(GameFormat.PRE_CONS, 40, id="pre_cons"),
            pytest.param(GameFormat.CEDH, 40, id="cedh"),
            pytest.param(GameFormat.PAUPER_EDH, 40, id="pauper_edh"),
            pytest.param(GameFormat.PLANECHASE, 40, id="planechase"),
            pytest.param(GameFormat.ARCHENEMY, 40, id="archenemy"),
            pytest.param(GameFormat.HORDE_MAGIC, 40, id="horde_magic"),
            pytest.param(GameFormat.TWO_HEADED_GIANT, 30, id="two_headed_giant"),
            pytest.param(GameFormat.BRAWL_TWO_PLAYER, 25, id="brawl_two_player"),
            pytest.param(GameFormat.BRAWL_MULTIPLAYER, 25, id="brawl_multiplayer"),
            pytest.param(GameFormat.STANDARD, 20, id="standard"),
            pytest.param(GameFormat.MODERN, 20, id="modern"),
            pytest.param(GameFormat.PIONEER, 20, id="pioneer"),
            pytest.param(GameFormat.PAUPER, 20, id="pauper"),
            pytest.param(GameFormat.LEGACY, 20, id="legacy"),
            pytest.param(GameFormat.VINTAGE, 20, id="vintage"),
            pytest.param(GameFormat.SEALED, 20, id="sealed"),
            pytest.param(GameFormat.OATHBREAKER, 20, id="oathbreaker"),
            pytest.param(GameFormat.DUEL_COMMANDER, 20, id="duel_commander"),
        ],
    )
    def test_life_amount_mapping(self, game_format: GameFormat, expected: int) -> None:
        assert playgroup_life_amount(game_format) == expected

    def test_all_formats_covered(self) -> None:
        for fmt in GameFormat:
            result = playgroup_life_amount(fmt)
            assert isinstance(result, int)
            assert result > 0


class TestPlaygroupBracket:
    @pytest.mark.parametrize(
        ("bracket", "expected"),
        [
            pytest.param(GameBracket.NONE.value, None, id="none"),
            pytest.param(GameBracket.BRACKET_1.value, 1, id="bracket_1"),
            pytest.param(GameBracket.BRACKET_2.value, 2, id="bracket_2"),
            pytest.param(GameBracket.BRACKET_3.value, 3, id="bracket_3"),
            pytest.param(GameBracket.BRACKET_4.value, 4, id="bracket_4"),
            pytest.param(GameBracket.BRACKET_5.value, 5, id="bracket_5"),
        ],
    )
    def test_bracket_mapping(self, bracket: int, expected: int | None) -> None:
        assert playgroup_bracket(bracket) == expected


class TestFindLinkedPlayer:
    def test_no_players(self) -> None:
        game = create_mock_game()
        assert find_linked_player(game) is None

    def test_no_linked_players(self) -> None:
        game = create_mock_game()
        game.players = [create_mock_user(xid=100), create_mock_user(xid=200)]
        assert find_linked_player(game) is None

    def test_first_player_linked(self) -> None:
        game = create_mock_game()
        game.players = [create_mock_user(xid=100), create_mock_user(xid=200)]
        game.players[0].playgroup_user_id = 42
        assert find_linked_player(game) == 42

    def test_second_player_linked(self) -> None:
        game = create_mock_game()
        game.players = [create_mock_user(xid=100), create_mock_user(xid=200)]
        game.players[1].playgroup_user_id = 99
        assert find_linked_player(game) == 99


@pytest.mark.asyncio
class TestLookupPlaygroupUser:
    async def test_success(self) -> None:
        client, requests = recording_client(
            httpx.Response(200, json={"id": 42, "username": "testplayer"}),
        )
        assert await lookup_playgroup_user(client, 123456789) == (42, "testplayer")
        [request] = requests
        assert str(request.url) == f"{API_URL}/api/v2/users/by_discord/123456789"

    async def test_not_found(self) -> None:
        client, _ = recording_client(httpx.Response(404))
        assert await lookup_playgroup_user(client, 999) == (None, None)

    async def test_http_error(self) -> None:
        client, _ = recording_client(httpx.Response(500))
        assert await lookup_playgroup_user(client, 123) == (None, None)

    async def test_network_error(self) -> None:
        client = client_for(in_order(httpx.ConnectError))
        assert await lookup_playgroup_user(client, 123) == (None, None)


@pytest.mark.asyncio
class TestFetchPlaygroupLiveSession:
    async def test_success(self) -> None:
        client, requests = recording_client(session("https://playgroup.gg/live/abc123"))
        game = create_mock_game(
            game_id=42,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            bracket=GameBracket.NONE.value,
        )

        result = await fetch_playgroup_live_session(client, game, 42, 4)

        assert result == {"url": "https://playgroup.gg/live/abc123"}
        [request] = requests
        assert str(request.url) == SESSIONS_URL
        assert json.loads(request.content) == {
            "player_amount": 4,
            "life_amount": 40,
            "client_identifier": "spellbot",
            "on_behalf_of_user_id": 42,
        }

    async def test_with_bracket(self) -> None:
        client, requests = recording_client(session("https://playgroup.gg/live/xyz"))
        game = create_mock_game(
            game_id=42,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            bracket=GameBracket.BRACKET_3.value,
        )

        await fetch_playgroup_live_session(client, game, 42, 4)

        assert json.loads(requests[0].content)["bracket"] == 3

    async def test_player_amount_capped_at_6(self) -> None:
        client, requests = recording_client(session("https://playgroup.gg/live/big"))
        game = create_mock_game(
            game_id=42,
            game_format=GameFormat.COMMANDER.value,
            seats=10,
            bracket=GameBracket.NONE.value,
        )

        await fetch_playgroup_live_session(client, game, 42, 10)

        assert json.loads(requests[0].content)["player_amount"] == 6


@pytest.mark.asyncio
class TestGenerateLink:
    async def test_no_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(playgroup_live_module.settings, "PLAYGROUP_LIVE_API_KEY", "")
        assert await generate_link(create_mock_game()) == GameLinkDetails()

    async def test_no_linked_player(self) -> None:
        game = create_mock_game(service=GameService.PLAYGROUP_LIVE.value)
        game.players = [create_mock_user(xid=100)]
        assert await generate_link(game) == GameLinkDetails()

    async def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        serve_httpx(monkeypatch, in_order(session("https://playgroup.gg/live/abc123")))
        result = await generate_link(linked_game())
        assert result == GameLinkDetails("https://playgroup.gg/live/abc123")

    async def test_uses_original_seats(self, monkeypatch: pytest.MonkeyPatch) -> None:
        requests = serve_httpx(monkeypatch, in_order(session("https://playgroup.gg/live/abc123")))

        result = await generate_link(linked_game(seats=2), original_seats=4)

        assert result == GameLinkDetails("https://playgroup.gg/live/abc123")
        assert json.loads(requests[0].content)["player_amount"] == 4

    @pytest.mark.usefixtures("quiet_span_errors")
    async def test_retries_on_failure_then_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        requests = serve_httpx(
            monkeypatch,
            in_order(httpx.ConnectError, session("https://playgroup.gg/live/retry")),
        )
        result = await generate_link(linked_game())
        assert result == GameLinkDetails("https://playgroup.gg/live/retry")
        assert len(requests) == 2

    @pytest.mark.usefixtures("quiet_span_errors")
    async def test_fails_after_all_retries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        attempts = [httpx.ConnectError] * playgroup_live_module.RETRY_ATTEMPTS
        requests = serve_httpx(monkeypatch, in_order(*attempts))
        assert await generate_link(linked_game()) == GameLinkDetails()
        assert len(requests) == playgroup_live_module.RETRY_ATTEMPTS

    async def test_returns_none_when_session_data_empty(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        serve_httpx(monkeypatch, in_order(session(None)))
        assert await generate_link(linked_game()) == GameLinkDetails()

    async def test_returns_none_when_no_retry_attempts(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(playgroup_live_module, "RETRY_ATTEMPTS", 0)
        monkeypatch.setattr(
            playgroup_live_module,
            "fetch_playgroup_live_session",
            decoys.async_raising(AssertionError("no attempts means no requests")),
        )
        assert await generate_link(linked_game()) == GameLinkDetails()


@pytest.mark.asyncio
@pytest.mark.usefixtures("quiet_span_errors")
class TestPlaygroupLiveTerminalClientErrors:
    async def test_400_is_not_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        requests = serve_httpx(
            monkeypatch,
            in_order(httpx.Response(400, text="bad session request")),
        )
        assert await generate_link(linked_game()) == GameLinkDetails()
        assert len(requests) == 1

    async def test_500_is_still_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        attempts = [httpx.Response(500)] * playgroup_live_module.RETRY_ATTEMPTS
        requests = serve_httpx(monkeypatch, in_order(*attempts))
        assert await generate_link(linked_game()) == GameLinkDetails()
        assert len(requests) == playgroup_live_module.RETRY_ATTEMPTS


@pytest.mark.asyncio
class TestFindPlaygroupUser:
    async def test_looks_up_with_a_fresh_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        requests = serve_httpx(
            monkeypatch,
            in_order(httpx.Response(200, json={"id": 7, "username": "seven"})),
        )
        assert await playgroup_live_module.find_playgroup_user(123) == (7, "seven")
        assert str(requests[0].url) == f"{API_URL}/api/v2/users/by_discord/123"
