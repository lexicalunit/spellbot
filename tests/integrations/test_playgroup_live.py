from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import spellbot.integrations.playgroup_live as playgroup_live_module
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.integrations.playgroup_live import (
    fetch_playgroup_live_session,
    find_linked_player,
    generate_link,
    lookup_playgroup_user,
    playgroup_bracket,
    playgroup_life_amount,
)
from tests.mocks import create_mock_game, create_mock_user


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


class TestLookupPlaygroupUser:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"id": 42, "username": "testplayer"}
        mock_client.get = AsyncMock(return_value=mock_response)

        with (
            patch.object(playgroup_live_module.settings, "PLAYGROUP_LIVE_API_KEY", "test-key"),
            patch.object(
                playgroup_live_module.settings,
                "PLAYGROUP_LIVE_API_URL",
                "https://playgroup.gg",
            ),
        ):
            user_id, username = await lookup_playgroup_user(mock_client, 123456789)

        assert user_id == 42
        assert username == "testplayer"
        mock_client.get.assert_called_once()
        call_url = mock_client.get.call_args[0][0]
        assert "123456789" in call_url

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client.get = AsyncMock(return_value=mock_response)

        with (
            patch.object(playgroup_live_module.settings, "PLAYGROUP_LIVE_API_KEY", "test-key"),
            patch.object(
                playgroup_live_module.settings,
                "PLAYGROUP_LIVE_API_URL",
                "https://playgroup.gg",
            ),
        ):
            user_id, username = await lookup_playgroup_user(mock_client, 999)

        assert user_id is None
        assert username is None

    @pytest.mark.asyncio
    async def test_http_error(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=mock_response,
            ),
        )
        mock_client.get = AsyncMock(return_value=mock_response)

        with (
            patch.object(playgroup_live_module.settings, "PLAYGROUP_LIVE_API_KEY", "test-key"),
            patch.object(
                playgroup_live_module.settings,
                "PLAYGROUP_LIVE_API_URL",
                "https://playgroup.gg",
            ),
        ):
            user_id, username = await lookup_playgroup_user(mock_client, 123)

        assert user_id is None
        assert username is None

    @pytest.mark.asyncio
    async def test_network_error(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))

        with (
            patch.object(playgroup_live_module.settings, "PLAYGROUP_LIVE_API_KEY", "test-key"),
            patch.object(
                playgroup_live_module.settings,
                "PLAYGROUP_LIVE_API_URL",
                "https://playgroup.gg",
            ),
        ):
            user_id, username = await lookup_playgroup_user(mock_client, 123)

        assert user_id is None
        assert username is None


class TestFetchPlaygroupLiveSession:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"url": "https://playgroup.gg/live/abc123"}
        mock_client.post = AsyncMock(return_value=mock_response)

        game = create_mock_game(
            game_id=42,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            bracket=GameBracket.NONE.value,
        )

        with (
            patch.object(playgroup_live_module.settings, "PLAYGROUP_LIVE_API_KEY", "test-key"),
            patch.object(
                playgroup_live_module.settings,
                "PLAYGROUP_LIVE_API_URL",
                "https://playgroup.gg",
            ),
        ):
            result = await fetch_playgroup_live_session(mock_client, game, 42, 4)

        assert result == {"url": "https://playgroup.gg/live/abc123"}
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["player_amount"] == 4
        assert payload["life_amount"] == 40
        assert payload["client_identifier"] == "spellbot"
        assert payload["on_behalf_of_user_id"] == 42
        assert "bracket" not in payload

    @pytest.mark.asyncio
    async def test_with_bracket(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"url": "https://playgroup.gg/live/xyz"}
        mock_client.post = AsyncMock(return_value=mock_response)

        game = create_mock_game(
            game_id=42,
            game_format=GameFormat.COMMANDER.value,
            seats=4,
            bracket=GameBracket.BRACKET_3.value,
        )

        with (
            patch.object(playgroup_live_module.settings, "PLAYGROUP_LIVE_API_KEY", "test-key"),
            patch.object(
                playgroup_live_module.settings,
                "PLAYGROUP_LIVE_API_URL",
                "https://playgroup.gg",
            ),
        ):
            await fetch_playgroup_live_session(mock_client, game, 42, 4)

        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["bracket"] == 3

    @pytest.mark.asyncio
    async def test_player_amount_capped_at_6(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"url": "https://playgroup.gg/live/big"}
        mock_client.post = AsyncMock(return_value=mock_response)

        game = create_mock_game(
            game_id=42,
            game_format=GameFormat.COMMANDER.value,
            seats=10,
            bracket=GameBracket.NONE.value,
        )

        with (
            patch.object(playgroup_live_module.settings, "PLAYGROUP_LIVE_API_KEY", "test-key"),
            patch.object(
                playgroup_live_module.settings,
                "PLAYGROUP_LIVE_API_URL",
                "https://playgroup.gg",
            ),
        ):
            await fetch_playgroup_live_session(mock_client, game, 42, 10)

        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["player_amount"] == 6


class TestGenerateLink:
    @pytest.mark.asyncio
    async def test_no_api_key(self) -> None:
        game = create_mock_game()

        with patch.object(playgroup_live_module.settings, "PLAYGROUP_LIVE_API_KEY", ""):
            result = await generate_link(game)

        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_no_linked_player(self) -> None:
        game = create_mock_game(service=GameService.PLAYGROUP_LIVE.value)
        game.players = [create_mock_user(xid=100)]

        with patch.object(playgroup_live_module.settings, "PLAYGROUP_LIVE_API_KEY", "test-key"):
            result = await generate_link(game)

        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        game = create_mock_game(
            game_id=42,
            game_format=GameFormat.COMMANDER.value,
            service=GameService.PLAYGROUP_LIVE.value,
            seats=4,
            bracket=GameBracket.NONE.value,
        )
        host = create_mock_user(xid=100)
        host.playgroup_user_id = 42
        game.players = [host]

        with (
            patch.object(playgroup_live_module.settings, "PLAYGROUP_LIVE_API_KEY", "test-key"),
            patch.object(
                playgroup_live_module,
                "fetch_playgroup_live_session",
                AsyncMock(return_value={"url": "https://playgroup.gg/live/abc123"}),
            ),
        ):
            result = await generate_link(game)

        assert result == ("https://playgroup.gg/live/abc123", None)

    @pytest.mark.asyncio
    async def test_uses_original_seats(self) -> None:
        game = create_mock_game(
            game_id=42,
            game_format=GameFormat.COMMANDER.value,
            service=GameService.PLAYGROUP_LIVE.value,
            seats=2,
            bracket=GameBracket.NONE.value,
        )
        host = create_mock_user(xid=100)
        host.playgroup_user_id = 42
        game.players = [host]

        mock_fetch = AsyncMock(return_value={"url": "https://playgroup.gg/live/abc123"})

        with (
            patch.object(playgroup_live_module.settings, "PLAYGROUP_LIVE_API_KEY", "test-key"),
            patch.object(playgroup_live_module, "fetch_playgroup_live_session", mock_fetch),
        ):
            result = await generate_link(game, original_seats=4)

        assert result == ("https://playgroup.gg/live/abc123", None)
        call_args = mock_fetch.call_args
        assert call_args[0][3] == 4  # player_amount argument

    @pytest.mark.asyncio
    async def test_retries_on_failure_then_succeeds(self) -> None:
        game = create_mock_game(
            game_id=42,
            game_format=GameFormat.COMMANDER.value,
            service=GameService.PLAYGROUP_LIVE.value,
            seats=4,
            bracket=GameBracket.NONE.value,
        )
        host = create_mock_user(xid=100)
        host.playgroup_user_id = 42
        game.players = [host]

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"url": "https://playgroup.gg/live/retry"}

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            side_effect=[Exception("Connection error"), mock_response],
        )

        with (
            patch.object(playgroup_live_module.settings, "PLAYGROUP_LIVE_API_KEY", "test-key"),
            patch.object(
                playgroup_live_module.settings,
                "PLAYGROUP_LIVE_API_URL",
                "https://playgroup.gg",
            ),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(playgroup_live_module, "add_span_error"),
        ):
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await generate_link(game)

        assert result == ("https://playgroup.gg/live/retry", None)
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_fails_after_all_retries(self) -> None:
        game = create_mock_game(
            game_id=42,
            game_format=GameFormat.COMMANDER.value,
            service=GameService.PLAYGROUP_LIVE.value,
            seats=4,
            bracket=GameBracket.NONE.value,
        )
        host = create_mock_user(xid=100)
        host.playgroup_user_id = 42
        game.players = [host]

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=Exception("Connection error"))

        with (
            patch.object(playgroup_live_module.settings, "PLAYGROUP_LIVE_API_KEY", "test-key"),
            patch.object(
                playgroup_live_module.settings,
                "PLAYGROUP_LIVE_API_URL",
                "https://playgroup.gg",
            ),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(playgroup_live_module, "add_span_error"),
        ):
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await generate_link(game)

        assert result == (None, None)
        assert mock_client.post.call_count == playgroup_live_module.RETRY_ATTEMPTS

    @pytest.mark.asyncio
    async def test_returns_none_when_session_data_empty(self) -> None:
        game = create_mock_game(
            game_id=42,
            game_format=GameFormat.COMMANDER.value,
            service=GameService.PLAYGROUP_LIVE.value,
            seats=4,
            bracket=GameBracket.NONE.value,
        )
        host = create_mock_user(xid=100)
        host.playgroup_user_id = 42
        game.players = [host]

        with (
            patch.object(playgroup_live_module.settings, "PLAYGROUP_LIVE_API_KEY", "test-key"),
            patch.object(
                playgroup_live_module,
                "fetch_playgroup_live_session",
                AsyncMock(return_value={}),
            ),
        ):
            result = await generate_link(game)

        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_returns_none_when_no_retry_attempts(self) -> None:
        game = create_mock_game(
            game_id=42,
            game_format=GameFormat.COMMANDER.value,
            service=GameService.PLAYGROUP_LIVE.value,
            seats=4,
            bracket=GameBracket.NONE.value,
        )
        host = create_mock_user(xid=100)
        host.playgroup_user_id = 42
        game.players = [host]

        with (
            patch.object(playgroup_live_module.settings, "PLAYGROUP_LIVE_API_KEY", "test-key"),
            patch.object(playgroup_live_module, "RETRY_ATTEMPTS", 0),
        ):
            result = await generate_link(game)

        assert result == (None, None)
