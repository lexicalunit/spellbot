from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import spellbot.integrations.convoke as convoke_module
from spellbot.enums import GameBracket, GameFormat
from spellbot.integrations.convoke import (
    ConvokeGameTypes,
    convoke_game_format,
    fetch_convoke_link,
    generate_link,
    passphrase,
)

if TYPE_CHECKING:
    from spellbot.models import GameDict


class TestConvokeGameFormat:
    @pytest.mark.parametrize(
        ("game_format", "expected"),
        [
            pytest.param(GameFormat.COMMANDER, ConvokeGameTypes.Commander, id="commander"),
            pytest.param(GameFormat.EDH_MAX, ConvokeGameTypes.Commander, id="edh_max"),
            pytest.param(GameFormat.EDH_HIGH, ConvokeGameTypes.Commander, id="edh_high"),
            pytest.param(GameFormat.EDH_MID, ConvokeGameTypes.Commander, id="edh_mid"),
            pytest.param(GameFormat.EDH_LOW, ConvokeGameTypes.Commander, id="edh_low"),
            pytest.param(
                GameFormat.EDH_BATTLECRUISER,
                ConvokeGameTypes.Commander,
                id="edh_battlecruiser",
            ),
            pytest.param(GameFormat.PRE_CONS, ConvokeGameTypes.Commander, id="pre_cons"),
            pytest.param(GameFormat.CEDH, ConvokeGameTypes.Commander, id="cedh"),
            pytest.param(GameFormat.PAUPER_EDH, ConvokeGameTypes.Commander, id="pauper_edh"),
            pytest.param(GameFormat.MODERN, ConvokeGameTypes.Modern, id="modern"),
            pytest.param(GameFormat.STANDARD, ConvokeGameTypes.Standard, id="standard"),
            pytest.param(GameFormat.HORDE_MAGIC, ConvokeGameTypes.Horde, id="horde_magic"),
            pytest.param(GameFormat.PLANECHASE, ConvokeGameTypes.Planechase, id="planechase"),
            pytest.param(GameFormat.LEGACY, ConvokeGameTypes.Other, id="legacy"),
            pytest.param(GameFormat.VINTAGE, ConvokeGameTypes.Other, id="vintage"),
            pytest.param(GameFormat.PIONEER, ConvokeGameTypes.Other, id="pioneer"),
        ],
    )
    def test_game_format_mapping(
        self,
        game_format: GameFormat,
        expected: ConvokeGameTypes,
    ) -> None:
        assert convoke_game_format(game_format) == expected


class TestPassphrase:
    def test_passphrase_when_disabled(self) -> None:
        with patch.object(convoke_module, "USE_PASSWORD", False):
            assert passphrase() is None

    def test_passphrase_when_enabled(self) -> None:
        with patch.object(convoke_module, "USE_PASSWORD", True):
            result = passphrase()
            assert result is not None
            parts = result.split(" ")
            assert len(parts) == 2
            assert parts[0] in convoke_module.ADJECTIVES
            assert parts[1] in convoke_module.NOUNS


class TestFetchConvokeLink:
    @pytest.mark.asyncio
    async def test_fetch_convoke_link_success(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"url": "https://convoke.gg/game/123"}
        mock_client.post = AsyncMock(return_value=mock_response)

        game = cast(
            "GameDict",
            {
                "id": 42,
                "format": GameFormat.COMMANDER.value,
                "seats": 4,
                "guild_xid": 12345,
                "channel_xid": 67890,
                "bracket": GameBracket.NONE.value,
            },
        )

        players = [
            {"xid": 100, "name": "Player1", "pin": "123456"},
            {"xid": 200, "name": "Player2", "pin": None},
        ]

        with (
            patch.object(
                convoke_module.services.games,
                "player_data",
                AsyncMock(return_value=players),
            ),
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key"),
            patch.object(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg"),
        ):
            result = await fetch_convoke_link(mock_client, game, None)

        assert result == {"url": "https://convoke.gg/game/123"}
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["spellbotGameId"] == "42"
        assert payload["spellbotGamePins"] == ["123456"]
        assert payload["discordPlayers"] == [
            {"id": "100", "name": "Player1"},
            {"id": "200", "name": "Player2"},
        ]

    @pytest.mark.asyncio
    async def test_fetch_convoke_link_with_bracket(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"url": "https://convoke.gg/game/456"}
        mock_client.post = AsyncMock(return_value=mock_response)

        game = cast(
            "GameDict",
            {
                "id": 99,
                "format": GameFormat.COMMANDER.value,
                "seats": 4,
                "guild_xid": 12345,
                "channel_xid": 67890,
                "bracket": GameBracket.BRACKET_2.value,
            },
        )

        with (
            patch.object(
                convoke_module.services.games,
                "player_data",
                AsyncMock(return_value=[]),
            ),
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key"),
            patch.object(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg"),
        ):
            result = await fetch_convoke_link(mock_client, game, None)

        assert result == {"url": "https://convoke.gg/game/456"}
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["bracketLevel"] == "B2"  # BRACKET_2.value (3) -> B{3-1} = B2

    @pytest.mark.asyncio
    async def test_fetch_convoke_link_with_password(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"url": "https://convoke.gg/game/789"}
        mock_client.post = AsyncMock(return_value=mock_response)

        game = cast(
            "GameDict",
            {
                "id": 101,
                "format": GameFormat.COMMANDER.value,
                "seats": 4,
                "guild_xid": 12345,
                "channel_xid": 67890,
                "bracket": GameBracket.NONE.value,
            },
        )

        with (
            patch.object(
                convoke_module.services.games,
                "player_data",
                AsyncMock(return_value=[]),
            ),
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_api_key"),
            patch.object(convoke_module.settings, "CONVOKE_ROOT", "https://api.convoke.gg"),
        ):
            result = await fetch_convoke_link(mock_client, game, "secret_pass")

        assert result == {"url": "https://convoke.gg/game/789"}
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["password"] == "secret_pass"


class TestGenerateLink:
    @pytest.mark.asyncio
    async def test_generate_link_no_api_key(self) -> None:
        game = cast(
            "GameDict",
            {"id": 1, "format": GameFormat.COMMANDER.value},
        )

        with patch.object(convoke_module.settings, "CONVOKE_API_KEY", ""):
            result = await generate_link(game)

        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_generate_link_success(self) -> None:
        game = cast(
            "GameDict",
            {
                "id": 1,
                "format": GameFormat.COMMANDER.value,
                "seats": 4,
                "guild_xid": 12345,
                "channel_xid": 67890,
                "bracket": GameBracket.NONE.value,
            },
        )

        with (
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_key"),
            patch.object(convoke_module, "passphrase", return_value=None),
            patch.object(
                convoke_module,
                "fetch_convoke_link",
                AsyncMock(return_value={"url": "https://convoke.gg/game/123"}),
            ),
        ):
            result = await generate_link(game)

        assert result == ("https://convoke.gg/game/123", None)

    @pytest.mark.asyncio
    async def test_generate_link_success_with_password_from_response(self) -> None:
        game = cast(
            "GameDict",
            {
                "id": 1,
                "format": GameFormat.COMMANDER.value,
                "seats": 4,
                "guild_xid": 12345,
                "channel_xid": 67890,
                "bracket": GameBracket.NONE.value,
            },
        )

        with (
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_key"),
            patch.object(convoke_module, "passphrase", return_value=None),
            patch.object(
                convoke_module,
                "fetch_convoke_link",
                AsyncMock(
                    return_value={"url": "https://convoke.gg/game/123", "password": "resp_pass"},
                ),
            ),
        ):
            result = await generate_link(game)

        assert result == ("https://convoke.gg/game/123", "resp_pass")

    @pytest.mark.asyncio
    async def test_generate_link_success_with_passphrase(self) -> None:
        game = cast(
            "GameDict",
            {
                "id": 1,
                "format": GameFormat.COMMANDER.value,
                "seats": 4,
                "guild_xid": 12345,
                "channel_xid": 67890,
                "bracket": GameBracket.NONE.value,
            },
        )

        with (
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_key"),
            patch.object(convoke_module, "passphrase", return_value="ancient dragon"),
            patch.object(
                convoke_module,
                "fetch_convoke_link",
                AsyncMock(return_value={"url": "https://convoke.gg/game/456"}),
            ),
        ):
            result = await generate_link(game)

        assert result == ("https://convoke.gg/game/456", "ancient dragon")

    @pytest.mark.asyncio
    async def test_generate_link_retries_on_failure_then_succeeds(self) -> None:
        """Test that generate_link retries after failure and succeeds on second attempt."""
        game = cast(
            "GameDict",
            {
                "id": 1,
                "format": GameFormat.COMMANDER.value,
                "seats": 4,
                "guild_xid": 12345,
                "channel_xid": 67890,
                "bracket": GameBracket.NONE.value,
            },
        )

        # Create a mock that fails then succeeds (to test the retry path)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"url": "https://convoke.gg/game/789"}

        mock_client = MagicMock(spec=httpx.AsyncClient)
        # First call fails, second call succeeds
        mock_client.post = AsyncMock(
            side_effect=[Exception("Connection error"), mock_response],
        )

        mock_player_data = AsyncMock(return_value=[])

        with (
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_key"),
            patch.object(convoke_module, "passphrase", return_value=None),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(convoke_module, "add_span_error"),
            patch.object(convoke_module.services.games, "player_data", mock_player_data),
        ):
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await generate_link(game)

        # First attempt fails, second succeeds
        assert result == ("https://convoke.gg/game/789", None)
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_link_fails_after_all_retries(self) -> None:
        """Test that generate_link returns None after exhausting all retry attempts."""
        game = cast(
            "GameDict",
            {
                "id": 1,
                "format": GameFormat.COMMANDER.value,
                "seats": 4,
                "guild_xid": 12345,
                "channel_xid": 67890,
                "bracket": GameBracket.NONE.value,
            },
        )

        mock_client = MagicMock(spec=httpx.AsyncClient)
        # All calls fail
        mock_client.post = AsyncMock(side_effect=Exception("Connection error"))

        mock_player_data = AsyncMock(return_value=[])

        with (
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_key"),
            patch.object(convoke_module, "passphrase", return_value=None),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(convoke_module, "add_span_error"),
            patch.object(convoke_module.services.games, "player_data", mock_player_data),
        ):
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await generate_link(game)

        # All attempts fail, returns None
        assert result == (None, None)
        # Verify that the post method was called RETRY_ATTEMPTS times (2)
        assert mock_client.post.call_count == convoke_module.RETRY_ATTEMPTS

    @pytest.mark.asyncio
    async def test_generate_link_returns_none_when_data_is_empty(self) -> None:
        """Test that generate_link returns None when fetch_convoke_link returns empty dict."""
        game = cast(
            "GameDict",
            {
                "id": 1,
                "format": GameFormat.COMMANDER.value,
                "seats": 4,
                "guild_xid": 12345,
                "channel_xid": 67890,
                "bracket": GameBracket.NONE.value,
            },
        )

        # Mock the response to return an empty dict (falsy)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {}

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        mock_player_data = AsyncMock(return_value=[])

        with (
            patch.object(convoke_module.settings, "CONVOKE_API_KEY", "test_key"),
            patch.object(convoke_module, "passphrase", return_value=None),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(convoke_module.services.games, "player_data", mock_player_data),
        ):
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await generate_link(game)

        # Empty dict is falsy, so returns None
        assert result == (None, None)
